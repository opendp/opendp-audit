"""Finite source-expression model for the Polars set-covering weight tie-break.

Pinned OpenDP: ef1a238634d6196b01a1a1e77d3d5ad2340e3094.
This models Rust's `-(*weight as i32)`; it does not execute OpenDP.
"""

from itertools import product
import unittest

U32_MAX = 2**32 - 1
I32_MAX = 2**31 - 1
I32_MIN = -(2**31)


def as_i32(weight):
    assert 0 <= weight <= U32_MAX
    return weight if weight <= I32_MAX else weight - 2**32


def source_weight_key(weight, *, checked=True):
    """Model the exact comparator term `-(*weight as i32)`."""
    value = as_i32(weight)
    if value == I32_MIN and checked:
        raise OverflowError("negation of i32::MIN in checked Rust")
    return as_i32((-value) & U32_MAX)


def source_covering(must_cover, sets, *, checked=True):
    """Model max_by_key ordering and remaining-cover removal."""
    uncovered = set(must_cover)
    chosen = []
    while uncovered:
        if not sets:
            return None
        best = max(
            sets,
            key=lambda entry: (
                len(entry[0] & uncovered),
                -len(entry[0]),
                source_weight_key(entry[1], checked=checked),
            ),
        )
        if best[0].isdisjoint(uncovered):
            return None
        uncovered.difference_update(best[0])
        chosen.append(best)
    return chosen


def safe_covering(must_cover, sets):
    """Model the intended Reverse(set.len()), Reverse(weight) ordering."""
    uncovered = set(must_cover)
    chosen = []
    while uncovered:
        if not sets:
            return None
        best = max(
            sets,
            key=lambda entry: (len(entry[0] & uncovered), -len(entry[0]), -entry[1]),
        )
        if best[0].isdisjoint(uncovered):
            return None
        uncovered.difference_update(best[0])
        chosen.append(best)
    return chosen


class TestCoveringTieBreak(unittest.TestCase):
    def test_checked_negation_panics_with_valid_u32_bound(self):
        with self.assertRaises(OverflowError):
            source_covering({"A"}, [(frozenset({"A"}), 2**31)])
        with self.assertRaises(OverflowError):
            source_covering({"A"}, [(frozenset({"A", "B"}), 2**31)])

    def test_release_wraps_at_single_problem_value(self):
        self.assertEqual(source_weight_key(2**31, checked=False), I32_MIN)
        self.assertEqual(source_weight_key(I32_MAX, checked=False), -I32_MAX)
        self.assertEqual(source_weight_key(2**31 + 1, checked=False), I32_MAX)
        self.assertEqual(source_weight_key(U32_MAX, checked=False), 1)

    def test_comparator_prefers_much_larger_weight_when_sets_tie(self):
        sets = [
            (frozenset({"A", "B"}), 1),
            (frozenset({"A", "C"}), 2**31 + 1),
        ]
        # Both cover one requested key and have two columns, so weight should win.
        self.assertEqual(source_covering({"A"}, sets)[0][1], 2**31 + 1)
        self.assertEqual(safe_covering({"A"}, sets)[0][1], 1)

    def test_safe_key_accepts_all_u32_boundary_values(self):
        for weight in (0, 1, I32_MAX, 2**31, 2**31 + 1, U32_MAX):
            self.assertEqual(safe_covering({"A"}, [(frozenset({"A"}), weight)])[0][1], weight)

    def test_small_weight_covering_and_noncoverage(self):
        covered = source_covering({"A", "B"}, [(frozenset({"A"}), 2), (frozenset({"B"}), 3)])
        self.assertEqual({frozenset(x[0]) for x in covered}, {frozenset({"A"}), frozenset({"B"})})
        self.assertIsNone(source_covering({"A", "C"}, [(frozenset({"A"}), 1)]))

    def test_safe_selection_returns_valid_cover_on_finite_universe(self):
        universe = {"A", "B"}
        subsets = [frozenset(), frozenset({"A"}), frozenset({"B"}), frozenset(universe)]
        for a, b in product(subsets, repeat=2):
            result = safe_covering(universe, [(a, 1), (b, 4)])
            if result is not None:
                self.assertGreaterEqual(set().union(*(p[0] for p in result)), universe)


if __name__ == "__main__":
    unittest.main()
