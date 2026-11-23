"""Source-equivalent NumPy regression for float32 SSCP arithmetic.

This is NOT an OpenDP native callback or a differential-privacy integration test.
It models the row-norm predicate in extras/numpy/_norm.py and the exact
arg.T @ arg expression in extras/numpy/_make_np_sscp/__init__.py at
OpenDP a010591f55b1713c926f8e355091471634480307.
"""
import math
import unittest
import warnings

try:
    import numpy as np
except ImportError:  # NumPy is optional in audit CI.
    np = None


@unittest.skipIf(np is None, "NumPy is optional in audit CI")
class TestNPSSCPFloat32OverflowModel(unittest.TestCase):
    @staticmethod
    def _inputs():
        return (
            np.array([[1e10, 0.0]], dtype=np.float32),
            np.array([[1e20, 0.0]], dtype=np.float32),
        )

    @staticmethod
    def _source_row_norm_member(x, norm, p):
        # Exact row predicate from OpenDP's _norm._rows_within_norm.
        x = np.ascontiguousarray(x)
        with np.errstate(all="ignore"):
            scale = np.max(np.abs(x), axis=1, keepdims=True, initial=0.0)
            scale = np.where(scale == 0.0, 1.0, scale)
            row_norm = np.linalg.norm(x / scale, ord=p, axis=1, keepdims=True)
            return (
                np.isfinite(x).all(axis=1, keepdims=True)
                & (row_norm <= norm / scale)
            )

    def test_both_adjacent_inputs_satisfy_declared_row_domain(self):
        good, bad = self._inputs()
        for x in (good, bad):
            self.assertEqual(x.dtype, np.float32)
            self.assertEqual(x.shape, (1, 2))
            self.assertTrue(self._source_row_norm_member(x, 1e21, p=2).all())
        # Same one-row dataset size, one row replaced => symmetric distance 2.
        self.assertFalse(np.array_equal(good, bad))

    def test_output_finiteness_and_warning_depend_on_private_row(self):
        good, bad = self._inputs()

        def matrix_with_warnings(x):
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always", RuntimeWarning)
                with np.errstate(over="warn"):
                    gram = x.T @ x
            return gram, [str(item.message) for item in captured]

        good_gram, good_warnings = matrix_with_warnings(good)
        bad_gram, bad_warnings = matrix_with_warnings(bad)

        self.assertEqual(good_gram.dtype, np.float32)
        self.assertEqual(bad_gram.dtype, np.float32)
        self.assertTrue(np.isfinite(good_gram).all())
        self.assertFalse(np.isfinite(bad_gram).all())
        self.assertTrue(np.isposinf(bad_gram[0, 0]))
        self.assertFalse(any("overflow" in msg for msg in good_warnings))
        self.assertTrue(any("overflow" in msg for msg in bad_warnings))

    def test_overflow_can_be_a_data_dependent_python_exception(self):
        good, bad = self._inputs()
        with np.errstate(over="raise"):
            self.assertTrue(np.isfinite(good.T @ good).all())
            with self.assertRaises(FloatingPointError):
                bad.T @ bad

    def test_draft_pca_refactor_finite_f64_norm_square_guard_is_insufficient(self):
        # Draft PR #3281 checks row_norm_sq = norm * norm in Python float,
        # but the actual data path still uses float32 matrix multiplication.
        norm = 1e21
        row_norm_sq = norm * norm
        self.assertTrue(math.isfinite(row_norm_sq))
        self.assertGreater(1e40, float(np.finfo(np.float32).max))


if __name__ == "__main__":
    unittest.main()
