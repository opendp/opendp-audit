"""Standalone model checks for a bounded OpenDP source audit.

These checks are not compiled OpenDP regressions. Their purpose is to preserve
reproducible arithmetic witnesses and the exact-rational sensitivity model.
"""
from fractions import Fraction
import math
import random
import struct
import unittest


def outward_float(value):
    result = float(value)
    if Fraction.from_float(result) < value:
        result = math.nextafter(result, math.inf)
    return result


def ulp_allowance(lower, upper, constant):
    magnitude = max(abs(lower), upper)
    product = Fraction.from_float(magnitude) * Fraction.from_float(abs(constant))
    rounded = outward_float(product)
    raw_exponent = (struct.unpack(">Q", struct.pack(">d", rounded))[0] >> 52) & 2047
    # 2^-1075 is not representable; the upward binary64 value is 2^-1074.
    if raw_exponent == 0:
        return math.ldexp(1.0, -1074)
    return math.ldexp(1.0, raw_exponent - 1023 - 52)


class LipschitzMulModelTest(unittest.TestCase):
    def test_inverted_interval_is_deferred(self):
        lower, upper, constant = 2.0, 1.0, 1.0
        self.assertEqual(max(abs(lower), upper), 2.0)
        self.assertEqual(ulp_allowance(lower, upper, constant), 2**-51)
        # total_clamp starts by checking this, but the constructor does not.
        self.assertGreater(lower, upper)

    def test_subnormal_allowance_rounds_up(self):
        self.assertEqual(ulp_allowance(0.0, 5e-324, 0.5), 5e-324)

    def test_exact_rational_bound_for_valid_intervals(self):
        rng = random.Random(20261122)
        cases = [
            (-10.0, 10.0, 0.3), (0.0, 100.0, -2.3),
            (-4.0, -1.0, 0.7), (-1.0, 2.0, 3.0),
            (0.0, 1.0, 1.5), (-1e-300, 1e-300, 0.6),
            (-1e-320, 1e-320, 0.5), (0.0, 5e-324, 0.5),
            (-5e-324, 0.0, 2.0), (-2.0, 2.0, 0.0),
            (-100.0, 1.0, -0.01),
        ]
        checks = 0
        for lower, upper, constant in cases:
            self.assertLessEqual(lower, upper)
            allowance = Fraction.from_float(ulp_allowance(lower, upper, constant))
            for _ in range(2000):
                sample = lambda: max(lower, min(upper, lower + (upper - lower) * rng.random()))
                x, y = sample(), sample()
                gx, gy = x * constant, y * constant
                lhs = abs(Fraction.from_float(gx) - Fraction.from_float(gy))
                rhs = (abs(Fraction.from_float(x) - Fraction.from_float(y))
                       * Fraction.from_float(abs(constant)) + allowance)
                self.assertLessEqual(lhs, rhs)
                checks += 1
        self.assertEqual(checks, 22000)


if __name__ == "__main__":
    unittest.main()
