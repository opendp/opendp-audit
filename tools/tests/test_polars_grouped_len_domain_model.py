"""Reference model of grouped Polars len() output-domain margins.

It models the two source branches at OpenDP ef1a2386. This does not
execute Rust or Polars. In particular, a failing output-domain implication
is a source-level witness, not a compiled-library regression run.
"""
from collections import Counter
from itertools import product
import unittest


def group_counts(rows):
    return Counter(key for key, _ in rows)


def output_margin(kind, original_max_groups):
    # make_expr_len constructs max_length=1, max_groups=Some(1).
    # make_expr_count preserves the input margin's max_groups.
    if kind == "len":
        return {"max_length": 1, "max_groups": 1}
    if kind == "count":
        return {"max_length": 1, "max_groups": original_max_groups}
    raise ValueError(kind)


def output_member(grouped_counts, margin):
    # The resulting aggregate has one row for each original group.
    # Margin::member's per-group length and total group-count checks.
    one_row_per_group = {key: 1 for key in grouped_counts}
    return (
        all(n <= margin["max_length"] for n in one_row_per_group.values())
        and (margin["max_groups"] is None
             or len(one_row_per_group) <= margin["max_groups"])
    )


class GroupedLenDomainModel(unittest.TestCase):
    def test_source_level_two_group_witness(self):
        rows = (("a", 5), ("b", 6))
        groups = group_counts(rows)
        self.assertEqual(groups, {"a": 1, "b": 1})
        self.assertFalse(output_member(groups, output_margin("len", None)))
        # The corresponding count constructor does not narrow max_groups.
        self.assertTrue(output_member(groups, output_margin("count", None)))

    def test_exhaustive_small_grouped_frames(self):
        alphabet = (("a", 10), ("b", 20), ("c", 30), ("d", 40))
        total, postcondition_failures = 0, 0
        for length in range(6):
            for rows in product(alphabet, repeat=length):
                total += 1
                groups = group_counts(rows)
                accepted = output_member(groups, output_margin("len", 4))
                if len(groups) > 1:
                    self.assertFalse(accepted)
                    postcondition_failures += 1
                else:
                    self.assertTrue(accepted)
                self.assertTrue(output_member(groups, output_margin("count", 4)))
        self.assertEqual(total, 1365)
        self.assertGreater(postcondition_failures, 1000)

    def test_select_without_grouping_remains_valid(self):
        # select([len()]) yields a single scalar result even on an empty frame.
        for length in range(0, 8):
            output_groups = 1
            self.assertLessEqual(output_groups, output_margin("len", None)["max_groups"])

    def test_corrected_grouped_margin(self):
        rows = (("a", 1), ("b", 2), ("c", 3))
        groups = group_counts(rows)
        original_max_groups = 4
        # Grouped aggregation should inherit the public original group bound.
        repaired = output_margin("count", original_max_groups)
        self.assertTrue(output_member(groups, repaired))
        self.assertEqual(repaired["max_length"], 1)
        self.assertEqual(repaired["max_groups"], original_max_groups)

    def test_groupwise_count_sensitivity_reference(self):
        # Finite checks of min(l1, l0 * linf) and
        # min(l1, sqrt(l0) * linf), for the count families.
        import math
        alphabet = (("a", None), ("a", 0), ("a", 1),
                    ("b", None), ("b", 0), ("b", 1))
        datasets = tuple(rows for n in range(4)
                         for rows in product(alphabet, repeat=n))
        self.assertEqual(len(datasets), 259)
        strategies = (
            lambda values: len(values),
            lambda values: sum(v is not None for v in values),
            lambda values: sum(v is None for v in values),
            lambda values: len(set(values)),
        )
        tests = 0
        for left in datasets:
            for right in datasets:
                per_group_distances = []
                for key in ("a", "b"):
                    lvals = tuple(v for g, v in left if g == key)
                    rvals = tuple(v for g, v in right if g == key)
                    lc, rc = Counter(lvals), Counter(rvals)
                    per_group_distances.append(sum(abs(lc[v] - rc[v])
                                                   for v in lc.keys() | rc.keys()))
                l0 = sum(d > 0 for d in per_group_distances)
                l1 = sum(per_group_distances)
                linf = max(per_group_distances)
                bound_l1 = min(l1, l0 * linf)
                bound_l2 = min(l1, math.sqrt(l0) * linf)
                for strategy in strategies:
                    diffs = []
                    for key in ("a", "b"):
                        lvals = tuple(v for g, v in left if g == key)
                        rvals = tuple(v for g, v in right if g == key)
                        diffs.append(abs(strategy(lvals) - strategy(rvals)))
                    self.assertLessEqual(sum(diffs), bound_l1)
                    self.assertLessEqual(math.hypot(*diffs), bound_l2 + 1e-12)
                    tests += 1
        self.assertEqual(tests, 4 * 259**2)


if __name__ == "__main__":
    unittest.main()
