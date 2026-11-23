"""Standalone regression: sized int64 NumPy sums wrap despite bounded rows.

Pinned upstream OpenDP main: a010591f55b1713c926f8e355091471634480307.
Scope: python/src/opendp/extras/numpy/_make_np_sum/__init__.py.
This checks the NumPy computation and callback formula, not native OpenDP FFI.
"""
import unittest

try:
    import numpy as np
except ImportError:
    np = None


VALUE = 1 << 60
SIZE = 8


@unittest.skipIf(np is None, "numpy is an optional audit dependency")
class TestInt64SumModularOverflow(unittest.TestCase):
    def setUp(self):
        self.x = np.full((SIZE, 1), VALUE, dtype=np.int64)
        self.x_prime = self.x.copy()
        self.x_prime[0, 0] = 0

    def test_neighbours_are_inside_scaled_row_norm_bound(self):
        # Replicates _rows_within_norm for p=1, origin=0.
        for data in (self.x, self.x_prime):
            scale = np.max(np.abs(data), axis=1, keepdims=True, initial=0)
            scale = np.where(scale == 0, 1.0, scale)
            row_norm = np.linalg.norm(data / scale, ord=1, axis=1, keepdims=True)
            valid = np.isfinite(data).all(axis=1, keepdims=True) & (
                row_norm <= float(VALUE) / scale
            )
            self.assertTrue(valid.all())
        self.assertEqual(np.count_nonzero(self.x != self.x_prime), 1)

    def test_source_numpy_sum_wraps_and_keeps_int64_dtype(self):
        a = self.x.sum(axis=0)
        b = self.x_prime.sum(axis=0)
        self.assertEqual(a.dtype, np.dtype("int64"))
        self.assertEqual(b.dtype, np.dtype("int64"))
        self.assertEqual(int(a[0]), -(1 << 63))
        self.assertEqual(int(b[0]), 7 * VALUE)

    def test_actual_output_change_exceeds_formula_by_factor_7_5(self):
        a = int(self.x.sum(axis=0)[0])
        b = int(self.x_prime.sum(axis=0)[0])
        actual = abs(a - b)
        # d_in=2 for a fixed-size symmetric-distance replacement.
        d_in = 2
        norm = float(VALUE)  # array2_domain coerces integer norm to float.
        stability = lambda d: d // 2 * 2 * norm
        claimed = stability(d_in)
        self.assertIsInstance(claimed, float)
        self.assertEqual(claimed, 2 * VALUE)
        self.assertEqual(actual, 15 * VALUE)
        self.assertEqual(actual / claimed, 7.5)


if __name__ == "__main__":
    unittest.main()
