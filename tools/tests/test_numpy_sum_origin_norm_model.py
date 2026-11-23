"""Reproduce unsized NumPy sum L2-origin underflow at pinned OpenDP main.

Upstream SHA: 7acfb2cdcee7d39fc26a6ade7edac15249c52f4b.
Standalone source-equivalent model only; this does not invoke OpenDP's FFI,
extrinsic domain, native noise mechanism, or privacy map.
"""
import math
import unittest

try:
    import numpy as np
except ImportError:
    np = None


def scaled_row_membership(centered, radius, order=2):
    """Match the implementation of _rows_within_norm."""
    centered = np.ascontiguousarray(centered)
    with np.errstate(all="ignore"):
        scale = np.max(np.abs(centered), axis=1, keepdims=True, initial=0.0)
        scale = np.where(scale == 0.0, 1.0, scale)
        row_norm = np.linalg.norm(centered / scale, ord=order, axis=1, keepdims=True)
        return np.isfinite(centered).all(axis=1, keepdims=True) & (
            row_norm <= radius / scale
        )


@unittest.skipIf(np is None, "NumPy optional in audit CI")
class TestOriginNormUnderflowModel(unittest.TestCase):
    def test_positive_radius_admissible_neighboring_arrays(self):
        radius = 1e-200
        origin = np.array([1e-200], dtype=np.float64)
        x0 = np.empty((0, 1), dtype=np.float64)
        x1 = np.array([[2e-200]], dtype=np.float64)

        # The arrays differ by one insertion under SymmetricDistance.
        self.assertEqual(x0.shape, (0, 1))
        self.assertEqual(x1.shape, (1, 1))
        for x in (x0, x1):
            self.assertEqual(x.dtype, np.float64)
            self.assertTrue(scaled_row_membership(x - origin, radius).all())

        # The bare NumPy L2 norm loses the origin via squaring underflow.
        origin_norm = float(np.linalg.norm(origin, ord=2))
        self.assertEqual(origin_norm, 0.0)
        self.assertEqual(math.hypot(*origin), 1e-200)

        # Exact outputs for one-row float64 summation; no addition roundoff.
        y0, y1 = x0.sum(axis=0), x1.sum(axis=0)
        actual_l2 = math.hypot(*list(y1 - y0))
        claimed_map_one = 1 * (radius + origin_norm)
        self.assertEqual(actual_l2, 2e-200)
        self.assertEqual(claimed_map_one, 1e-200)
        self.assertGreater(actual_l2, claimed_map_one)

    def test_zero_radius_admits_nonzero_origin_but_map_returns_zero(self):
        radius = 0.0
        origin = np.array([1e-200])
        data = np.array([[1e-200]])
        self.assertTrue(scaled_row_membership(data - origin, radius).all())
        claimed_map_one = radius + float(np.linalg.norm(origin, ord=2))
        self.assertEqual(claimed_map_one, 0.0)
        self.assertEqual(data.sum(axis=0)[0], 1e-200)

    def test_zero_origin_does_not_trigger_underflow_issue(self):
        radius = 1e-200
        origin = np.array([0.0])
        data = np.array([[1e-200]])
        self.assertTrue(scaled_row_membership(data - origin, radius).all())
        self.assertEqual(radius + np.linalg.norm(origin, 2), 1e-200)
        self.assertEqual(data.sum(axis=0)[0], 1e-200)

    def test_l1_origin_norm_does_not_underflow_in_one_dimension(self):
        radius = 1e-200
        origin = np.array([1e-200])
        self.assertEqual(float(np.linalg.norm(origin, ord=1)), 1e-200)
        self.assertEqual(radius + np.linalg.norm(origin, ord=1), 2e-200)


class TestAnalyticGaussianPrivacy(unittest.TestCase):
    def test_zcdp_budget_underestimated_by_factor_four(self):
        # Ratios must be computed before squaring; squaring 1e-200 underflows.
        sigma = 1e-200
        claimed_sensitivity = 1e-200
        actual_sensitivity = 2e-200
        claimed_rho = (claimed_sensitivity / sigma) ** 2 / 2
        actual_rho = (actual_sensitivity / sigma) ** 2 / 2
        self.assertEqual(claimed_rho, 0.5)
        self.assertEqual(actual_rho, 2.0)
        self.assertGreater(actual_rho, claimed_rho)


if __name__ == "__main__":
    unittest.main()
