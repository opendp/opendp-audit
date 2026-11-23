"""Reference model of privacy-free Polars literal and public-length expressions.

Does not execute native OpenDP/Rust/Polars. Models the documented
Invariant::Lengths premise and Expr::Literal single-expression contract.
"""
from collections import Counter
from itertools import product
import unittest


ALPHABET = tuple(product(('a', 'b'), (0, 1, 2)))


def keyed_lengths(rows):
    return Counter(key for key, _ in rows)


def public_len_privacy(invariant):
    """Model exact make_expr_private_len constructor's admission rule."""
    if invariant != 'Lengths':
        raise ValueError('partition lengths are not public')
    return 0


def public_lit_privacy():
    """A literal expression is independent of input contents."""
    return 0


def length_release(rows):
    return tuple(sorted(keyed_lengths(rows).items()))


def literal_aggregate(rows, value):
    """Model grouped literal values; the keys are supplied by outer grouping."""
    return tuple((key, value) for key in sorted(keyed_lengths(rows)))


class PrivacyFreeExprModelTests(unittest.TestCase):
    def test_exact_length_is_zero_only_given_length_invariant(self):
        self.assertEqual(public_len_privacy('Lengths'), 0)
        for invalid in (None, 'Keys', 'Unspecified'):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    public_len_privacy(invalid)

    def test_exhaustive_matching_public_group_lengths(self):
        datasets = tuple(rows for n in range(4)
                         for rows in product(ALPHABET, repeat=n))
        self.assertEqual(len(datasets), 259)
        eligible = 0
        ineligible = 0
        for left in datasets:
            for right in datasets:
                if keyed_lengths(left) == keyed_lengths(right):
                    self.assertEqual(length_release(left), length_release(right))
                    eligible += 1
                else:
                    ineligible += 1
        self.assertEqual(eligible, 15085)
        self.assertEqual(ineligible, 51996)
        self.assertEqual(eligible + ineligible, 259 ** 2)

    def test_public_literal_expression_value_is_data_independent(self):
        datasets = tuple(rows for n in range(4)
                         for rows in product(ALPHABET, repeat=n))
        values = (0, 17, -5, 'public')
        for literal in values:
            self.assertEqual(public_lit_privacy(), 0)
            for rows in datasets:
                self.assertTrue(all(v == literal for _, v in
                                    literal_aggregate(rows, literal)))
        # Crucial distinction: the overall grouped output additionally
        # carries group-key presence, not protected by a literal's zero map.
        first = (('a', 1),)
        second = (('b', 1),)
        self.assertNotEqual(literal_aggregate(first, 17),
                            literal_aggregate(second, 17))

    def test_len_without_grouping_and_empty_frame(self):
        # Ungrouped select([len()]) produces one scalar, including 0 on empty.
        for n in range(8):
            rows = tuple(('a', 0) for _ in range(n))
            self.assertEqual(len(rows), n)
        self.assertEqual(len(()), 0)
        # A grouped empty frame contains no group; these are different shapes.
        self.assertEqual(length_release(()), ())

    def test_group_keys_only_invariant_does_not_fix_lengths(self):
        left = (('a', 1), ('b', 1))
        right = (('a', 1), ('a', 2), ('b', 1))
        self.assertEqual(set(keyed_lengths(left)), set(keyed_lengths(right)))
        self.assertNotEqual(length_release(left), length_release(right))
        with self.assertRaises(ValueError):
            public_len_privacy('Keys')


if __name__ == '__main__':
    unittest.main()
