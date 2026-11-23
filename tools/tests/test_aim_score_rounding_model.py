"""Standalone regression model for OpenDP AIM score-subtraction sensitivity.

Pinned upstream: 7acfb2cdcee7d39fc26a6ade7edac15249c52f4b.
Models _make_aim_scores and the two-candidate permute-and-flip law;
does not construct a native OpenDP/MBI measurement.
"""
import math
import unittest

try:
    import numpy as np
except ImportError:
    np = None


PENALTY = float(2**54 + 8)
EXPECTATION = PENALTY / 2.0


def score_vectors():
    if np is None:
        raise RuntimeError("NumPy required")
    synthetic = {
        "A": np.array([1.0, 1.0]),
        "B": np.array([2.0, 0.0]),
    }
    before = {
        "A": np.array([2, 0], dtype=np.int32),
        "B": np.array([2, 0], dtype=np.int32),
    }
    after = {
        "A": np.array([3, 0], dtype=np.int32),
        "B": np.array([2, 1], dtype=np.int32),
    }
    def score(data):
        # Match _make_aim_scores, with weight=1 and shape=(2,).
        return np.array([
            np.linalg.norm((data[key] - synthetic[key]).flatten(), 1)
            - PENALTY
            for key in ("A", "B")
        ], dtype=np.float64)
    return before, after, score(before), score(after)


class TestAIMScoreRoundingModel(unittest.TestCase):
    def test_public_penalty_from_small_positive_measurement_budget(self):
        self.assertTrue(math.isfinite(PENALTY))
        self.assertTrue(math.isfinite(EXPECTATION))
        self.assertGreater(EXPECTATION, 0)
        # get_scale(MaxDivergence, d_out, sensitivity) = sensitivity / d_out.
        d_measure = 1.0 / EXPECTATION
        self.assertGreater(d_measure, 0)
        self.assertEqual(1.0 / d_measure, EXPECTATION)
        self.assertEqual(2.0 * EXPECTATION, PENALTY)

    @unittest.skipIf(np is None, "NumPy optional in audit CI")
    def test_neighboring_datasets_have_unit_marginal_l1_distance(self):
        before, after, _, _ = score_vectors()
        for key in ("A", "B"):
            self.assertEqual(np.sum(np.abs(after[key] - before[key])), 1)
        # Public synthetic marginal projections are consistent in total.
        self.assertEqual(sum([1.0, 1.0]), sum([2.0, 0.0]))

    @unittest.skipIf(np is None, "NumPy optional in audit CI")
    def test_score_rounding_exceeds_claimed_stability_map(self):
        _, _, before_scores, after_scores = score_vectors()
        np.testing.assert_array_equal(before_scores, [-PENALTY, -PENALTY])
        np.testing.assert_array_equal(
            after_scores, [-PENALTY + 4.0, -PENALTY]
        )
        observed_linf = float(np.max(np.abs(after_scores - before_scores)))
        advertised_linf = 1.0  # max per-clique L1 distance * Count.weight
        self.assertEqual(observed_linf, 4.0)
        self.assertGreater(observed_linf, advertised_linf)

    def test_two_candidate_selection_exceeds_reported_pure_dp(self):
        # For permute-and-flip, when two scores differ by gap g,
        # Pr(select lower-score candidate) = exp(-g / scale) / 2.
        scale, claimed_d_in, actual_gap = 2.0, 1.0, 4.0
        advertised_epsilon = 2 * claimed_d_in / scale
        p_before = 0.5
        p_after = 0.5 * math.exp(-actual_gap / scale)
        actual_log_ratio = math.log(p_before / p_after)
        self.assertEqual(advertised_epsilon, 1.0)
        self.assertAlmostEqual(actual_log_ratio, 2.0)
        self.assertGreater(actual_log_ratio, advertised_epsilon)


if __name__ == "__main__":
    unittest.main()
