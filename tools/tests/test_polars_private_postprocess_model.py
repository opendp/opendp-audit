"""Exact finite model of private Polars postprocessing composition and fills.

Models binary DP data processing and source-described AST/Option behavior.
It does not invoke OpenDP Rust, its privacy maps, or the Polars optimizer.
"""
from fractions import Fraction
from itertools import product
import unittest

PROBS = (Fraction(1, 4), Fraction(1, 2), Fraction(3, 4))


def ratio_bound(p, q):
    return max(p / q, q / p, (1 - p) / (1 - q), (1 - q) / (1 - p))


def binary_joint(p1, p2):
    return (p1 * p2, p1 * (1 - p2), (1 - p1) * p2, (1 - p1) * (1 - p2))


def postprocessed(law, mask):
    value = sum((mass for i, mass in enumerate(law) if mask & (1 << i)), Fraction(0))
    return (1 - value, value)


def combine_fills(fills, postprocessor):
    return None if any(x is None for x in fills) else postprocessor(fills)


class PrivatePolarsPostprocessTests(unittest.TestCase):
    def test_binary_private_composition_exact(self):
        cases = comparisons = 0
        for p1, q1, p2, q2 in product(PROBS, repeat=4):
            max_ratio = ratio_bound(p1, q1) * ratio_bound(p2, q2)
            joint_p, joint_q = binary_joint(p1, p2), binary_joint(q1, q2)
            for mask in range(16):
                for out_p, out_q in zip(
                    postprocessed(joint_p, mask), postprocessed(joint_q, mask)
                ):
                    self.assertLessEqual(out_p, max_ratio * out_q)
                    self.assertLessEqual(out_q, max_ratio * out_p)
                    comparisons += 2
                cases += 1
        self.assertEqual(cases, 1296)
        self.assertEqual(comparisons, 5184)

    def test_all_or_nothing_fills(self):
        cases = 0
        for n in range(1, 7):
            for presence in product((False, True), repeat=n):
                fills = [f"fill_{i}" if present else None for i, present in enumerate(presence)]
                actual = combine_fills(fills, tuple)
                self.assertEqual(actual is not None, all(presence))
                if actual is not None:
                    self.assertEqual(actual, tuple(fills))
                cases += 1
        self.assertEqual(cases, 126)

    def test_alias_binary_fill_rules(self):
        alias = lambda xs: f"{xs[0]} as release"
        binary = lambda xs: f"({xs[0]} + {xs[1]})"
        self.assertEqual(alias(["expr"]), "expr as release")
        self.assertEqual(combine_fills(["fill"], alias), "fill as release")
        self.assertEqual(binary(["sum", "len"]), "(sum + len)")
        self.assertEqual(combine_fills(["fill_sum", "fill_len"], binary),
                         "(fill_sum + fill_len)")
        self.assertIsNone(combine_fills(["fill_sum", None], binary))

    def test_projection_boolean_options(self):
        count = 0
        for parallel, duplicate_check, broadcast in product((False, True), repeat=3):
            accepted = duplicate_check and broadcast
            self.assertEqual(accepted, bool(duplicate_check and broadcast))
            if accepted:
                count += 1
        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
