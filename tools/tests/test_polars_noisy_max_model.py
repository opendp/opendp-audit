"""Independent finite probability model for OpenDP Polars noisy_max.

This models the positive-scale top-1 permute-and-flip and exponential
mechanism proposal laws from a pinned source revision. It does not execute
OpenDP Rust, Polars or random sampling.
"""
import itertools
import math
import unittest
from functools import lru_cache


@lru_cache(maxsize=None)
def single_row_law(scores, scale, negate, replacement):
    assert scores and scale > 0
    values = tuple(-x if negate else x for x in scores)
    maximum = max(values)
    weights = tuple(math.exp((v - maximum) / scale) for v in values)
    if replacement:
        total = sum(weights)
        probs = tuple(w / total for w in weights)
    else:
        n = len(values)
        probs = [0.0] * n
        for permutation in itertools.permutations(range(n)):
            reject = 1.0 / math.factorial(n)
            for i in permutation:
                probs[i] += reject * weights[i]
                reject *= 1.0 - weights[i]
        probs = tuple(probs)
    assert all(p >= 0 for p in probs)
    assert abs(sum(probs) - 1) <= 1e-13
    return probs


def max_divergence(p, q):
    return max(math.log(a / b) for a, b in zip(p, q))


def renyi_divergence(p, q, alpha):
    return math.log(sum(a**alpha / b**(alpha - 1) for a, b in zip(p, q))) / (alpha - 1)


class PolarsNoisyMaxPrivacyModel(unittest.TestCase):
    def test_groupwise_l0_composition_and_index_support(self):
        pure_checks = zcdp_checks = 0
        for n in (1, 2, 3, 4):
            vectors = tuple(itertools.product((-1, 0, 1), repeat=n))
            pairs = ((x, y) for x in vectors for y in vectors
                     if max(abs(a - b) for a, b in zip(x, y)) <= 1)
            for x, y in pairs:
                li = max(abs(a - b) for a, b in zip(x, y))
                for scale in (0.5, 1.0, 2.0):
                    for negate in (False, True):
                        for replacement in (False, True):
                            p = single_row_law(x, scale, negate, replacement)
                            q = single_row_law(y, scale, negate, replacement)
                            self.assertEqual(len(p), n)
                            self.assertEqual(len(q), n)
                            # LInfDistance::default() is non-monotonic; score
                            # range sensitivity is at most 2 * li.
                            eps = 2 * li / scale
                            for l0 in (1, 2):
                                if not replacement:
                                    self.assertLessEqual(
                                        l0 * max_divergence(p, q),
                                        l0 * eps + 1e-10,
                                    )
                                    pure_checks += 1
                                else:
                                    rho = eps**2 / 8
                                    for alpha in (1.1, 1.5, 2, 4, 8, 16):
                                        self.assertLessEqual(
                                            l0 * renyi_divergence(p, q, alpha),
                                            alpha * l0 * rho + 1e-10,
                                        )
                                        zcdp_checks += 1
        self.assertEqual(pure_checks, 33600)
        self.assertEqual(zcdp_checks, 201600)

    def test_two_changed_rows_joint_product_identity(self):
        for replacement in (False, True):
            for negate in (False, True):
                p = single_row_law((-1, 0, 1), 1.0, negate, replacement)
                q = single_row_law((0, 0, 1), 1.0, negate, replacement)
                joint_p = [a * b for a in p for b in p]
                joint_q = [a * b for a in q for b in q]
                self.assertEqual(len(joint_p), 9)
                if replacement:
                    for alpha in (1.5, 2, 4):
                        self.assertAlmostEqual(
                            renyi_divergence(joint_p, joint_q, alpha),
                            2 * renyi_divergence(p, q, alpha), delta=1e-12,
                        )
                else:
                    self.assertAlmostEqual(
                        max_divergence(joint_p, joint_q),
                        2 * max_divergence(p, q), delta=1e-12,
                    )

    def test_zero_scale_argmax_and_argmin(self):
        for scores in itertools.product((-1, 0, 1), repeat=4):
            for negate in (False, True):
                # Rust max_by_key selects the last maximizing index on a tie.
                values = [-x if negate else x for x in scores]
                selected = max(range(len(scores)), key=lambda i: (values[i], i))
                self.assertIn(selected, range(len(scores)))
                self.assertEqual(values[selected], max(values))


if __name__ == "__main__":
    unittest.main()
