"""Independent rational oracle for discrete Laplace's pure-DP privacy bound.

This tests arithmetic properties, not compiled OpenDP code or the sampler.
"""

import math
import random
import sys
import unittest
from fractions import Fraction


def ceil_f64(value: Fraction) -> float:
    """Least binary64 value not below nonnegative rational value."""
    if value < 0:
        raise ValueError("nonnegative rational required")
    try:
        nearest = float(value)
    except OverflowError:
        return math.inf
    if math.isinf(nearest):
        return math.inf
    if Fraction.from_float(nearest) < value:
        return math.nextafter(nearest, math.inf)
    return nearest


def laplace_loss(sensitivity: Fraction, scale: Fraction) -> float:
    """Rational model for the Laplace privacy-map branch rules."""
    if scale < 0 or sensitivity < 0:
        raise ValueError("negative distance or scale")
    if sensitivity == 0:
        return 0.0
    if scale == 0:
        return math.inf
    return ceil_f64(sensitivity / scale)


class TestLaplacePrivacyMapModel(unittest.TestCase):
    def test_zero_and_negative_boundaries(self):
        self.assertEqual(laplace_loss(Fraction(0), Fraction(0)), 0.0)
        self.assertEqual(laplace_loss(Fraction(0), Fraction(1)), 0.0)
        self.assertEqual(laplace_loss(Fraction(1), Fraction(0)), math.inf)
        for distance, scale in [(-1, 1), (1, -1), (0, -1)]:
            with self.subTest(distance=distance, scale=scale):
                with self.assertRaises(ValueError):
                    laplace_loss(Fraction(distance), Fraction(scale))

    def test_exact_and_upward_rounding(self):
        self.assertEqual(laplace_loss(Fraction(2), Fraction(1)), 2.0)
        self.assertEqual(laplace_loss(Fraction(1), Fraction(3)), math.nextafter(1 / 3, math.inf))
        self.assertEqual(laplace_loss(Fraction(1, 3), Fraction(1, 5)), 5 / 3)

    def test_very_small_and_large_loss(self):
        tiny = Fraction.from_float(math.ulp(0.0))
        large = Fraction.from_float(sys.float_info.max)
        self.assertEqual(laplace_loss(tiny, large), math.ulp(0.0))
        self.assertEqual(laplace_loss(Fraction(10**400), Fraction(1)), math.inf)

    def test_upward_enclosure_and_minimality(self):
        rng = random.Random(20261123)
        for _ in range(300):
            distance = Fraction(rng.randrange(1, 10000), rng.randrange(1, 10000))
            scale = Fraction(rng.randrange(1, 10000), rng.randrange(1, 10000))
            exact = distance / scale
            out = laplace_loss(distance, scale)
            self.assertGreaterEqual(Fraction.from_float(out), exact)
            previous = math.nextafter(out, -math.inf)
            self.assertLess(Fraction.from_float(previous), exact)


if __name__ == "__main__":
    unittest.main()
