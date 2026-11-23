"""Reference checks for Polars private cast dtype/nullability preconditions.

This module does not invoke OpenDP or Polars. It models the integer-range
containment rule and public allowlist classifications in OpenDP's cast.rs.
"""

import random
import unittest


INTEGER_BOUNDS = {
    "UInt32": (0, 2**32 - 1),
    "UInt64": (0, 2**64 - 1),
    "Int8": (-2**7, 2**7 - 1),
    "Int16": (-2**15, 2**15 - 1),
    "Int32": (-2**31, 2**31 - 1),
    "Int64": (-2**63, 2**63 - 1),
}
SMALL_UNSIGNED = ("UInt8", "UInt16")
PRIMITIVE_NUMERIC = set(INTEGER_BOUNDS) | set(SMALL_UNSIGNED) | {"Float32", "Float64"}
NUMERIC = PRIMITIVE_NUMERIC | {"Boolean"}
SAFE_IDENTITY = NUMERIC | {"String", "Date", "Datetime", "Time", "Categorical", "Enum"}


def integer_widening(from_dtype, to_dtype):
    if from_dtype not in INTEGER_BOUNDS or to_dtype not in INTEGER_BOUNDS:
        return False
    low_in, high_in = INTEGER_BOUNDS[from_dtype]
    low_out, high_out = INTEGER_BOUNDS[to_dtype]
    return low_out <= low_in and high_in <= high_out


def cast_allowed(from_dtype, to_dtype):
    if from_dtype == to_dtype:
        return from_dtype in SAFE_IDENTITY
    return (
        (from_dtype in NUMERIC and to_dtype in NUMERIC)
        or (from_dtype in NUMERIC and to_dtype == "String")
        or (from_dtype == "String" and to_dtype in PRIMITIVE_NUMERIC)
        or (from_dtype == "Categorical" and to_dtype in {"String", "Enum"})
        or (from_dtype == "Enum" and to_dtype == "String")
        or (from_dtype == "String" and to_dtype == "Enum")
    )


def null_preserving(from_dtype, to_dtype):
    return (
        from_dtype == to_dtype
        or integer_widening(from_dtype, to_dtype)
        or (from_dtype in {"Categorical", "Enum"} and to_dtype == "String")
        or (from_dtype, to_dtype) in {
            ("Float32", "Float64"),
            ("Int8", "Float64"),
            ("Int16", "Float64"),
            ("Int32", "Float64"),
            ("Int64", "Float64"),
            ("UInt32", "Float64"),
            ("UInt64", "Float64"),
            ("Int8", "String"),
            ("Int16", "String"),
            ("Int32", "String"),
            ("Int64", "String"),
            ("UInt32", "String"),
            ("UInt64", "String"),
            ("Float32", "String"),
            ("Float64", "String"),
            ("Boolean", "String"),
        }
    )


class TestPolarsPrivateCastReference(unittest.TestCase):
    def test_integer_widening_is_range_containment(self):
        rng = random.Random(20261123)
        for from_dtype, (low, high) in INTEGER_BOUNDS.items():
            for to_dtype, (target_low, target_high) in INTEGER_BOUNDS.items():
                expected = target_low <= low and high <= target_high
                self.assertEqual(integer_widening(from_dtype, to_dtype), expected)
                if not expected:
                    continue
                samples = [low, high, 0] + [
                    rng.randint(low, high) for _ in range(50)
                ]
                for value in samples:
                    self.assertLessEqual(target_low, value)
                    self.assertLessEqual(value, target_high)

    def test_numeric_cast_allowlist_and_rejected_temporal(self):
        for from_dtype in NUMERIC:
            for to_dtype in NUMERIC:
                self.assertTrue(cast_allowed(from_dtype, to_dtype))
            self.assertTrue(cast_allowed(from_dtype, "String"))
        for to_dtype in PRIMITIVE_NUMERIC:
            self.assertTrue(cast_allowed("String", to_dtype))
        for pair in [
            ("String", "Datetime"),
            ("Date", "Datetime"),
            ("Datetime", "String"),
            ("Int32", "Date"),
            ("Categorical", "UInt32"),
            ("UInt64", "Enum"),
            ("String", "Categorical"),
            ("Array", "Array"),
            ("List", "List"),
            ("Null", "Null"),
        ]:
            self.assertFalse(cast_allowed(*pair), pair)

    def test_narrowing_and_unknown_small_unsigned_are_conservative(self):
        for source, target in [
            ("String", "Int32"),
            ("Int64", "Int32"),
            ("Float64", "Int64"),
            ("Boolean", "Int64"),
            ("UInt8", "UInt32"),
            ("UInt16", "UInt64"),
        ]:
            self.assertTrue(cast_allowed(source, target))
            self.assertFalse(null_preserving(source, target))

    def test_supported_nonnull_preserving_pair_examples(self):
        for source, target in [
            ("Int32", "Int64"),
            ("UInt32", "Int64"),
            ("UInt32", "UInt64"),
            ("Float32", "Float64"),
            ("UInt64", "Float64"),
            ("Int64", "String"),
            ("Float64", "String"),
            ("Categorical", "String"),
            ("Enum", "String"),
            ("Boolean", "Boolean"),
        ]:
            self.assertTrue(cast_allowed(source, target))
            self.assertTrue(null_preserving(source, target))


if __name__ == "__main__":
    unittest.main()
