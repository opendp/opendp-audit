"""Independent arithmetic oracle for the Polars clip audit.

This does not execute OpenDP or Polars. It tests the mathematical row-wise
clamp and validation rules assumed by a stable public-bounds transformation.
"""

import math
import random
import unittest


def validated_bounds(lower, upper):
    if isinstance(lower, float) and math.isnan(lower):
        raise ValueError("lower cannot be NaN")
    if isinstance(upper, float) and math.isnan(upper):
        raise ValueError("upper cannot be NaN")
    if lower > upper:
        raise ValueError("lower must not exceed upper")
    return lower, upper


def clipped(value, lower, upper):
    validated_bounds(lower, upper)
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return math.nan
    return min(max(value, lower), upper)


class TestClipBoundContractModel(unittest.TestCase):
    def test_reject_invalid_bounds(self):
        for lower, upper in [
            (1, 0),
            (math.nan, 1.0),
            (0.0, math.nan),
            (math.nan, math.nan),
        ]:
            with self.subTest(lower=lower, upper=upper):
                with self.assertRaises(ValueError):
                    validated_bounds(lower, upper)

    def test_closed_interval_and_null_cases(self):
        for lower, upper in [(-2, 2), (0, 0), (-math.inf, 1.0), (-1.0, math.inf)]:
            with self.subTest(bounds=(lower, upper)):
                self.assertEqual(clipped(None, lower, upper), None)
                self.assertTrue(math.isnan(clipped(math.nan, lower, upper)))
                for x in [-math.inf, -3, -1, 0, 1, 3, math.inf]:
                    result = clipped(x, lower, upper)
                    self.assertGreaterEqual(result, lower)
                    self.assertLessEqual(result, upper)

    def test_integer_clamp_nonexpansive(self):
        rng = random.Random(20261123)
        for _ in range(300):
            lo, hi = sorted((rng.randint(-10**12, 10**12), rng.randint(-10**12, 10**12)))
            a, b = rng.randint(-10**12, 10**12), rng.randint(-10**12, 10**12)
            ca, cb = clipped(a, lo, hi), clipped(b, lo, hi)
            self.assertLessEqual(abs(ca - cb), abs(a - b))
            self.assertEqual(ca, clipped(ca, lo, hi))

    def test_finite_float_clamp_nonexpansive(self):
        rng = random.Random(9916)
        for _ in range(300):
            lo, hi = sorted((rng.uniform(-1000, 1000), rng.uniform(-1000, 1000)))
            a, b = rng.uniform(-2000, 2000), rng.uniform(-2000, 2000)
            ca, cb = clipped(a, lo, hi), clipped(b, lo, hi)
            self.assertLessEqual(abs(ca - cb), abs(a - b))
            self.assertEqual(ca, clipped(ca, lo, hi))


if __name__ == "__main__":
    unittest.main()
