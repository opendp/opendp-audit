"""Source-level reference checks for OpenDP's make_noisy_max wrapper.

This is NOT compiled OpenDP/Rust, and does not test sampling distributions.
It models the k=1 wrapper, source-level size guard, and deterministic
zero-scale argmax tie behavior.
"""
from itertools import product
import math
import unittest


class FailedFunction(ValueError):
    pass


def domain_member(values, declared_size=None):
    return declared_size is None or len(values) == declared_size


def accepts_constructor(declared_size, scale):
    return (declared_size is None or declared_size >= 1) and (
        math.isfinite(scale) and math.copysign(1.0, scale) >= 0
    )


def top_k_one_zero_scale(scores, negate=False):
    # Primitive top-k with k=1 uses max_by_key, which picks the final tie.
    if not scores:
        return []
    sign = -1 if negate else 1
    maximum = max(sign * score for score in scores)
    return [max(i for i, x in enumerate(scores) if sign * x == maximum)]


def noisy_max_extract(indices):
    if not indices:
        raise FailedFunction('candidates set is empty')
    return indices[0]


def privacy_map_reference(d, scale, monotonic, measure):
    if d < 0:
        raise ValueError('InvalidDistance')
    if d == 0:
        return 0.0
    if scale == 0:
        return float('inf')
    drange = d if monotonic else 2 * d
    if measure == 'pure':
        return drange / scale
    if measure == 'zcdp':
        return ((drange / scale) ** 2) / 8
    raise ValueError('measure')


class NoisyMaxWrapperReferenceTests(unittest.TestCase):
    def test_empty_unsized_accepted_but_invocation_fails(self):
        self.assertTrue(domain_member([], None))
        self.assertTrue(accepts_constructor(None, 1.0))
        self.assertEqual(top_k_one_zero_scale([]), [])
        with self.assertRaisesRegex(FailedFunction, 'candidates set is empty'):
            noisy_max_extract(top_k_one_zero_scale([]))
        self.assertFalse(accepts_constructor(0, 1.0))
        self.assertTrue(accepts_constructor(1, 1.0))
        self.assertFalse(domain_member([], 1))

    def test_k_one_postprocess_and_zero_scale_exact_extrema(self):
        cases = 0
        for n in range(1, 7):
            for scores in product((0, 1, 2), repeat=n):
                for negate in (False, True):
                    indices = top_k_one_zero_scale(scores, negate)
                    self.assertEqual(len(indices), 1)
                    i = noisy_max_extract(indices)
                    self.assertGreaterEqual(i, 0)
                    self.assertLess(i, n)
                    expected_score = min(scores) if negate else max(scores)
                    self.assertEqual(scores[i], expected_score)
                    self.assertEqual(
                        i, max(j for j, v in enumerate(scores) if v == expected_score)
                    )
                    cases += 1
        self.assertEqual(cases, 2 * sum(3 ** n for n in range(1, 7)))

    def test_singleton_result_index_and_option_independence(self):
        for value in (-1, 0, 1, 1000):
            for negate in (False, True):
                self.assertEqual(noisy_max_extract(
                    top_k_one_zero_scale([value], negate)), 0)
                for scale in (0.0, 0.1, 1.0, 1e300):
                    self.assertTrue(accepts_constructor(None, scale))

    def test_scale_and_fixed_size_guards(self):
        for scale in (math.inf, -math.inf, math.nan, -1.0, -0.0):
            self.assertFalse(accepts_constructor(None, scale))
        for scale in (0.0, 0.5, 1e300):
            self.assertTrue(accepts_constructor(None, scale))
        for n in range(1, 7):
            self.assertTrue(accepts_constructor(n, 1.0))
            self.assertFalse(domain_member([], n))

    def test_privacy_map_equals_k_one_topk_map_on_regular_cases(self):
        checks = 0
        for d, scale, monotonic, measure in product(
            (0, 1, 2, 3), (0.0, 0.5, 1.0, 2.0),
            (False, True), ('pure', 'zcdp')
        ):
            observed = privacy_map_reference(d, scale, monotonic, measure)
            if d == 0:
                self.assertEqual(observed, 0.0)
            elif scale == 0.0:
                self.assertTrue(math.isinf(observed))
            else:
                drange = d * (1 if monotonic else 2)
                expected = drange / scale if measure == 'pure' else (
                    drange / scale) ** 2 / 8
                self.assertEqual(observed, expected)
            checks += 1
        self.assertEqual(checks, 64)
        with self.assertRaisesRegex(ValueError, 'InvalidDistance'):
            privacy_map_reference(-1, 1.0, False, 'pure')


if __name__ == '__main__':
    unittest.main()
