"""Independent mathematical model for OpenDP scalar-to-vector metric cast.

The model evaluates finite singleton Lp norms for positive integer p and
makes the distinct conventional L0 interpretation explicit. It does not
compile or execute OpenDP Rust.
"""

from fractions import Fraction
import math
import unittest


def lp_singleton(a, b, p):
    """Real-valued Lp norm of the one-element difference for p > 0."""
    if p <= 0:
        raise ValueError("ordinary Lp norm uses positive exponent")
    return abs(float(a - b) ** p) ** (1.0 / p)


def l0_singleton(a, b):
    """Count of nonzero coordinate differences, if one reinterprets p=0 as L0."""
    return int(a != b)


class TestScalarToVectorLpModel(unittest.TestCase):
    def test_singleton_norm_equals_absolute_distance_for_positive_p(self):
        vals = [Fraction(-2), Fraction(-1, 2), Fraction(0), Fraction(1, 2), Fraction(2)]
        for p in (1, 2, 3, 4, 8):
            for a in vals:
                for b in vals:
                    self.assertTrue(math.isclose(lp_singleton(a, b, p), float(abs(a - b)), rel_tol=1e-12, abs_tol=1e-12))

    def test_zero_exponent_is_outside_the_documented_norm_formula(self):
        with self.assertRaises(ValueError):
            lp_singleton(Fraction(0), Fraction(1, 2), 0)

    def test_zero_norm_convention_fails_identity_stability_for_small_gap(self):
        left, right = Fraction(0), Fraction(1, 2)
        input_absolute_distance = abs(left - right)
        output_l0_distance = l0_singleton(left, right)
        advertised_stability = input_absolute_distance
        self.assertEqual(output_l0_distance, 1)
        self.assertEqual(advertised_stability, Fraction(1, 2))
        self.assertGreater(output_l0_distance, advertised_stability)

    def test_default_index_postprocessing_boundary(self):
        # Representative outputs for the Rust get(i).cloned().unwrap_or_default()
        # postprocessor, with i=0 and integer default 0.
        examples = [((), 0), ((7,), 7), ((7, 8), 7)]
        for vec, expected in examples:
            actual = vec[0] if vec else 0
            self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
