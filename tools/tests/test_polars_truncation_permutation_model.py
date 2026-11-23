"""Independent finite model of Polars identifier-truncation matching.

NOT compiled OpenDP/Polars. Models the current source-recognized positional
enumeration and dense rank, and checks their unordered-id metric invariants.
"""
from itertools import permutations
import unittest

UINT32_MAX = (1 << 32) - 1


def positional_per_group(rows, limit):
    """Source-recognized int_range(0, len()).over([ID, group]) < limit."""
    seen = {}
    result = []
    for identifier, group, value in rows:
        key = (identifier, group)
        index = seen.get(key, 0)
        seen[key] = index + 1
        if index < limit:
            result.append((identifier, group, value))
    return tuple(result)


def positional_extra_field_dense_rank(rows, limit):
    """Illustrative rank on struct(hash(key), key, position) per identifier.

    A third position field is not in the grouping certificate returned by the
    current matcher when it recognizes a hash/key prefix. This is a model of
    the matcher shape; NOT actual Polars hash or rank execution.
    """
    positions = {}
    keyed = []
    for identifier, group, value in rows:
        pos = positions.get(identifier, 0)
        positions[identifier] = pos + 1
        keyed.append((identifier, group, value, pos))
    output = []
    for identifier, group, value, pos in keyed:
        candidates = sorted({(g, p) for i, g, _, p in keyed if i == identifier})
        dense_rank = candidates.index((group, pos)) + 1
        if dense_rank <= limit:
            output.append((identifier, group, value))
    return tuple(output)


def source_certificate_threshold(op, threshold):
    """Current matching: strict gives k; inclusive gives k+1; u32 checked."""
    if not 0 <= threshold <= UINT32_MAX:
        raise ValueError("threshold not representable as u32")
    correction = int(op in ("<=", ">="))
    if threshold + correction > UINT32_MAX:
        raise OverflowError("source InfAdd must reject overflow")
    return threshold + correction


def retained_count(n, op, k, one_based):
    index_range = range(1, n + 1) if one_based else range(n)
    if op in ("<", ">"):
        return sum(i < k for i in index_range)
    return sum(i <= k for i in index_range)


def matcher_conjunction(atoms):
    """AllHorizontal/And returns no certificate if any leaf is unrecognized."""
    if any(atom is None for atom in atoms):
        return None
    return [bound for atom in atoms for bound in atom]


class TruncationPermutationReferenceTests(unittest.TestCase):
    def test_ordinal_truncation_changes_release_under_row_permutation(self):
        values = (10, 20, 30)
        all_rows = [tuple((7, "a", v) for v in order)
                    for order in permutations(values)]
        for k in (1, 2):
            sums = {sum(v for _, _, v in positional_per_group(rows, k))
                    for rows in all_rows}
            self.assertGreater(len(sums), 1)
            for rows in all_rows:
                # Unordered ID adjacency sees precisely the same rows.
                self.assertEqual(sorted(rows), sorted(all_rows[0]))
                self.assertLessEqual(len(positional_per_group(rows, k)), k)

    def test_extra_rank_field_can_select_different_values_with_same_key(self):
        first = ((7, "a", 10), (7, "a", 20))
        second = tuple(reversed(first))
        self.assertEqual(sorted(first), sorted(second))
        self.assertEqual(positional_extra_field_dense_rank(first, 1), ((7, "a", 10),))
        self.assertEqual(positional_extra_field_dense_rank(second, 1), ((7, "a", 20),))
        # The matched certificate mentions only the key "a", not the
        # positional third rank field used to choose a record.
        self.assertEqual({g for _, g, _ in first}, {"a"})

    def test_source_strict_inclusive_threshold_bounds_never_understate_counts(self):
        checks = 0
        for n in range(0, 34):
            for threshold in range(0, 36):
                for op in ("<", "<=", ">", ">="):
                    bound = source_certificate_threshold(op, threshold)
                    for one_based in (False, True):
                        count = retained_count(n, op, threshold, one_based)
                        self.assertLessEqual(count, bound)
                        checks += 1
        self.assertEqual(checks, 34 * 36 * 4 * 2)
        self.assertEqual(source_certificate_threshold("<", UINT32_MAX), UINT32_MAX)
        with self.assertRaises(OverflowError):
            source_certificate_threshold("<=", UINT32_MAX)
        self.assertEqual(retained_count(10, "<", 5, True), 4)
        self.assertEqual(source_certificate_threshold("<", 5), 5)

    def test_conjunction_model_never_certifies_unmatched_branch(self):
        self.assertIsNone(matcher_conjunction([["per_group=2"], None]))
        self.assertIsNone(matcher_conjunction([None, ["num_groups=3"]]))
        self.assertEqual(matcher_conjunction([["per_group=2"], ["num_groups=3"]]),
                         ["per_group=2", "num_groups=3"])
        self.assertEqual(matcher_conjunction([[], []]), [])


if __name__ == "__main__":
    unittest.main()
