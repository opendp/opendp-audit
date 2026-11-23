"""Independent small-grid model for OpenDP Gaussian float integerization.

This is NOT a compiled OpenDP test. Coordinates lie on a miniature dyadic
lattice, and quantization rounds half-integers toward positive infinity.
"""
from fractions import Fraction
from itertools import product
from math import sqrt, floor
import unittest


def quantize_index(lattice_index: int, grid_multiplier: int) -> int:
    """Round lattice_index/grid_multiplier; ties go toward +infinity."""
    t = grid_multiplier
    return (2 * lattice_index + t) // (2 * t)


def quantized_distance_units(a: int, b: int, t: int) -> int:
    return abs(quantize_index(a, t) - quantize_index(b, t)) * t


class FloatGaussianRoundingModelTests(unittest.TestCase):
    def test_ties_are_rounded_up_in_source_formula(self):
        # Source implementation and Rust upstream tests use ties upward.
        for value, expected in [(-5, -2), (-3, -1), (-1, 0),
                                (1, 1), (3, 2), (5, 3)]:
            self.assertEqual(quantize_index(value, 2), expected)

    def test_scalar_and_vector_l2_rounding_bound_on_small_grid(self):
        # All values are integer multiples of a miniature input lattice g.
        # The maximum per-coordinate expansion is at most (h-g), where h=t*g.
        # For n dimensions the bound is sqrt(n)*(h-g) by triangle inequality.
        counts = {}
        for n, m in ((1, 8), (2, 8), (3, 4)):
            for t in (1, 2, 4, 8):
                pairs = [((a - b) ** 2, quantized_distance_units(a, b, t) ** 2)
                         for a in range(-m, m + 1)
                         for b in range(-m, m + 1)]
                count = 0
                allowance = sqrt(n) * (t - 1)
                for coordinate_pairs in product(pairs, repeat=n):
                    original2 = sum(d2 for d2, _ in coordinate_pairs)
                    rounded2 = sum(d2 for _, d2 in coordinate_pairs)
                    self.assertLessEqual(sqrt(rounded2), sqrt(original2) + allowance + 1e-12)
                    count += 1
                counts[(n, t)] = count
        self.assertEqual(sum(counts.values()),
                         4 * (17 ** 2 + 17 ** 4 + 9 ** 6))

    def test_source_grid_index_formula_is_exact_for_dyadic_values(self):
        for k in range(-4, 5):
            grid = Fraction(2 ** k) if k >= 0 else Fraction(1, 2 ** -k)
            for raw in range(-40, 41):
                x = Fraction(raw, 16)
                expected = (2 * (x / grid).numerator + (x / grid).denominator) // (2 * (x / grid).denominator)
                # Source computes the same result using floor_div and bit shift.
                self.assertEqual(expected, floor((x / grid) + Fraction(1, 2)))


if __name__ == "__main__":
    unittest.main()
