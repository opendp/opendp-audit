"""Exact-integer model of OpenDP integer threshold postprocessing.

The model reproduces the pinned source stage ordering for nonzero entries:
native integer -> IBig, additive noise, strict signed threshold, saturating
cast to the original integer. Noise outcomes are deterministic. The test does
not execute Rust, Dashu, or an OpenDP mechanism.
"""
import unittest


def native_bounds(bits, signed):
    if signed:
        return -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    return 0, (1 << bits) - 1


def threshold_release(value, threshold, noise, bits, signed):
    lo, hi = native_bounds(bits, signed)
    if not (lo <= value <= hi and lo <= threshold <= hi):
        raise ValueError("source type value out of range")
    if value == 0:  # Core suppresses explicit zero keys before noise.
        return None
    noisy_ibig = value + noise
    keep = (noisy_ibig > threshold) if threshold >= 0 else (noisy_ibig < threshold)
    if not keep:
        return None
    return max(lo, min(hi, noisy_ibig))


class IntegerThresholdPostSaturationTests(unittest.TestCase):
    def test_unsigned_upper_boundary(self):
        for bits in (8, 16, 32, 64, 128):
            with self.subTest(bits=bits):
                _, hi = native_bounds(bits, signed=False)
                self.assertEqual(
                    threshold_release(hi, hi, +1, bits, signed=False), hi
                )

    def test_signed_positive_upper_boundary(self):
        for bits in (8, 16, 32, 64, 128):
            with self.subTest(bits=bits):
                _, hi = native_bounds(bits, signed=True)
                self.assertEqual(
                    threshold_release(hi, hi, +1, bits, signed=True), hi
                )

    def test_signed_negative_lower_boundary(self):
        for bits in (8, 16, 32, 64, 128):
            with self.subTest(bits=bits):
                lo, _ = native_bounds(bits, signed=True)
                self.assertEqual(
                    threshold_release(lo, lo, -1, bits, signed=True), lo
                )

    def test_in_range_strict_controls(self):
        for bits in (8, 16, 32, 64, 128):
            for signed in (False, True):
                self.assertEqual(
                    threshold_release(10, 10, +1, bits, signed), 11
                )
                self.assertIsNone(threshold_release(10, 10, 0, bits, signed))
            self.assertEqual(
                threshold_release(-10, -10, -1, bits, signed=True), -11
            )
            self.assertIsNone(threshold_release(-10, -10, 0, bits, signed=True))

    def test_explicit_zero_suppressed(self):
        for bits in (8, 16, 32, 64, 128):
            self.assertIsNone(threshold_release(0, 0, +1, bits, signed=False))
            self.assertIsNone(threshold_release(0, 0, -1, bits, signed=True))

    def test_public_boundary_parameters_valid(self):
        # Finite, nonzero native inputs and thresholds at both signed extremes.
        for bits in (8, 16, 32, 64, 128):
            lo, hi = native_bounds(bits, True)
            self.assertLess(lo, 0)
            self.assertGreater(hi, 0)
            self.assertEqual(hi - lo + 1, 1 << bits)


if __name__ == "__main__":
    unittest.main()
