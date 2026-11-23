"""Analytical reference checks for integer scalar Gaussian privacy.

Does not invoke compiled OpenDP. Uses a finite-support log-sum-exp model of
ideal discrete-Gaussian noise. Source assumptions are audited separately.
"""
import math
import unittest


def logsumexp(values):
    peak = max(values)
    return peak + math.log(sum(math.exp(x - peak) for x in values))


def log_pmf(mean, sigma):
    # Wide for means in [-2,2], sigma <=3, and Renyi order <=5.
    # This is NOT a verification of the exact infinite tail.
    logweights = [-0.5 * ((i - mean) / sigma) ** 2 for i in range(-80, 81)]
    normalizer = logsumexp(logweights)
    return [v - normalizer for v in logweights]


def renyi_divergence(logp, logq, alpha):
    return logsumexp([
        alpha * p + (1 - alpha) * q
        for p, q in zip(logp, logq)
    ]) / (alpha - 1)


def integer_saturation(value, lower=-128, upper=127):
    return min(upper, max(lower, value))


class GaussianScalarPrivacyModelTests(unittest.TestCase):
    def test_discrete_gaussian_zcdp_bound(self):
        checks = 0
        for sigma in (0.5, 1.0, 2.0, 3.0):
            laws = {mean: log_pmf(mean, sigma) for mean in range(-2, 3)}
            for mean1 in range(-2, 3):
                for mean2 in range(-2, 3):
                    for alpha in (2, 3, 5):
                        actual = renyi_divergence(
                            laws[mean1], laws[mean2], alpha
                        )
                        advertised = (
                            alpha * (mean1 - mean2) ** 2 / (2 * sigma ** 2)
                        )
                        self.assertLessEqual(
                            actual, advertised + 1e-9,
                            (sigma, mean1, mean2, alpha, actual, advertised),
                        )
                        checks += 1
        self.assertEqual(checks, 300)

    def test_saturating_integer_postprocessor_is_deterministic(self):
        values = (-500, -128, -127, -1, 0, 1, 127, 128, 500)
        for x in values:
            out = integer_saturation(x)
            self.assertGreaterEqual(out, -128)
            self.assertLessEqual(out, 127)
            for y in values:
                self.assertLessEqual(
                    abs(out - integer_saturation(y)), abs(x - y)
                )

    def test_reference_map_boundaries(self):
        def reference_map(distance, scale):
            if distance < 0:
                raise ValueError("negative sensitivity")
            if distance == 0:
                return 0
            if scale == 0:
                return math.inf
            if scale < 0:
                raise ValueError("negative scale")
            return (distance / scale) ** 2 / 2

        self.assertEqual(reference_map(0, 0), 0)
        self.assertEqual(reference_map(2, 0), math.inf)
        self.assertEqual(reference_map(3, 2), 1.125)
        with self.assertRaises(ValueError):
            reference_map(-1, 1)
        with self.assertRaises(ValueError):
            reference_map(1, -1)


if __name__ == "__main__":
    unittest.main()
