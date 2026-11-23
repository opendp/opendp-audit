"""Reproduce MST score-stability under-accounting from public-model rounding.

OpenDP main 7acfb2cdcee7d39fc26a6ade7edac15249c52f4b.
Source: python/src/opendp/extras/mbi/_mst/__init__.py::_make_mst_scores.
This tests source-equivalent NumPy and ideal permute-and-flip; it does not
execute native OpenDP or mbi.MarkovRandomField.
"""
import math
import unittest

try:
    import numpy as np
except ImportError:
    np = None


PUBLIC_TOTAL = float(2**55 + 16)
EDGES = ("AB", "AC", "BC")


def neighboring_pairwise_marginals():
    """D0=4*(A0,B0,C0); D1=D0+[(A0,B0,C1)]."""
    if np is None:
        raise RuntimeError("numpy is required")
    before = {e: np.array([[4, 0], [0, 0]], dtype=np.int32) for e in EDGES}
    after = {
        "AB": np.array([[5, 0], [0, 0]], dtype=np.int32),
        "AC": np.array([[4, 1], [0, 0]], dtype=np.int32),
        "BC": np.array([[4, 1], [0, 0]], dtype=np.int32),
    }
    # Compatible public joint model has all mass at (A0,B0,C0).
    synthetic = {
        e: np.array([[PUBLIC_TOTAL, 0.0], [0.0, 0.0]], dtype=np.float64)
        for e in EDGES
    }
    return before, after, synthetic


def mst_scores(marginals, synthetic):
    # Exactly the source's induced matrix 1-norm, NOT flattened L1.
    return np.array([
        float(np.linalg.norm(marginals[e] - synthetic[e], 1))
        for e in EDGES
    ])


class TestMSTPublicModelRounding(unittest.TestCase):
    @unittest.skipIf(np is None, "numpy is an optional audit dependency")
    def test_one_insertion_changes_each_pairwise_marginal_by_one(self):
        before, after, synthetic = neighboring_pairwise_marginals()
        self.assertEqual({m.sum() for m in before.values()}, {4})
        self.assertEqual({m.sum() for m in after.values()}, {5})
        self.assertEqual({m.sum() for m in synthetic.values()}, {PUBLIC_TOTAL})
        for edge in EDGES:
            self.assertEqual(int(np.abs(after[edge] - before[edge]).sum()), 1)

    @unittest.skipIf(np is None, "numpy is an optional audit dependency")
    def test_source_equivalent_scores_exceed_stability_map(self):
        before, after, synthetic = neighboring_pairwise_marginals()
        scores_before = mst_scores(before, synthetic)
        scores_after = mst_scores(after, synthetic)
        np.testing.assert_array_equal(scores_before, [PUBLIC_TOTAL] * 3)
        np.testing.assert_array_equal(scores_after - scores_before, [-8.0, 0.0, 0.0])
        observed_linf = float(np.max(np.abs(scores_after - scores_before)))
        declared_linf = 1  # max(distance[1] for distance in d_in.values())
        self.assertEqual(observed_linf, 8.0)
        self.assertGreater(observed_linf, declared_linf)

    @unittest.skipIf(np is None, "numpy is an optional audit dependency")
    def test_selection_likelihood_exceeds_declared_epsilon(self):
        before, after, synthetic = neighboring_pairwise_marginals()
        scores_before = mst_scores(before, synthetic)
        scores_after = mst_scores(after, synthetic)
        gap = float(scores_after[1] - scores_after[0])
        self.assertEqual(gap, 8.0)
        scale = 4.0
        # With three initially tied candidates, P(AB)=1/3.
        # When AB alone is lower by gap, it must be visited first (1/3)
        # and accepted (exp(-gap/scale)).
        p_before = 1.0 / 3.0
        p_after = math.exp(-gap / scale) / 3.0
        claimed_eps = 2.0 * 1.0 / scale
        actual_log_ratio = math.log(p_before / p_after)
        self.assertEqual(claimed_eps, 0.5)
        self.assertAlmostEqual(actual_log_ratio, 2.0)
        self.assertGreater(actual_log_ratio, claimed_eps)


if __name__ == "__main__":
    unittest.main()
