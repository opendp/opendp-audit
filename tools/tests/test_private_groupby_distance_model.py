"""Finite reference model for private Polars grouped distance normalization.

Pinned source: opendp/opendp@ef1a238634d6196b01a1a1e77d3d5ad2340e3094,
rust/src/measurements/make_private_lazyframe/group_by/mod.rs.
This is NOT a native OpenDP/Polars test. It assumes valid grouping keys and
public margin certificates; it does not test privacy mechanisms or noise tails.
"""
from collections import Counter
from fractions import Fraction
from itertools import combinations_with_replacement
import unittest

MAX_U32 = (1 << 32) - 1


def checked_product(a, b):
    result = a * b
    if result > MAX_U32:
        raise OverflowError("checked u32 bound overflow")
    return result


def min_optional(a, b):
    vals = [v for v in (a, b) if v is not None]
    return min(vals) if vals else None


def normalize(b0, b1, bi, max_groups=None, max_length=None, invariant=False):
    """Faithful finite-u32 model of group_by privacy_map's triple normalization.

    b0/b1/bi are existing certified input Bounds over grouping keys / total.
    max_groups/max_length are independently certified public domain margins.
    """
    if max_groups is not None:
        max_changed_groups = max_groups if invariant else checked_product(max_groups, 2)
    else:
        max_changed_groups = None
    max_group_change = (checked_product(max_length, 2)
                        if max_length is not None else None)
    l0 = min_optional(b0, max_changed_groups)
    li = min_optional(bi, max_group_change)
    l1 = b1
    if l1 is not None:
        l0 = l1 if l0 is None else l0
        li = l1 if li is None else li
    elif l0 is not None and li is not None:
        l1 = checked_product(l0, li)
    else:
        raise ValueError("insufficient bound certificates")
    l0 = min(l0, l1)
    li = min(li, l1)
    l1 = min(l1, checked_product(l0, li))
    return l0, l1, li


def exact_group_distance(left, right):
    """Symmetric differences of multisets of (group, distinguishable value)."""
    a, b = Counter(left), Counter(right)
    group_distances = [sum(abs(a[(key, val)] - b[(key, val)])
                           for val in range(2)) for key in range(3)]
    return (sum(bool(d) for d in group_distances),
            sum(group_distances), max(group_distances, default=0))


def public_caps(left, right):
    distinct_left = {key for key, _ in left}
    distinct_right = {key for key, _ in right}
    groups = max(len(distinct_left), len(distinct_right))
    length = max((sum(1 for key, _ in rows if key == group)
                  for rows in (left, right) for group in range(3)), default=0)
    return groups, length, distinct_left == distinct_right


class GroupByBoundsReferenceTests(unittest.TestCase):
    def test_all_small_multisets_and_certificate_combinations(self):
        alphabet = [(group, value) for group in range(3) for value in range(2)]
        data = [()] + [rows for n in range(1, 4)
                        for rows in combinations_with_replacement(alphabet, n)]
        self.assertEqual(len(data), 84)
        examined = 0
        for left in data:
            for right in data:
                actual0, actual1, actuali = exact_group_distance(left, right)
                group_cap, row_cap, same_keys = public_caps(left, right)
                for v in range(8):
                    invariant = same_keys and v % 2 == 0
                    b0 = actual0 + (v % 2) if v % 3 else None
                    b1 = actual1 + (v % 3) if v % 4 else None
                    bi = actuali + ((v // 2) % 2) if v % 5 else None
                    g = group_cap if v % 2 == 0 else None
                    k = row_cap if v % 3 != 1 else None
                    bound0, bound1, boundi = normalize(b0, b1, bi, g, k, invariant)
                    self.assertGreaterEqual(bound0, actual0)
                    self.assertGreaterEqual(bound1, actual1)
                    self.assertGreaterEqual(boundi, actuali)
                    # Bounds need only dominate the *true* distance.
                    # The ordered tightening steps can leave a loose l0/linf
                    # after tightening l1, without invalidating its guarantee.
                    examined += 1
        self.assertEqual(examined, 84 * 84 * 8)

    def test_missing_certificates_fail_closed(self):
        with self.assertRaises(ValueError):
            normalize(None, None, None)
        with self.assertRaises(ValueError):
            normalize(1, None, None)
        with self.assertRaises(ValueError):
            normalize(None, None, 1)
        self.assertEqual(normalize(None, 7, None), (7, 7, 7))
        self.assertEqual(normalize(2, None, 3), (2, 6, 3))

    def test_checked_overflow_rejects_uncertifiable_bounds(self):
        with self.assertRaises(OverflowError):
            normalize(1, 1, 1, max_groups=1 << 31, invariant=False)
        with self.assertRaises(OverflowError):
            normalize(1, 1, 1, max_length=1 << 31)
        with self.assertRaises(OverflowError):
            normalize(1 << 16, None, 1 << 16)
        with self.assertRaises(OverflowError):
            normalize(1 << 16, MAX_U32, 1 << 16)

    def test_threshold_gap_and_joint_failure_probability(self):
        p = Fraction(1, 7)  # an upper bound on each unstable key release
        checked = 0
        for li in range(6):
            for threshold in range(9):
                if threshold <= li:
                    self.assertFalse(threshold > li)
                    continue  # source rejects this threshold in privacy_map
                for l0 in range(7):
                    joint = 1 - (1 - p) ** l0
                    self.assertGreaterEqual(joint, 0)
                    self.assertLessEqual(joint, min(1, l0 * p))
                    self.assertEqual(threshold - li > 0, True)
                    checked += 1
        self.assertEqual(checked, sum(8 - li for li in range(6)) * 7)


if __name__ == "__main__":
    unittest.main()
