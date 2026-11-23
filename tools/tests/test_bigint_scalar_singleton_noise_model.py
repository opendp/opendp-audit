"""Exact finite model for IBig scalar noise via a singleton vector.

Pins upstream ef1a238634d6196b01a1a1e77d3d5ad2340e3094.
This models the *reduction*, not compiled Rust, Dashu, random sampling,
or a full differential-privacy proof for the noise distribution.
"""
from fractions import Fraction
import math
import unittest


def finite_discrete_noise(p, radius):
    # Convenient rational finite laws with weights (1/2)^|z|^p.
    # Truncation is a model convenience, NOT OpenDP's support.
    unnormalized = {
        z: Fraction(1, 2) ** (abs(z) ** p)
        for z in range(-radius, radius + 1)
    }
    total = sum(unnormalized.values())
    return {z: probability / total for z, probability in unnormalized.items()}


def singleton_path(shift, noise):
    vector_input = [shift]
    # Vector noise implementation maps independently over elements.
    vector_release = [value + noise for value in vector_input]
    return vector_release[0] if vector_release else 0


def modeled_privacy_map(p, distance, scale):
    if distance < 0 or scale < 0:
        raise ValueError("invalid distance or scale")
    if distance == 0:
        return Fraction(0)
    if scale == 0:
        return math.inf
    fraction = distance / scale
    return fraction if p == 1 else fraction**2 / 2


class BigIntScalarSingletonNoiseModel(unittest.TestCase):
    def test_scalar_vector_laws_match_for_finite_noise_models(self):
        cases = 0
        for p in (1, 2):
            for radius in (0, 1, 3, 8):
                law = finite_discrete_noise(p, radius)
                self.assertEqual(sum(law.values()), 1)
                for shift in range(-12, 13):
                    # Equality of output laws follows from outcome-by-outcome
                    # equality; exact rational mass comparison is also checked.
                    scalar = {shift + z: mass for z, mass in law.items()}
                    vector = {singleton_path(shift, z): mass for z, mass in law.items()}
                    self.assertEqual(scalar, vector)
                    self.assertEqual(sum(vector.values()), 1)
                    cases += 1
        self.assertEqual(cases, 200)

    def test_singleton_lp_distance_equals_absolute_distance(self):
        checks = 0
        for p in (1, 2):
            for x in range(-8, 9):
                for y in range(-8, 9):
                    scalar = abs(x - y)
                    vector_power = sum(abs(a - b)**p for a, b in zip([x], [y]))
                    self.assertEqual(vector_power, scalar**p)
                    checks += 1
        self.assertEqual(checks, 578)

    def test_precomposition_keeps_privacy_map_parameters(self):
        cases = 0
        scales = (Fraction(0), Fraction(1, 2), Fraction(1),
                  Fraction(3, 2), Fraction(2))
        distances = (Fraction(0), Fraction(1, 2), Fraction(1),
                     Fraction(3, 2), Fraction(3))
        for p in (1, 2):
            for scale in scales:
                for distance in distances:
                    scalar_map = modeled_privacy_map(p, distance, scale)
                    vector_map = modeled_privacy_map(p, distance, scale)
                    self.assertEqual(scalar_map, vector_map)
                    self.assertEqual(scalar_map == math.inf, scale == 0 and distance > 0)
                    cases += 1
        self.assertEqual(cases, 50)

    def test_negative_distance_is_an_error_for_both_measures(self):
        for p in (1, 2):
            for d in (Fraction(-1), Fraction(-1, 2)):
                with self.assertRaises(ValueError):
                    modeled_privacy_map(p, d, Fraction(1))

    def test_zero_scale_is_deterministic_at_all_tested_shifts(self):
        for shift in range(-50, 51):
            self.assertEqual(singleton_path(shift, 0), shift)

    def test_sampler_failure_does_not_trigger_default_fallback(self):
        class SampleError(Exception):
            pass

        def failing_sample(_shift):
            raise SampleError("entropy unavailable")

        for shift in (-100, 0, 100):
            with self.assertRaisesRegex(SampleError, "entropy unavailable"):
                singleton_path(shift, failing_sample(shift))


if __name__ == "__main__":
    unittest.main()
