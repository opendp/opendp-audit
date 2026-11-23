"""Independent reference model of SklearnFit row alignment at OpenDP main.

Pinned upstream: a010591f55b1713c926f8e355091471634480307.
This tests the Python source's membership control flow, not native FFI.
"""
import unittest
from dataclasses import dataclass


@dataclass
class Fit:
    X: object
    y: object = None


class ArrayLike:
    def __init__(self, rows, columns=2):
        self.shape = (rows, columns)


class VectorLike:
    def __init__(self, rows):
        self.rows = rows

    def __len__(self):
        return self.rows


def source_n_rows(value):
    shape = getattr(value, "shape", None)
    return int(shape[0]) if shape else len(value)


def source_member(value, X_domain, y_domain):
    if not isinstance(value, Fit):
        return False
    if not X_domain(value.X):
        return False
    if (y_domain is None) != (value.y is None):
        return False
    if y_domain is not None:
        if not y_domain(value.y):
            return False
        if source_n_rows(value.X) != source_n_rows(value.y):
            return False
    return True


def valid_X(value):
    return isinstance(value, ArrayLike)


def valid_y(value):
    return isinstance(value, VectorLike)


class TestSklearnFitAlignmentModel(unittest.TestCase):
    def test_exhaustive_length_combinations(self):
        pairs = 0
        for x_rows in range(9):
            for y_rows in range(9):
                fit = Fit(ArrayLike(x_rows), VectorLike(y_rows))
                self.assertEqual(
                    source_member(fit, valid_X, valid_y), x_rows == y_rows
                )
                pairs += 1
        self.assertEqual(pairs, 81)

    def test_optional_target_contract(self):
        x = ArrayLike(3)
        self.assertTrue(source_member(Fit(x), valid_X, None))
        self.assertFalse(source_member(Fit(x, VectorLike(3)), valid_X, None))
        self.assertFalse(source_member(Fit(x), valid_X, valid_y))

    def test_invalid_carriers_fail_without_row_check(self):
        self.assertFalse(source_member(None, valid_X, valid_y))
        self.assertFalse(source_member(Fit(VectorLike(3), VectorLike(3)), valid_X, valid_y))
        self.assertFalse(source_member(Fit(ArrayLike(3), 3), valid_X, valid_y))

    def test_shape_first_and_len_fallback(self):
        self.assertEqual(source_n_rows(ArrayLike(0)), 0)
        self.assertEqual(source_n_rows(ArrayLike(15)), 15)
        self.assertEqual(source_n_rows(VectorLike(0)), 0)
        self.assertEqual(source_n_rows(VectorLike(15)), 15)

    def test_rejected_alignment_does_not_rely_on_domain_fixed_sizes(self):
        self.assertFalse(
            source_member(Fit(ArrayLike(4), VectorLike(3)), valid_X, valid_y)
        )

    def test_model_exposes_unsupported_scalar_target_exception(self):
        # A custom y-domain may admit scalars, but _n_rows requires sized rows.
        # This is outside the documented row-aligned supported carrier contract.
        with self.assertRaises(TypeError):
            source_member(Fit(ArrayLike(1), 42), valid_X, lambda _: True)


if __name__ == "__main__":
    unittest.main()
