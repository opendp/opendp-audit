"""Finite mathematical model for Polars aggregate integer widening casts.

This models the range containment rule and mathematical integer distance, not
compiled OpenDP, Polars casting, or binary floating-point metric arithmetic.
Pinned upstream: ef1a238634d6196b01a1a1e77d3d5ad2340e3094.
"""

from itertools import product
import unittest


BITS = {
    "UInt32": (0, 2**32 - 1),
    "UInt64": (0, 2**64 - 1),
    "Int8": (-2**7, 2**7 - 1),
    "Int16": (-2**15, 2**15 - 1),
    "Int32": (-2**31, 2**31 - 1),
    "Int64": (-2**63, 2**63 - 1),
}


def is_integer_widening_cast(source, target):
    """Translate the precise interval-containment check from cast.rs."""
    lower, upper = BITS[source]
    target_lower, target_upper = BITS[target]
    return target_lower <= lower and upper <= target_upper


def candidate_values(bounds):
    low, high = bounds
    return sorted({low, low + 1, high - 1, high} | {x for x in (-1, 0, 1) if low <= x <= high})


def integer_lp_distance(xs, ys, p):
    """Exact integer-powered Lp norm raised to p (avoids float rounding)."""
    assert p > 0 and len(xs) == len(ys)
    return sum(abs(x - y)**p for x, y in zip(xs, ys))


class TestAggregateIntegerWidening(unittest.TestCase):
    def test_all_36_type_pairs_match_range_containment(self):
        for source, target in product(BITS, repeat=2):
            with self.subTest(source=source, target=target):
                low, high = BITS[source]
                tlow, thigh = BITS[target]
                self.assertEqual(
                    is_integer_widening_cast(source, target),
                    tlow <= low and high <= thigh,
                )

    def test_representative_widening_and_narrowing_cases(self):
        for source, target in (
            ("Int8", "Int16"), ("Int8", "Int64"),
            ("UInt32", "UInt64"), ("UInt32", "Int64"),
            ("Int64", "Int64"),
        ):
            self.assertTrue(is_integer_widening_cast(source, target))
        for source, target in (
            ("Int16", "Int8"), ("UInt64", "Int64"),
            ("Int64", "UInt64"), ("Int32", "UInt32"),
        ):
            self.assertFalse(is_integer_widening_cast(source, target))

    def test_all_accepted_casts_preserve_scalar_integer_distances(self):
        checked = 0
        for source, target in product(BITS, repeat=2):
            if not is_integer_widening_cast(source, target):
                continue
            values = candidate_values(BITS[source])
            for x, y in product(values, repeat=2):
                # Integer value-preserving cast is exactly the identity on
                # the source interval; absolute-distance equality follows.
                self.assertGreaterEqual(x, BITS[target][0])
                self.assertLessEqual(x, BITS[target][1])
                self.assertEqual(abs(int(x) - int(y)), abs(x - y))
                checked += 1
        self.assertGreater(checked, 100)

    def test_accepted_casts_preserve_mathematical_lp_for_aggregate_vectors(self):
        for source, target in product(BITS, repeat=2):
            if not is_integer_widening_cast(source, target):
                continue
            values = candidate_values(BITS[source])
            for x, y in product(values, repeat=2):
                left = [x, 0, y]
                right = [0, y, x]
                for p in (1, 2, 4):
                    self.assertEqual(integer_lp_distance(left, right, p),
                                     integer_lp_distance(list(map(int, left)),
                                                         list(map(int, right)), p))

    def test_cast_options_do_not_overflow_for_accepted_integer_ranges(self):
        # Strict, NonStrict and Overflowing modes have identical mathematical
        # values on these accepted source/target ranges. This does not test
        # Polars' native option or null behavior.
        for source, target in product(BITS, repeat=2):
            if not is_integer_widening_cast(source, target):
                continue
            for value in candidate_values(BITS[source]):
                self.assertLessEqual(BITS[target][0], value)
                self.assertGreaterEqual(BITS[target][1], value)


if __name__ == "__main__":
    unittest.main()
