"""Finite reference model for the metric-unbounded cast's u32 arithmetic.

Pinned upstream: opendp/opendp@ef1a238634d6196b01a1a1e77d3d5ad2340e3094.
This translates a single Rust expression and checks metric distances; it does
not execute Rust code and is not an end-to-end DP experiment.
"""

from itertools import product
from collections import Counter
import unittest

MAX_U32 = (1 << 32) - 1


def map_unchecked_u32(d_in):
    """Rust `StabilityMap::new(|d_in| d_in * 2)` with unchecked u32 math."""
    assert 0 <= d_in <= MAX_U32
    return (d_in * 2) & MAX_U32


def change_one_distance(a, b):
    assert len(a) == len(b)
    counter_a = Counter(a)
    counter_b = Counter(b)
    return sum((counter_a - counter_b).values())


def symmetric_distance(a, b):
    counter_a = Counter(a)
    counter_b = Counter(b)
    return sum((counter_a - counter_b).values()) + sum((counter_b - counter_a).values())


def hamming_distance(a, b):
    assert len(a) == len(b)
    return sum(x != y for x, y in zip(a, b))


def insert_delete_distance(a, b):
    """Shortest add/remove edit path, computed via longest common subsequence."""
    table = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i, x in enumerate(a, 1):
        for j, y in enumerate(b, 1):
            table[i][j] = table[i - 1][j - 1] + 1 if x == y else max(table[i - 1][j], table[i][j - 1])
    return len(a) + len(b) - 2 * table[len(a)][len(b)]


class TestMetricUnboundedCastOverflow(unittest.TestCase):
    def test_small_vectors_satisfy_correct_two_times_bound(self):
        for size in range(1, 5):
            datasets = tuple(product((0, 1), repeat=size))
            for left in datasets:
                for right in datasets:
                    self.assertLessEqual(symmetric_distance(left, right), 2 * change_one_distance(left, right))
                    self.assertLessEqual(insert_delete_distance(left, right), 2 * hamming_distance(left, right))

    def test_boundary_unchecked_u32_wraps_to_zero(self):
        self.assertEqual(map_unchecked_u32((1 << 31) - 1), MAX_U32 - 1)
        self.assertEqual(map_unchecked_u32(1 << 31), 0)
        self.assertEqual(map_unchecked_u32((1 << 31) + 1), 2)
        self.assertEqual(map_unchecked_u32(MAX_U32), MAX_U32 - 1)

    def test_size_one_real_neighbor_violates_both_advertised_metric_maps(self):
        a, b = (0,), (1,)
        advertised = map_unchecked_u32(1 << 31)
        self.assertEqual(change_one_distance(a, b), 1)
        self.assertEqual(hamming_distance(a, b), 1)
        self.assertEqual(symmetric_distance(a, b), 2)
        self.assertEqual(insert_delete_distance(a, b), 2)
        self.assertLessEqual(change_one_distance(a, b), 1 << 31)
        self.assertLessEqual(hamming_distance(a, b), 1 << 31)
        self.assertGreater(symmetric_distance(a, b), advertised)
        self.assertGreater(insert_delete_distance(a, b), advertised)

    def test_checked_multiply_would_reject_unrepresentable_range(self):
        # In checked Rust arithmetic this boundary is an overflow/panic;
        # a fallible map should return Err instead of panicking or wrapping.
        self.assertTrue(((1 << 31) - 1) <= MAX_U32 // 2)
        self.assertFalse((1 << 31) <= MAX_U32 // 2)


if __name__ == "__main__":
    unittest.main()
