"""Independent fixed-width and noise-law models for Polars DP mean auditing.

Does not execute compiled OpenDP, Polars, or Rust. The integer model mirrors
(lower + upper) / 2 under checked or wrapping arithmetic, then clipping.
The denominator model uses ideal symmetric two-sided geometric noise and
unsigned saturation, not a Monte Carlo simulation.
"""
import math
import random
import unittest


def integer_range(bits, signed):
    return (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)


def checked_midpoint(lower, upper, bits, signed):
    minimum, maximum = integer_range(bits, signed)
    total = lower + upper
    if not minimum <= total <= maximum:
        raise OverflowError("lower + upper is outside the integer type")
    return total // 2 if total >= 0 else -((-total) // 2)


def wrapped_midpoint(lower, upper, bits, signed):
    minimum, maximum = integer_range(bits, signed)
    mask = (1 << bits) - 1
    total = (lower + upper) & mask
    if signed and total > maximum:
        total -= 1 << bits
    return total // 2 if total >= 0 else -((-total) // 2)


def clip(value, lower, upper):
    return max(lower, min(value, upper))


def discrete_laplace_unsigned_bias(count, scale):
    """Excess mean from clamping count+Z at zero for ideal integer Laplace."""
    q = math.exp(-1.0 / scale)
    return q ** (count + 1) / (1.0 - q * q)


class PolarsDpMeanReferenceModel(unittest.TestCase):
    def test_checked_arithmetic_overflows_for_valid_integer_bounds(self):
        examples = (
            (8, True, 100, 120, 110, 100),
            (8, True, -120, -100, -110, -100),
            (32, False, 2**31, 2**31 + 2, 2**31 + 1, 2**31),
            (32, True, 2**30, 2**30 + 2, 2**30 + 1, 2**30),
            (64, True, (2**63 - 1) - 8, (2**63 - 1) - 2,
             (2**63 - 1) - 5, (2**63 - 1) - 8),
        )
        for bits, signed, lower, upper, ideal, observed in examples:
            with self.subTest(bits=bits, signed=signed, lower=lower):
                with self.assertRaises(OverflowError):
                    checked_midpoint(lower, upper, bits, signed)
                self.assertEqual((lower + upper) // 2, ideal)
                actual = clip(wrapped_midpoint(lower, upper, bits, signed), lower, upper)
                self.assertEqual(actual, observed)
                self.assertNotEqual(actual, ideal)

    def test_integer_midpoint_model_and_clip_range(self):
        rng = random.Random(20261122)
        checked = 0
        overflowed = 0
        for bits, signed in ((8, True), (16, True), (32, True),
                             (64, True), (32, False), (64, False)):
            minimum, maximum = integer_range(bits, signed)
            samples = [minimum, minimum + 1, minimum + 2, -1, 0, 1,
                       maximum - 2, maximum - 1, maximum]
            samples = [x for x in samples if minimum <= x <= maximum]
            pairs = [(a, b) for a in samples for b in samples if a <= b]
            for _ in range(1500):
                a = rng.randrange(minimum, maximum + 1)
                b = rng.randrange(minimum, maximum + 1)
                pairs.append((min(a, b), max(a, b)))
            for a, b in pairs:
                ideal = (a + b) // 2 if a + b >= 0 else -((-(a + b)) // 2)
                result = clip(wrapped_midpoint(a, b, bits, signed), a, b)
                self.assertLessEqual(a, result)
                self.assertLessEqual(result, b)
                try:
                    self.assertEqual(checked_midpoint(a, b, bits, signed), ideal)
                except OverflowError:
                    overflowed += 1
                else:
                    self.assertEqual(result, ideal)
                    checked += 1
        self.assertGreater(checked, 5000)
        self.assertGreater(overflowed, 1000)

    def test_omitted_signed_argument_defaults_to_false(self):
        # In current upstream match_shim<_, 3>, omitted arguments become lit(NULL).
        # lit.bool().unwrap_or(false) maps the third null argument to false.
        input_expressions = ["input", "scale"]
        args = input_expressions + [None] * (3 - len(input_expressions))
        self.assertEqual(args, ["input", "scale", None])
        signed = args[2] if isinstance(args[2], bool) else False
        self.assertFalse(signed)

    def test_unsigned_noise_has_positive_bias_near_zero(self):
        scale = 1.0
        q = math.exp(-1 / scale)
        norm = (1 - q) / (1 + q)
        for count in (0, 1, 2):
            expected_excess = discrete_laplace_unsigned_bias(count, scale)
            actual_excess = sum(
                (max(0, count + z) - count) * norm * q ** abs(z)
                for z in range(-90, 91)
            )
            self.assertAlmostEqual(actual_excess, expected_excess, delta=1e-12)
            self.assertGreater(expected_excess, 0.0)
        # Non-saturating signed ideal noise has zero mean.
        signed_noise_mean = sum(
            z * norm * q ** abs(z) for z in range(-90, 91)
        )
        self.assertAlmostEqual(signed_noise_mean, 0.0, delta=1e-12)


if __name__ == "__main__":
    unittest.main()
