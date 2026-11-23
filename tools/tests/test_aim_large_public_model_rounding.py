"""Standalone AIM model-projection rounding privacy regression.

Pinned OpenDP main: 7acfb2cdcee7d39fc26a6ade7edac15249c52f4b.
This models the exact NumPy score formula and a two-candidate
permute-and-flip event, not the native OpenDP/MBI construction.
"""
import math
import unittest

try:
    import numpy as np
except ImportError:
    np = None


PUBLIC_TOTAL = float(2**55 + 16)
PUBLIC_PENALTY = 4.0


def score_vectors():
    if np is None:
        raise RuntimeError("NumPy required")
    # A compatible public joint synthetic table puts all its mass in (A=0,B=0).
    synthetic = {name: np.array([PUBLIC_TOTAL, 0.0]) for name in ("A", "B")}
    before = {
        "A": np.array([4, 0], dtype=np.int32),
        "B": np.array([4, 0], dtype=np.int32),
    }
    # Add one record with A=0, B=1.
    after = {
        "A": np.array([5, 0], dtype=np.int32),
        "B": np.array([4, 1], dtype=np.int32),
    }

    def score(data):
        return np.array([
            np.linalg.norm((data[key] - synthetic[key]).flatten(), 1)
            - PUBLIC_PENALTY
            for key in ("A", "B")
        ], dtype=np.float64)

    return before, after, score(before), score(after)


class TestAIMPublicModelRounding(unittest.TestCase):
    def test_public_model_and_penalty_are_finite_and_consistent(self):
        self.assertTrue(math.isfinite(PUBLIC_TOTAL))
        self.assertTrue(math.isfinite(PUBLIC_PENALTY))
        self.assertGreater(PUBLIC_TOTAL, 0)
        # Two-cell query with expected per-cell noise magnitude 2.
        # For MaxDivergence and marginal L1 sensitivity 1, d_measure=0.5.
        self.assertEqual(2.0 * (1.0 / 0.5), PUBLIC_PENALTY)

    @unittest.skipIf(np is None, "NumPy optional in audit CI")
    def test_one_record_change_exceeds_reported_score_linf_bound(self):
        before, after, scores0, scores1 = score_vectors()
        for name in ("A", "B"):
            self.assertEqual(int(np.sum(np.abs(after[name] - before[name]))), 1)
        self.assertEqual(scores0[0], scores0[1])
        np.testing.assert_array_equal(scores1 - scores0, [-16.0, 0.0])
        self.assertEqual(float(np.max(np.abs(scores1 - scores0))), 16.0)
        self.assertGreater(16.0, 1.0)  # _make_aim_scores stability map

    @unittest.skipIf(np is None, "NumPy optional in audit CI")
    def test_private_selection_event_can_exceed_claimed_epsilon(self):
        _, _, scores0, scores1 = score_vectors()
        gap = float(scores1[1] - scores1[0])
        self.assertEqual(gap, 16.0)
        scale = 4.0
        claimed_epsilon = 2.0 * 1.0 / scale
        # Under permute-and-flip, Pr(select lower score) = exp(-gap/scale)/2.
        p_a_before = 0.5
        p_a_after = 0.5 * math.exp(-gap / scale)
        observed_log_ratio = math.log(p_a_before / p_a_after)
        self.assertEqual(claimed_epsilon, 0.5)
        self.assertAlmostEqual(observed_log_ratio, 4.0)
        self.assertGreater(observed_log_ratio, claimed_epsilon)


if __name__ == "__main__":
    unittest.main()
