"""Source-equivalent SSCP transform/output-domain membership regression.

Pinned upstream: opendp/opendp a010591f55b1713c926f8e355091471634480307.
This models source code, not the OpenDP FFI or native Domain.member.

The exact negative tiny eigenvalue depends on NumPy LAPACK/BLAS and float
rounding. A witness-specific test skips if the current numerical backend
does not reproduce it; see the investigation for executed NumPy 2.3.5 results.
"""
import unittest

try:
    import numpy as np
except ImportError:
    np = None


def sscp_output_source_model(X):
    return X.T @ X


def sscp_old_member_model(C, num_features=2):
    """Replicate checks in _sscp_domain's inner _member for valid dtype."""
    if not isinstance(C, np.ndarray):
        return False
    if C.shape != (C.shape[0], C.shape[0]):
        return False
    if num_features is not None and C.shape[0] != num_features:
        return False
    if (~np.isfinite(C)).any():
        return False
    if np.any(C != C.T):
        return False
    if np.any(np.linalg.eigvals(C) < 0):
        return False
    return True


def proposed_symmetric_member_model(C, num_features=2):
    """PR #3281's proposed finite symmetric matrix domain predicate."""
    return (
        isinstance(C, np.ndarray)
        and C.shape == (num_features, num_features)
        and np.isfinite(C).all()
        and not np.any(C != C.T)
    )


@unittest.skipUnless(np is not None, "NumPy optional in audit CI")
class TestSSCPGramPSDMembership(unittest.TestCase):
    def check_candidate(self, dtype):
        X = np.array([[0.5, 0.7]], dtype=dtype)
        # Input array2_domain(norm=1,p=2,size=1,num_columns=2,nan=False,T=dtype)
        # accepts this array. The scaled source predicate and ordinary norm
        # both give a radius strictly below 1.
        self.assertEqual(X.shape, (1, 2))
        self.assertTrue(np.isfinite(X).all())
        self.assertLess(np.linalg.norm(X[0], ord=2), 1.0)
        C = sscp_output_source_model(X)
        self.assertEqual(C.dtype, dtype)
        self.assertEqual(C.shape, (2, 2))
        np.testing.assert_array_equal(C, C.T)
        self.assertTrue(np.isfinite(C).all())
        return C

    def test_float64_sscp_output_rejected_by_own_domain(self):
        C = self.check_candidate(np.float64)
        smallest = np.min(np.linalg.eigvals(C))
        if not smallest < 0.0:
            self.skipTest("LAPACK backend did not reproduce negative eigenvalue")
        self.assertFalse(sscp_old_member_model(C))
        self.assertTrue(proposed_symmetric_member_model(C))
        self.assertGreater(smallest, -1e-12)

    def test_float32_sscp_output_rejected_by_own_domain(self):
        C = self.check_candidate(np.float32)
        smallest = np.min(np.linalg.eigvals(C))
        if not smallest < 0.0:
            self.skipTest("LAPACK backend did not reproduce negative eigenvalue")
        self.assertFalse(sscp_old_member_model(C))
        self.assertTrue(proposed_symmetric_member_model(C))
        self.assertGreater(smallest, -1e-6)

    def test_binary_exact_rank_one_control_admitted(self):
        for dtype in (np.float32, np.float64):
            X = np.array([[0.5, 0.5]], dtype=dtype)
            C = sscp_output_source_model(X)
            self.assertTrue(sscp_old_member_model(C))
            self.assertTrue(proposed_symmetric_member_model(C))

    def test_non_symmetric_and_non_finite_still_rejected(self):
        for C in (
            np.array([[1.0, 2.0], [1.0, 1.0]]),
            np.array([[1.0, np.nan], [np.nan, 1.0]]),
        ):
            self.assertFalse(sscp_old_member_model(C))
            self.assertFalse(proposed_symmetric_member_model(C))


if __name__ == "__main__":
    unittest.main()
