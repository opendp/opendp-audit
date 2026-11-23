"""Standalone source-model regression for OpenDP's SSCP norm contract.

This models predicates/maps inspected at upstream
7acfb2cdcee7d39fc26a6ade7edac15249c52f4b; not a native OpenDP test.
"""

import math
import unittest

try:
    import numpy as np
except ImportError:
    np = None


class TestSSCPNormMembershipModel(unittest.TestCase):
    def test_trace_bound_required_for_bounded_data(self):
        # C = X.T @ X with one row of L2 norm <= 1 requires trace(C) <= 1.
        norm = 1.0
        size = 1
        accepted_diagonal = (16.0, 0.0)
        self.assertGreater(sum(accepted_diagonal), size * norm**2)

    def test_eigenvalue_stability_contradiction(self):
        # Two 2-row matrices differ by one row replacement; symmetric d <= 2.
        eigvals_c0 = (0.0, 0.0)
        eigvals_c1 = (0.0, 16.0)
        output_l1 = sum(abs(a - b) for a, b in zip(eigvals_c0, eigvals_c1))
        claimed = 2 * 1.0**2
        self.assertEqual(output_l1, 16.0)
        self.assertEqual(claimed, 2.0)
        self.assertGreater(output_l1, claimed)

    def test_ideal_laplace_output_event(self):
        # At scale 1, Pr[Y[1] <= 0] = 1/2 or exp(-16)/2.
        p0 = 0.5
        p1 = math.exp(-16.0) * 0.5
        self.assertAlmostEqual(math.log(p0 / p1), 16.0)
        self.assertGreater(math.log(p0 / p1), 2.0)

    @unittest.skipIf(np is None, "NumPy is optional in audit CI")
    def test_numpy_checks_current_membership_accepts_counterexample(self):
        # Model every explicitly checked predicate in _sscp_domain._member.
        c0 = np.zeros((2, 2), dtype=np.float64)
        c1 = np.diag([16.0, 0.0])
        for c in (c0, c1):
            self.assertEqual(c.dtype, np.float64)
            self.assertEqual(c.shape, (2, 2))
            self.assertTrue(np.isfinite(c).all())
            self.assertTrue(np.array_equal(c, c.T))
            self.assertFalse(np.any(np.linalg.eigvals(c) < 0))
        self.assertEqual(float(np.trace(c1)), 16.0)
        self.assertEqual(
            float(np.sum(np.abs(np.linalg.eigvalsh(c1) - np.linalg.eigvalsh(c0)))),
            16.0,
        )


if __name__ == "__main__":
    unittest.main()
