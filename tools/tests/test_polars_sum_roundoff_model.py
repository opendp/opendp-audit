"""Exact-rational reference model for stable Polars sum arithmetic.

Tests the mathematical error and overflow bounds in the pinned OpenDP source.
Does not call OpenDP, Rust Polars, or Polars' runtime aggregation kernel.
"""
from fractions import Fraction
import math
import random
import struct
import sys
import unittest


FLOATS = {
    "f32": {
        "unit_roundoff": Fraction(1, 2**24),
        "max_finite": struct.unpack(">f", bytes.fromhex("7f7fffff"))[0],
    },
    "f64": {
        "unit_roundoff": Fraction(1, 2**53),
        "max_finite": sys.float_info.max,
    },
}
INTS = {
    "u32": (0, 2**32 - 1),
    "u64": (0, 2**64 - 1),
    "i32": (-(2**31), 2**31 - 1),
    "i64": (-(2**63), 2**63 - 1),
}


def quantize(value, kind):
    if kind == "f32":
        return struct.unpack(">f", struct.pack(">f", value))[0]
    return float(value)


def magnitude_bound(length, low, high, kind):
    """Exact mathematical counterpart of sum_error/sum_relaxation."""
    if not (math.isfinite(low) and math.isfinite(high)) or low > high:
        raise ValueError("sum requires finite ordered bounds")
    magnitude = max(abs(low), abs(high))
    if length <= 1 or magnitude == 0:
        return Fraction(0), Fraction(0)
    u = FLOATS[kind]["unit_roundoff"]
    hu = (length - 1) * u
    if hu >= 1:
        raise ValueError("depth * unit roundoff must be < 1")
    error = hu / (1 - hu) * length * Fraction.from_float(magnitude)
    maximum = Fraction.from_float(FLOATS[kind]["max_finite"])
    if length * Fraction.from_float(magnitude) + error > maximum:
        raise OverflowError("potential intermediate sum overflow")
    return error, 2 * error


def sum_strategy(values, kind, strategy):
    if strategy == "left":
        accum = 0.0
        for x in values:
            accum = quantize(accum + x, kind)
        return accum
    if strategy == "right":
        accum = 0.0
        for x in reversed(values):
            accum = quantize(accum + x, kind)
        return accum
    pending = list(values)
    if not pending:
        return 0.0
    while len(pending) > 1:
        merged = []
        for i in range(0, len(pending), 2):
            merged.append(
                quantize(pending[i] + pending[i + 1], kind)
                if i + 1 < len(pending) else pending[i]
            )
        pending = merged
    return pending[0]


def integer_sum_size_limit(lower, upper, min_val, max_val):
    """Counterpart of exact arbitrary-precision size_limit logic."""
    limit = 2**64 - 1  # Rust usize::MAX on the 64-bit CI target
    if upper > 0:
        limit = min(limit, max_val // upper)
    if lower < 0:
        limit = min(limit, min_val // lower)
    return limit


class TestPolarsSumRoundoffModel(unittest.TestCase):
    def test_bound_on_rounded_arbitrary_association(self):
        rng = random.Random(20261123)
        for kind in FLOATS:
            for length in (2, 3, 4, 7, 16, 64):
                for bound in (1.0, 1024.0):
                    error, relax = magnitude_bound(length, -bound, bound, kind)
                    self.assertEqual(relax, 2 * error)
                    for _ in range(20):
                        values = [
                            quantize(rng.uniform(-bound, bound), kind)
                            for _ in range(length)
                        ]
                        exact = sum(map(Fraction.from_float, values), Fraction(0))
                        for strategy in ("left", "right", "tree"):
                            observed = sum_strategy(values, kind, strategy)
                            self.assertLessEqual(
                                abs(Fraction.from_float(observed) - exact),
                                error,
                                (kind, length, bound, strategy, values),
                            )

    def test_same_multiset_can_change_sum_at_zero_distance(self):
        a = [1e16, 1.0, -1e16]
        b = [1e16, -1e16, 1.0]
        self.assertEqual(sorted(a), sorted(b))
        self.assertEqual(sum_strategy(a, "f64", "left"), 0.0)
        self.assertEqual(sum_strategy(b, "f64", "left"), 1.0)
        _, relaxation = magnitude_bound(3, -1e16, 1e16, "f64")
        self.assertGreaterEqual(relaxation, Fraction(1))

    def test_overflow_and_depth_rejections(self):
        for kind in FLOATS:
            maximum = FLOATS[kind]["max_finite"]
            self.assertEqual(
                magnitude_bound(1, -maximum, maximum, kind),
                (Fraction(0), Fraction(0)),
            )
            with self.assertRaises(OverflowError):
                magnitude_bound(2, -maximum, maximum, kind)
            for bad in ((float("nan"), 1), (0, float("inf")), (2, -1)):
                with self.assertRaises(ValueError):
                    magnitude_bound(3, *bad, kind)
        with self.assertRaises(ValueError):
            magnitude_bound(2**24 + 1, -1.0, 1.0, "f32")

    def test_integer_intermediate_overflow_limit(self):
        for dtype, (lower_repr, upper_repr) in INTS.items():
            for lower, upper in (
                (lower_repr, upper_repr),
                (-1 if lower_repr < 0 else 0, 1),
                (0, 0),
            ):
                limit = integer_sum_size_limit(
                    lower, upper, lower_repr, upper_repr
                )
                self.assertGreaterEqual(limit, 1)
                for n in (0, 1, min(10, limit), limit):
                    self.assertGreaterEqual(n * lower, lower_repr)
                    self.assertLessEqual(n * upper, upper_repr)
                if limit < 100_000:
                    self.assertTrue(
                        (limit + 1) * lower < lower_repr
                        or (limit + 1) * upper > upper_repr
                    )


if __name__ == "__main__":
    unittest.main()
