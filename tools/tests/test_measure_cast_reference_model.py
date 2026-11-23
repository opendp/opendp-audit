"""Independent finite-distribution models of OpenDP privacy measure casts.

Does NOT execute Rust or certify the floating-point directed arithmetic
backend. Assumes full-support distributions and valid source guarantees.
"""
from itertools import combinations
import math
import unittest


def finite_laws():
    for d in (8, 16):
        if d == 8:
            for a in range(1, d):
                for b in range(1, d - a):
                    yield (a / d, b / d, (d - a - b) / d)
        else:
            for a in range(1, d):
                yield (a / d, (d - a) / d)


def max_symmetric_pure_epsilon(p, q):
    return max(
        max(math.log(a / b), math.log(b / a))
        for a, b in zip(p, q)
    )


def renyi_divergence(p, q, alpha):
    terms = [
        alpha * math.log(a) + (1 - alpha) * math.log(b)
        for a, b in zip(p, q)
    ]
    peak = max(terms)
    return (peak + math.log(sum(math.exp(t - peak) for t in terms))) / (
        alpha - 1
    )


def optimal_symmetric_delta(p, q, epsilon):
    multiplier = math.exp(epsilon)
    return max(
        sum(max(0.0, a - multiplier * b) for a, b in zip(x, y))
        for x, y in ((p, q), (q, p))
    )


class MeasureCastModelTests(unittest.TestCase):
    def test_puredp_to_zcdp_model(self):
        laws = list(finite_laws())
        self.assertEqual(len(laws), 36)
        checked = 0
        for p in laws:
            for q in laws:
                if len(p) != len(q):
                    continue
                epsilon = max_symmetric_pure_epsilon(p, q)
                rho = epsilon ** 2 / 2
                for order in (1.5, 2.0, 3.0, 5.0, 10.0):
                    self.assertLessEqual(
                        renyi_divergence(p, q, order),
                        order * rho + 1e-11,
                        (p, q, order),
                    )
                    checked += 1
        self.assertEqual(checked, 3330)

    def test_fixed_approxdp_to_profile_model(self):
        laws = list(finite_laws())
        checked = 0
        for p in laws:
            for q in laws:
                if len(p) != len(q):
                    continue
                for epsilon0 in (0.0, 0.1, 0.5, 1.0, 2.0):
                    fixed_delta = optimal_symmetric_delta(p, q, epsilon0)
                    for epsilon in (
                        0.0, 0.05, 0.1, 0.49, 0.5, 0.75, 1.0, 2.0, 3.0,
                    ):
                        claimed = fixed_delta if epsilon >= epsilon0 else 1.0
                        actual = optimal_symmetric_delta(p, q, epsilon)
                        self.assertLessEqual(
                            actual, claimed + 1e-11,
                            (p, q, epsilon0, epsilon, claimed, actual),
                        )
                        checked += 1
        self.assertEqual(checked, 29970)

    def test_profile_step_boundary(self):
        fixed_epsilon, fixed_delta = 0.5, 0.25
        curve = lambda epsilon: fixed_delta if epsilon >= fixed_epsilon else 1.0
        self.assertEqual(curve(math.nextafter(fixed_epsilon, 0.0)), 1.0)
        self.assertEqual(curve(fixed_epsilon), fixed_delta)
        self.assertEqual(curve(math.nextafter(fixed_epsilon, math.inf)), fixed_delta)


if __name__ == "__main__":
    unittest.main()
