"""Source-equivalent NumPy regression for integer-origin membership rounding.

Pinned OpenDP main: a010591f55b1713c926f8e355091471634480307.
Scope: extras/numpy/array2_domain and _rows_within_norm, plus make_np_sum.
This does not execute OpenDP's native domain, privacy map, or noise sampler.
"""
import unittest

try:
    import numpy as np
except ImportError:
    np = None


ORIGIN_INTEGER = 1 << 60
RADIUS = 1.0


def _source_row_membership(x, origin, radius, p):
    """Match array2_domain's x-origin followed by _rows_within_norm."""
    centered = np.ascontiguousarray(x - origin)
    with np.errstate(all="ignore"):
        scale = np.max(np.abs(centered), axis=1, keepdims=True, initial=0.0)
        scale = np.where(scale == 0.0, 1.0, scale)
        row_norm = np.linalg.norm(centered / scale, ord=p, axis=1, keepdims=True)
        return np.isfinite(centered).all(axis=1, keepdims=True) & (
            row_norm <= radius / scale
        )


@unittest.skipIf(np is None, "NumPy is an optional audit dependency")
class TestIntegerOriginDomainMembership(unittest.TestCase):
    def setUp(self):
        # array2_domain casts the provided integer-origin ndarray to float64.
        origin_arg = np.array([ORIGIN_INTEGER], dtype=np.int64)
        self.origin = origin_arg.astype(float)
        self.x0 = np.array([[ORIGIN_INTEGER - 64]], dtype=np.int64)
        self.x1 = np.array([[ORIGIN_INTEGER + 128]], dtype=np.int64)

    def test_source_equivalent_membership_admits_both_invalid_rows(self):
        # Integer-to-float promotion discards both integer offsets.
        np.testing.assert_array_equal(self.x0 - self.origin, [[0.0]])
        np.testing.assert_array_equal(self.x1 - self.origin, [[0.0]])
        self.assertEqual(abs(int(self.x0[0, 0]) - ORIGIN_INTEGER), 64)
        self.assertEqual(abs(int(self.x1[0, 0]) - ORIGIN_INTEGER), 128)

        for p in (1, 2):
            for x in (self.x0, self.x1):
                self.assertTrue(_source_row_membership(x, self.origin, RADIUS, p).all())
                self.assertGreater(abs(int(x[0, 0]) - ORIGIN_INTEGER), RADIUS)

    def test_sized_sum_stability_underestimated_by_factor_96_without_overflow(self):
        self.assertEqual(self.x0.shape, (1, 1))
        self.assertEqual(self.x1.shape, (1, 1))
        self.assertEqual(self.x0.dtype, np.dtype("int64"))
        self.assertEqual(self.x1.dtype, np.dtype("int64"))
        # One row substitution is distance 2 under SymmetricDistance.
        self.assertEqual(np.count_nonzero(self.x0 != self.x1), 1)
        y0, y1 = self.x0.sum(axis=0), self.x1.sum(axis=0)
        self.assertEqual(y0.dtype, np.dtype("int64"))
        self.assertEqual(y1.dtype, np.dtype("int64"))
        self.assertEqual(int(y0[0]), ORIGIN_INTEGER - 64)
        self.assertEqual(int(y1[0]), ORIGIN_INTEGER + 128)
        actual = abs(int(y1[0]) - int(y0[0]))
        # Code in make_np_sum: d_in // 2 * 2 * norm for sized datasets.
        reported = (2 // 2) * 2 * RADIUS
        self.assertEqual(actual, 192)
        self.assertEqual(reported, 2.0)
        self.assertEqual(actual / reported, 96.0)

    def test_zero_radius_makes_the_mismatch_more_extreme(self):
        # array2_domain permits norm=0, and mixed subtraction still rounds to 0.
        for x in (self.x0, self.x1):
            self.assertTrue(_source_row_membership(x, self.origin, 0.0, 1).all())
        self.assertEqual((2 // 2) * 2 * 0.0, 0.0)
        self.assertEqual(
            int(self.x1.sum(axis=0)[0]) - int(self.x0.sum(axis=0)[0]), 192
        )

    def test_outside_the_float_ulp_is_rejected(self):
        far = np.array([[ORIGIN_INTEGER + 512]], dtype=np.int64)
        self.assertFalse(_source_row_membership(far, self.origin, RADIUS, 1).all())


if __name__ == "__main__":
    unittest.main()
