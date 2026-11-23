"""Finite reference model for non-deprecated identifier truncation bounds.

Reviewed upstream: opendp/opendp@ef1a238634d6196b01a1a1e77d3d5ad2340e3094.
Does NOT import or execute Polars/OpenDP. Rows are (identifier, group, payload).
This checks cardinality under one changed ID, NOT permutation invariance.
"""
from collections import Counter, defaultdict
from itertools import combinations_with_replacement
import unittest


def truncated(rows, max_groups, per_group, *, final_group_by):
    keys = defaultdict(set)
    for ident, group, _ in rows:
        keys[ident].add(group)
    ranked = {ident: set(sorted(groups)[:max_groups]) for ident, groups in keys.items()}
    seen = Counter()
    kept = []
    for ident, group, payload in rows:
        key = (ident, group)
        if group not in ranked[ident] or seen[key] >= per_group:
            continue
        seen[key] += 1
        kept.append((ident, group, payload))
    if final_group_by:
        return tuple(sorted({(ident, group) for ident, group, _ in kept}))
    return tuple(kept)


def contributed(output, ident, final_group_by):
    if final_group_by:
        groups = [group for user, group in output if user == ident]
    else:
        groups = [group for user, group, _ in output if user == ident]
    return Counter(groups)


def compute_bound(total_ids, group_id_limit, max_groups, per_group, final_group_by):
    # One differing ID: upstream per_group ID bound=1 and total_ids=1.
    # Final GroupBy(ID,g) yields at most one output row per ID/g tuple.
    row_limit = min(per_group, 1) if final_group_by else per_group
    num_groups = min(total_ids * max_groups, group_id_limit)
    return row_limit, num_groups


class TestIdentifierTruncationModel(unittest.TestCase):
    def test_combined_bounds_for_neighbors(self):
        alphabet = [(0, group, val) for group in range(3) for val in (0, 1)]
        data_sets = [()] + [
            rows for n in range(1, 5)
            for rows in combinations_with_replacement(alphabet, n)
        ]
        baselines = [(), ((1, 0, 0),), ((1, 1, 1), (1, 2, 0))]
        checked = 0
        for present in data_sets:
            for baseline in baselines:
                for k in range(5):
                    for l in range(4):
                        for final in (False, True):
                            a = truncated(present + baseline, k, l, final_group_by=final)
                            b = truncated(baseline, k, l, final_group_by=final)
                            # The unchanged ID must retain exactly the same rows.
                            self.assertEqual(
                                contributed(a, 1, final), contributed(b, 1, final)
                            )
                            contribution = contributed(a, 0, final)
                            row_bound, group_bound = compute_bound(1, 3, k, l, final)
                            self.assertLessEqual(
                                max(contribution.values(), default=0), row_bound
                            )
                            self.assertLessEqual(len(contribution), group_bound)
                            checked += 1
        self.assertEqual(checked, 3 * 210 * 5 * 4 * 2)

    def test_comparison_threshold_offset_is_conservative(self):
        # Enumeration is zero-indexed; dense ranks are one-indexed.
        # Source maps <t to t and <=t to t+1 (conservative, sometimes loose).
        for threshold in range(6):
            strict_bound = threshold
            inclusive_bound = threshold + 1
            enumeration = list(range(7))
            dense_ranks = list(range(1, 8))
            for values in (enumeration, dense_ranks):
                self.assertLessEqual(
                    sum(v < threshold for v in values), strict_bound
                )
                self.assertLessEqual(
                    sum(v <= threshold for v in values), inclusive_bound
                )

    def test_materialize_computed_grouping_key(self):
        # Prior upstream #3082 / merged PR #3087: stale A+B after aggregation
        # is a different key from materialized A and collapses groups.
        rows = [(7, 500 - 2 * j, j) for j in range(20)]
        before = [(ident, a + b, b) for ident, a, b in rows]
        self.assertEqual(len({group for _, group, _ in before}), 20)
        after_group_by = [
            (ident, computed_key, b) for ident, computed_key, b in before
        ]
        correctly_materialized = Counter(a for _, a, _ in after_group_by)
        stale_recomputed = Counter(a + b for _, a, b in after_group_by)
        self.assertEqual(max(correctly_materialized.values()), 1)
        self.assertEqual(max(stale_recomputed.values()), 20)


if __name__ == "__main__":
    unittest.main()
