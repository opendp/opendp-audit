"""Independent stopping-law and finite privacy checks for a pinned OpenDP audit.

No compiled Rust/OpenDP code is invoked. The tests model the documented
geometric sampler law and the idealized candidate-selection output law.
"""
from fractions import Fraction
import math
import unittest


def passed_sampler_rate(requested):
    return -1.0 / math.log1p(-requested)


def effective_stop_probability(requested):
    if requested == 0:
        return 0.0
    return -math.expm1(-passed_sampler_rate(requested))


def selection_output_law(base, stop):
    """Two qualifying outcomes and one failure; stop only after a failure."""
    qualify = base[0] + base[1]
    denominator = stop + (1 - stop) * qualify
    if not denominator:
        return None  # no qualifying outcome and no stopping => nontermination
    return (
        base[0] / denominator,
        base[1] / denominator,
        stop * base[2] / denominator,
    )


def multiplicative_gap(p, q):
    return max(max(a / b, b / a) for a, b in zip(p, q) if a and b)


class SelectPrivateCandidateModelTests(unittest.TestCase):
    def test_mismatched_stopping_rates(self):
        for requested, predicted in (
            (0.1, 0.9999244881968662),
            (0.5, 0.7637099116554773),
            (0.9, 0.3522785148581993),
        ):
            actual = effective_stop_probability(requested)
            self.assertAlmostEqual(actual, predicted, delta=1e-12)
            self.assertGreater(abs(actual - requested), 0.1)

    def test_never_qualifying_without_stopping_does_not_terminate(self):
        always_fails = (Fraction(0), Fraction(0), Fraction(1))
        self.assertIsNone(selection_output_law(always_fails, Fraction(0)))
        self.assertEqual(
            selection_output_law(always_fails, Fraction(1, 2)),
            (Fraction(0), Fraction(0), Fraction(1)),
        )

    def test_factor_two_dp_bound_in_finite_output_model(self):
        bases = [
            (Fraction(a, 12), Fraction(b, 12), Fraction(12 - a - b, 12))
            for a in range(1, 11)
            for b in range(1, 12 - a)
        ]
        self.assertEqual(len(bases), 55)
        comparisons = 0
        for stop in (
            Fraction(0), Fraction(1, 100), Fraction(1, 10),
            Fraction(1, 2), Fraction(9, 10),
        ):
            for left in bases:
                for right in bases:
                    allowed = multiplicative_gap(left, right) ** 2
                    outcome_left = selection_output_law(left, stop)
                    outcome_right = selection_output_law(right, stop)
                    self.assertLessEqual(
                        multiplicative_gap(outcome_left, outcome_right),
                        allowed, (stop, left, right),
                    )
                    comparisons += 1
        self.assertEqual(comparisons, 15125)


if __name__ == "__main__":
    unittest.main()
