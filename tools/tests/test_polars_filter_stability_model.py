"""Independent model of row-local frame/aggregation filtering in OpenDP.

This is NOT a compiled Rust/Polars test. It checks the mathematical
non-expansiveness of deterministic predicates applied to each record.
"""
from collections import Counter
from itertools import product
import unittest


ROWS = ((0, "a"), (1, "a"), (2, "b"), (3, "b"))
PREDICATES = (
    lambda r: True,
    lambda r: False,
    lambda r: r[0] >= 2,
    lambda r: r[0] % 2 == 0,
    lambda r: r[1] == "a",
    lambda r: r[0] in (1, 2),
)


def row_multiset_distance(left, right):
    first, second = Counter(left), Counter(right)
    return sum(abs(first[row] - second[row]) for row in ROWS)


def filter_rows(records, predicate):
    return tuple(row for row in records if predicate(row))


def groupwise_distances(left, right):
    """Per-key row multiset distance, including absent groups as empty."""
    keys = set(row[1] for row in left + right)
    return {
        key: row_multiset_distance(
            tuple(row for row in left if row[1] == key),
            tuple(row for row in right if row[1] == key),
        )
        for key in keys
    }


def grouped_expression_filter(records, predicate):
    """Apply a filter inside each existing group, retaining empty groups."""
    keys = set(row[1] for row in records)
    return {
        key: tuple(row[0] for row in records if row[1] == key and predicate(row))
        for key in keys
    }


class PolarsFilterStabilityModel(unittest.TestCase):
    def test_frame_filter_is_nonexpansive_on_all_small_multisets(self):
        datasets = [rows for n in range(5) for rows in product(ROWS, repeat=n)]
        self.assertEqual(len(datasets), 341)
        comparisons = 0
        for predicate in PREDICATES:
            filtered = [filter_rows(rows, predicate) for rows in datasets]
            for i, left in enumerate(datasets):
                for j, right in enumerate(datasets):
                    self.assertLessEqual(
                        row_multiset_distance(filtered[i], filtered[j]),
                        row_multiset_distance(left, right),
                    )
                    comparisons += 1
        self.assertEqual(comparisons, 6 * 341**2)

    def test_groupwise_l0_l1_linf_metrics_are_nonexpansive(self):
        datasets = [rows for n in range(4) for rows in product(ROWS, repeat=n)]
        self.assertEqual(len(datasets), 85)
        comparisons = 0
        for predicate in PREDICATES:
            filtered = [filter_rows(rows, predicate) for rows in datasets]
            for i, left in enumerate(datasets):
                for j, right in enumerate(datasets):
                    before = groupwise_distances(left, right)
                    after = groupwise_distances(filtered[i], filtered[j])
                    for key, distance in after.items():
                        self.assertLessEqual(distance, before[key])
                    for norm in (
                        lambda d: sum(v != 0 for v in d.values()),
                        lambda d: sum(d.values()),
                        lambda d: max(d.values(), default=0),
                    ):
                        self.assertLessEqual(norm(after), norm(before))
                    comparisons += 1
        self.assertEqual(comparisons, 6 * 85**2)

    def test_frame_filter_can_destroy_length_and_key_invariants(self):
        records = ((0, "a"), (1, "a"), (2, "b"))
        surviving = filter_rows(records, lambda r: r[0] == 2)
        self.assertNotEqual(len(surviving), len(records))
        self.assertEqual({r[1] for r in surviving}, {"b"})
        self.assertEqual({r[1] for r in records}, {"a", "b"})

    def test_aggregation_filter_preserves_partition_keys_not_lengths(self):
        records = ((0, "a"), (1, "a"), (2, "b"))
        aggregate = grouped_expression_filter(records, lambda r: r[0] > 1)
        self.assertEqual(set(aggregate), {"a", "b"})
        self.assertEqual(aggregate["a"], ())
        self.assertEqual(aggregate["b"], (2,))
        self.assertNotEqual(len(aggregate["a"]), 2)


if __name__ == "__main__":
    unittest.main()
