"""Independent CKS20 geometric/Laplace law model; does not execute OpenDP.

Pinned upstream: opendp/opendp@ef1a238634d6196b01a1a1e77d3d5ad2340e3094.
"""
import math
import unittest
from fractions import Fraction


def fast_geom_mass(x, k):
    """Evaluate the fast sampler's U-accept/V-geometric decomposition."""
    assert x > 0 and k >= 0
    n, d = x.numerator, x.denominator
    weights = [math.exp(-u / d) for u in range(d)]
    norm = sum(weights)
    return sum(
        (weights[z % d] / norm)
        * (1 - math.exp(-1))
        * math.exp(-(z // d))
        for z in range(k * n, (k + 1) * n)
    )


def signed_laplace_mass(scale, k):
    """Derive mass from the positive/negative sign and zero rejection."""
    q = math.exp(-1 / float(scale))
    accept = (1 + q) / 2
    return (0.5 * (1 - q) * q ** abs(k)) / accept


def rustdoc_coefficient(scale):
    q = math.exp(-1 / float(scale))
    return (q - 1) / (q + 1)


class TestCKS20LaplaceLaw(unittest.TestCase):
    def test_fast_geometric_positive_rational(self):
        for x in (Fraction(1, 2), Fraction(3, 4), Fraction(5, 3), Fraction(2)):
            with self.subTest(x=x):
                q = math.exp(-float(x))
                for k in range(8):
                    self.assertAlmostEqual(fast_geom_mass(x, k), (1 - q) * q**k, places=13)

    def test_laplace_mass_symmetric_normalized(self):
        for scale in (Fraction(1, 2), Fraction(1), Fraction(2), Fraction(3)):
            with self.subTest(scale=scale):
                q = math.exp(-1 / float(scale))
                p0 = (1 - q) / (1 + q)
                self.assertGreater(p0, 0)
                for k in range(-8, 9):
                    self.assertAlmostEqual(signed_laplace_mass(scale, k), p0 * q**abs(k), places=14)
                self.assertAlmostEqual(p0 * (1 + 2 * q / (1 - q)), 1, places=14)

    def test_rustdoc_sign_is_negative(self):
        for scale in (Fraction(1, 2), Fraction(1), Fraction(2), Fraction(3)):
            self.assertLess(rustdoc_coefficient(scale), 0)
            self.assertAlmostEqual(rustdoc_coefficient(scale), -signed_laplace_mass(scale, 0), places=14)

    def test_small_scale_limit_matches_zero_branch(self):
        # This verifies the positive-scale limit, not execution of Rust's zero branch.
        p0 = [signed_laplace_mass(Fraction(1, n), 0) for n in (2, 4, 8, 16, 32)]
        self.assertEqual(p0, sorted(p0))
        self.assertAlmostEqual(p0[-1], 1, places=12)


if __name__ == "__main__":
    unittest.main()
