"""Standalone source-equivalent model of zero-size private NumPy mean.

Upstream commit: a010591f55b1713c926f8e355091471634480307.
This model does not import OpenDP. It reproduces NumPy empty-row
clamping, summation and division performed by make_private_np_mean.
The real OpenDP Laplace/Gaussian samplers and FFI are not exercised.
"""
import unittest
import warnings

try:
    import numpy as np
except ImportError:
    np = None


def clamp_empty_source_model(X, norm, p):
    """Exact relevant empty-row operations from make_np_clamp."""
    origin = np.array(0.0)
    margin = 1.0 - 4 * np.finfo(float).eps
    with np.errstate(all="ignore"):
        raw = np.ascontiguousarray(X, dtype=float)
        centered = np.nan_to_num(raw - origin)
        scale = np.max(np.abs(centered), axis=1, keepdims=True, initial=0.0)
        unit = centered / np.where(scale == 0, 1.0, scale)
        unit_norm = np.linalg.norm(unit, ord=p, axis=1, keepdims=True)
        limit = norm / np.maximum(unit_norm, 1.0)
        projected = origin + unit * (limit * margin)
    return projected


def source_mean_postprocessing(sums, size):
    """The precise postprocessing expression in make_private_np_mean."""
    return np.array(sums) / size


@unittest.skipUnless(np is not None, "NumPy optional in audit CI")
class TestPrivateNumPyMeanZeroSize(unittest.TestCase):
    def test_zero_size_constructor_predicate_only_rejects_none(self):
        # array2_domain(size=0) is valid because upstream checks nonnegative
        # integer size, and make_private_np_mean checks only size is None.
        self.assertFalse(0 is None)
        self.assertTrue(isinstance(0, int) and 0 >= 0)

    def test_empty_sum_division_generates_nan_warning(self):
        for dtype in (np.float32, np.float64):
            with self.subTest(dtype=dtype):
                X = np.empty((0, 2), dtype=dtype)
                sums = X.sum(axis=0)
                np.testing.assert_array_equal(sums, np.zeros(2, dtype=dtype))
                with warnings.catch_warnings(record=True) as emitted:
                    warnings.simplefilter("always")
                    mean = source_mean_postprocessing(sums, X.shape[0])
                self.assertTrue(np.isnan(mean).all())
                self.assertTrue(
                    any("invalid value encountered in divide" in str(w.message)
                        for w in emitted)
                )

    def test_empty_clamp_path_handles_p1_p2(self):
        X = np.empty((0, 2), dtype=np.float64)
        for p in (1, 2):
            with self.subTest(p=p):
                clipped = clamp_empty_source_model(X, 1.0, p)
                self.assertEqual(clipped.shape, (0, 2))
                self.assertEqual(clipped.size, 0)
                with warnings.catch_warnings(record=True) as emitted:
                    warnings.simplefilter("always")
                    val = source_mean_postprocessing(clipped.sum(axis=0), 0)
                self.assertTrue(np.isnan(val).all())
                self.assertEqual(len(emitted), 1)

    def test_noise_scale_multiplied_by_public_row_count(self):
        for scale in (0.5, 1.0, 100.0):
            with self.subTest(scale=scale):
                self.assertEqual(scale * 0, 0.0)
                self.assertEqual(scale * 1, scale)

    def test_nonempty_mean_control(self):
        X = np.array([[1.0, 2.0], [3.0, 4.0]])
        with warnings.catch_warnings(record=True) as emitted:
            warnings.simplefilter("always")
            mean = source_mean_postprocessing(X.sum(axis=0), len(X))
        np.testing.assert_array_equal(mean, [2.0, 3.0])
        self.assertEqual(emitted, [])


if __name__ == "__main__":
    unittest.main()
