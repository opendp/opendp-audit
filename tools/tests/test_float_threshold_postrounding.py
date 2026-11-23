"""Exact-arithmetic model of thresholding before float reconversion.

Reproduces the pinned OpenDP stage order, not its noise sampler, RBig cast,
or full Rust measurement. The positive-probability noise outcome Z=+1 is
chosen deterministically. Floating-point rounding is checked separately.
"""
from fractions import Fraction
import math
import struct
import unittest


def round_float(value: Fraction, bits: int) -> float:
    rounded64 = float(value)
    if bits == 64:
        return rounded64
    if bits == 32:
        return struct.unpack(">f", struct.pack(">f", rounded64))[0]
    raise ValueError(bits)


def thresholded_release(value: float, threshold: float, k: int, noise: int, bits: int):
    """Model exact quantization -> integer threshold -> nearest-float output."""
    grid = Fraction(2) ** k
    value_int = math.floor(Fraction.from_float(value) / grid + Fraction(1, 2))
    threshold_int = math.floor(Fraction.from_float(threshold) / grid)
    raw = value_int + noise
    if not raw > threshold_int:
        return None
    rational_release = raw * grid
    return rational_release, round_float(rational_release, bits)


class FloatThresholdPostRoundingTests(unittest.TestCase):
    def test_f64_minimal_witness(self):
        t, k = 1.0, -54
        result = thresholded_release(t, t, k, +1, 64)
        self.assertIsNotNone(result)
        ideal, output = result
        self.assertGreater(ideal, Fraction.from_float(t))
        self.assertEqual(output, t)
        self.assertEqual(Fraction.from_float(2.0**k) / Fraction(2)**k, 1)

    def test_f32_minimal_witness(self):
        t, k = 1.0, -26
        result = thresholded_release(t, t, k, +1, 32)
        self.assertIsNotNone(result)
        ideal, output = result
        self.assertGreater(ideal, Fraction.from_float(t))
        self.assertEqual(output, t)
        self.assertEqual(Fraction.from_float(2.0**k) / Fraction(2)**k, 1)

    def test_f64_integer_grid_witness(self):
        # Even k=0, scale=1 can lose +1 for a large public threshold.
        t = float(2**54)
        ideal, output = thresholded_release(t, t, 0, +1, 64)
        self.assertGreater(ideal, Fraction.from_float(t))
        self.assertEqual(output, t)

    def test_witness_family_at_binary_exponents(self):
        comparisons = 0
        for bits, exponents, k_offset in (
            (64, range(-200, 201), -54),
            (32, range(-60, 61), -26),
        ):
            for exponent in exponents:
                t = math.ldexp(1.0, exponent)
                k = exponent + k_offset
                ideal, output = thresholded_release(t, t, k, +1, bits)
                self.assertGreater(ideal, Fraction.from_float(t))
                self.assertEqual(output, t, (bits, exponent, k))
                comparisons += 1
        self.assertEqual(comparisons, 522)

    def test_sufficient_grid_increment_is_visible(self):
        ideal, output = thresholded_release(1.0, 1.0, -52, +1, 64)
        self.assertGreater(ideal, Fraction(1))
        self.assertEqual(output, math.nextafter(1.0, math.inf))
        ideal, output = thresholded_release(0.0, 0.0, -54, +1, 64)
        self.assertGreater(ideal, Fraction(0))
        self.assertGreater(output, 0.0)

    def test_laplace_increment_has_positive_probability(self):
        # With integerized Laplace scale 1, P[Z=1]=((1-a)/(1+a))*a.
        a = math.exp(-1.0)
        p = (1.0 - a) / (1.0 + a) * a
        self.assertGreater(p, 0.17)
        self.assertLess(p, 0.171)


if __name__ == "__main__":
    unittest.main()
