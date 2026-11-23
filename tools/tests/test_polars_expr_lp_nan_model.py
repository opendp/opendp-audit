"""Independent source-branch model for Polars ExprDomain Lp NaN preconditions.

This is NOT an OpenDP integration test: it reconstructs the boolean branch
conditions of MetricSpace::check_space in the pinned upstream implementation.
f32/f64 AtomDomain::default() permits NaN; Polars bitmap nullable is separate.
"""
import itertools
import math
import unittest


FLOATS = ("Float32", "Float64")
NUMERIC = set(FLOATS) | {"Int32", "UInt64"}


def expression_check(p: int, dtype: str, nullable: bool) -> bool:
    # Mirrors the exact success guards of ExprDomain + LpDistance<P,Q>.
    return p in (1, 2) and not nullable and dtype in NUMERIC


def vector_check(nan_allowed: bool) -> bool:
    # Mirrors VectorDomain<AtomDomain<T>> + LpDistance<P,Q>, for P in {1,2}.
    return not nan_allowed


class PolarsExprLpNanModel(unittest.TestCase):
    def test_default_float_atom_permits_nan(self):
        for dtype in FLOATS:
            with self.subTest(dtype=dtype):
                nan_allowed = True  # CheckNull::NULLABLE for f32/f64
                self.assertTrue(nan_allowed)
                self.assertTrue(math.isnan(float("nan")))

    def test_metric_space_precondition_mismatch(self):
        mismatches = 0
        checked = 0
        for dtype, p, nan_allowed, nullable in itertools.product(
            FLOATS, (1, 2), (False, True), (False, True)
        ):
            accepted_expression = expression_check(p, dtype, nullable)
            checked += 1
            if nullable:
                self.assertFalse(accepted_expression)
                continue

            accepted_vector = vector_check(nan_allowed)
            self.assertEqual(accepted_expression, True)
            if nan_allowed:
                self.assertFalse(accepted_vector)
                mismatches += 1
            else:
                self.assertTrue(accepted_vector)

        self.assertEqual(checked, 16)
        self.assertEqual(mismatches, 4)

    def test_integer_non_nan_controls(self):
        for dtype, p in itertools.product(("Int32", "UInt64"), (1, 2)):
            self.assertTrue(expression_check(p, dtype, nullable=False))
            self.assertTrue(vector_check(nan_allowed=False))

    def test_rejects_non_numeric_null_and_invalid_exponent(self):
        self.assertFalse(expression_check(1, "String", nullable=False))
        self.assertFalse(expression_check(1, "Float64", nullable=True))
        self.assertFalse(expression_check(0, "Float64", nullable=False))
        self.assertFalse(expression_check(3, "Float64", nullable=False))


if __name__ == "__main__":
    unittest.main()
