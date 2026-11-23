"""Pinned-source witness for OpenDP floating search's finite probe horizon.

Models `impl_bands_float!`, `signed_band_search`, and the no-bounds
`exponential_bounds_search` dispatch in OpenDP ef1a238634d6196b01a1a1e77d3d5ad2340e3094.
No OpenDP binary is executed; this is a deterministic source-level model.
"""

import struct
import unittest


def cast_float(value, width):
    return struct.unpack("<f" if width == 4 else "<d", struct.pack("<f" if width == 4 else "<d", value))[0]


def pinned_bands(width, center=0., sign=1):
    """The same `size_of::<Self>()` and `2.powi(k*k)` loop as the pinned Rust source."""
    f = lambda value: cast_float(value, width)
    s = 1. if sign > 0 else -1.
    return [f(center), f(center + s * .5)] + [f(center + s * (2. ** (k * k))) for k in range(width)]


def pinned_band_search(predicate, width, sign):
    bands = pinned_bands(width, 0., sign)
    at_center = predicate(bands[0])
    for lower, upper in zip(bands, bands[1:]):
        if at_center != predicate(upper):
            return tuple(sorted((lower, upper)))
    return None


def pinned_infer_bounds(predicate, width):
    return pinned_band_search(predicate, width, 1) or pinned_band_search(predicate, width, -1)


class FloatBandHorizonModelTests(unittest.TestCase):
    def test_f32_search_cannot_infer_representable_1024_threshold(self):
        self.assertEqual(pinned_bands(4), [0., .5, 1., 2., 16., 512.])
        predicate = lambda x: x >= 1024.
        self.assertIsNone(pinned_infer_bounds(predicate, 4))
        self.assertFalse(predicate(0.))
        self.assertTrue(predicate(2048.))  # Explicit two-sided bounds succeed.

    def test_f64_search_cannot_infer_representable_2pow50_threshold(self):
        self.assertEqual(pinned_bands(8)[-1], 2. ** 49)
        predicate = lambda x: x >= 2. ** 50
        self.assertIsNone(pinned_infer_bounds(predicate, 8))
        self.assertFalse(predicate(0.))
        self.assertTrue(predicate(2. ** 51))  # Explicit two-sided bounds succeed.

    def test_one_sided_upper_bound_inference_has_same_limit(self):
        self.assertIsNone(pinned_band_search(lambda x: x >= 1024., 4, 1))
        self.assertIsNone(pinned_band_search(lambda x: x >= 2. ** 50, 8, 1))

    def test_negative_thresholds_are_symmetric(self):
        self.assertIsNone(pinned_infer_bounds(lambda x: x <= -1024., 4))
        self.assertIsNone(pinned_infer_bounds(lambda x: x <= -(2. ** 50), 8))

    def test_threshold_at_last_probe_is_bracketed(self):
        self.assertEqual(pinned_infer_bounds(lambda x: x >= 512., 4), (16., 512.))
        self.assertEqual(pinned_infer_bounds(lambda x: x >= 2. ** 49, 8), (2. ** 36, 2. ** 49))


if __name__ == "__main__":
    unittest.main()
