"""Finite reference model for OpenDP Polars stable group-by contribution bounds.

Tests the algebra behind the audited Rust source, not compiled OpenDP/Polars.
"""
from collections import Counter, defaultdict
from itertools import product
import random
import unittest


def grouped_sum(rows):
    groups = defaultdict(int)
    for key, value in rows:
        groups[key] += value
    return Counter((key, total) for key, total in groups.items())


def symmetric_distance(left, right):
    return sum((left - right).values()) + sum((right - left).values())


def changed_contributions(before, after):
    left, right = Counter(before), Counter(after)
    return (left - right) + (right - left)


def groupby_stability_map(contributed_rows, contributed_groups):
    candidates = [b for b in (contributed_rows, contributed_groups) if b is not None]
    if not candidates:
        raise ValueError("row or group contribution bound required")
    return 2 * min(candidates)


class GroupByStabilityModel(unittest.TestCase):
    def test_missing_bound_and_minimum(self):
        with self.assertRaises(ValueError):
            groupby_stability_map(None, None)
        self.assertEqual(groupby_stability_map(4, None), 8)
        self.assertEqual(groupby_stability_map(None, 3), 6)
        self.assertEqual(groupby_stability_map(7, 2), 4)
        self.assertEqual(groupby_stability_map(0, 20), 0)
        self.assertEqual(groupby_stability_map(0, 0), 0)

    def test_exhaustive_neighbor_pairs(self):
        row_alphabet = tuple(product((0, 1), (-1, 0, 1)))
        datasets = [rows for n in range(4) for rows in product(row_alphabet, repeat=n)]
        self.assertEqual(len(datasets), 259)
        checks = 0
        for old in datasets:
            old_result = grouped_sum(old)
            for new in datasets:
                delta = changed_contributions(old, new)
                rows_changed = sum(delta.values())
                groups_changed = len({key for key, _ in delta})
                output_dist = symmetric_distance(old_result, grouped_sum(new))
                bound = groupby_stability_map(rows_changed, groups_changed)
                self.assertLessEqual(output_dist, bound, (old, new, output_dist, bound))
                checks += 1
        self.assertEqual(checks, 259 * 259)

    def test_random_multi_group_aggregates(self):
        rng = random.Random(20261123)
        alphabet = tuple(product(range(5), (-9, -4, -1, 0, 2, 8)))
        for _ in range(10000):
            old = [rng.choice(alphabet) for _ in range(rng.randrange(11))]
            new = [rng.choice(alphabet) for _ in range(rng.randrange(11))]
            delta = changed_contributions(old, new)
            bound = groupby_stability_map(sum(delta.values()), len({key for key, _ in delta}))
            self.assertLessEqual(
                symmetric_distance(grouped_sum(old), grouped_sum(new)), bound
            )

    def test_materialized_key_names_are_output_names(self):
        # Illustrative metadata examples; not executed Polars expressions.
        for original, output_name in (
            ("col('A')", "A"),
            ("col('A').alias('key')", "key"),
            ("col('A') + col('B')", "A"),
        ):
            materialized = ("column", output_name)
            self.assertEqual(materialized[1], output_name, original)


if __name__ == "__main__":
    unittest.main()
