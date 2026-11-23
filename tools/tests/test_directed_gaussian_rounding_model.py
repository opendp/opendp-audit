"""Independent binary64 upper-bound model for OpenDP's float Gaussian L2 allowance.

NOT compiled Rust. This verifies a mathematical reference implementation of
upward usize->f64 conversion followed by upward f64 square root, with exact
Fraction comparisons to the ideal real-valued bound.
"""
from fractions import Fraction
import math
import random
import unittest


def integer_to_binary64_up(n):
    """Reference upper f64 representation of a nonnegative integer."""
    value = float(n)
    if Fraction.from_float(value) < n:
        value = math.nextafter(value, math.inf)
    return value


def binary64_sqrt_up(value):
    """Reference binary64 ceiling of sqrt(value), using exact comparisons."""
    out = math.sqrt(value)
    if Fraction.from_float(out) ** 2 < Fraction.from_float(value):
        out = math.nextafter(out, math.inf)
    return out


def test_values():
    sizes = set(range(0, 5001))
    for exp in range(0, 65):
        power = 1 << exp
        for offset in (-127, -3, -2, -1, 0, 1, 2, 3, 127):
            n = power + offset
            if 0 <= n <= 2**64 - 1:
                sizes.add(n)
    for root in (1, 2, 3, 127, 65535, 65536, 2**26 - 1, 2**26, 2**32 - 1):
        for offset in (-2, -1, 0, 1, 2):
            n = root * root + offset
            if 0 <= n <= 2**64 - 1:
                sizes.add(n)
    rng = random.Random(20261122)
    for _ in range(4000):
        sizes.add(rng.randrange(2**64))
    return sorted(sizes)


class DirectedGaussianRoundingModelTests(unittest.TestCase):
    def test_upward_sqrt_multiplier_for_usize64(self):
        values = test_values()
        self.assertEqual(len(values), 9484)
        for n in values:
            upper_float = integer_to_binary64_up(n)
            sqrt_upper = binary64_sqrt_up(upper_float)
            self.assertGreaterEqual(Fraction.from_float(upper_float), n)
            self.assertGreaterEqual(Fraction.from_float(sqrt_upper) ** 2, n)
            self.assertTrue(math.isfinite(sqrt_upper))

    def test_nontrivial_integer_cast_boundaries(self):
        for n in (2**53, 2**53 + 1, 2**53 + 3,
                  2**63 - 1, 2**63 + 1, 2**64 - 1):
            upper = integer_to_binary64_up(n)
            self.assertGreaterEqual(Fraction.from_float(upper), n)
            if n != 2**53:
                self.assertGreater(Fraction.from_float(upper), n)

    def test_upward_sqrt_integer_vs_exact_square(self):
        for n in (0, 1, 2, 3, 6, 24, 2**53 + 1, 2**64 - 1):
            sqrt_upper = binary64_sqrt_up(integer_to_binary64_up(n))
            self.assertGreaterEqual(Fraction.from_float(sqrt_upper) ** 2, n)
            if n == 0:
                self.assertEqual(sqrt_upper, 0)


if __name__ == "__main__":
    unittest.main()
