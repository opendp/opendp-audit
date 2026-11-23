"""Source-model regression for the global-group private select constructor.

Not compiled OpenDP. Pinned upstream SHA:
ef1a238634d6196b01a1a1e77d3d5ad2340e3094
"""
from collections import Counter
from fractions import Fraction
from itertools import product
import random
import unittest


def get_empty_group_per_group(bounds):
    # Bounds::get_bound(empty) uses only bindings with by subset of empty.
    vals = [limit for by, limit in bounds if not by and limit is not None]
    return min(vals) if vals else None


def select_distance(bounds):
    # make_private_select::t_group_by stability map
    rows = get_empty_group_per_group(bounds)
    if rows is None:
        raise ValueError("per_group contributions is unknown")
    return 1, rows, rows


def sym_diff_rows(left, right):
    x, y = Counter(left), Counter(right)
    return sum((x - y).values()) + sum((y - x).values())


def compose_costs(nonnegative_coefficients, mapped_distance):
    if not nonnegative_coefficients:
        raise ValueError("Must have at least one measurement")
    # Synthetic additive privacy maps to test the single invocation/composition
    # wiring; not an implementation of a particular OpenDP measure.
    return sum((Fraction(coeff) * mapped_distance[2]
                for coeff in nonnegative_coefficients), Fraction(0))


def valid_projection_options(duplicate_check, should_broadcast, run_parallel):
    del run_parallel
    return duplicate_check and should_broadcast


class PrivateSelectSourceModel(unittest.TestCase):
    def test_missing_global_bound_rejected(self):
        for bounds in [[], [(frozenset({"k"}), 2)],
                       [(frozenset(), None), (frozenset({"k"}), 3)]]:
            with self.assertRaisesRegex(ValueError, "unknown"):
                select_distance(bounds)

    def test_empty_composition_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            compose_costs([], (1, 2, 2))

    def test_global_bound_and_composition(self):
        self.assertEqual(select_distance([
            (frozenset({"k"}), 1),
            (frozenset(), 7), (frozenset(), 4),
        ]), (1, 4, 4))
        self.assertEqual(compose_costs([Fraction(1, 2), 2, 3],
                                       (1, 4, 4)), Fraction(22, 1))

    def test_projection_options(self):
        for duplicate, broadcast, parallel in product((False, True), repeat=3):
            self.assertEqual(valid_projection_options(duplicate, broadcast, parallel),
                             duplicate and broadcast)

    def test_finite_multiset_distance_bound_exhaustive(self):
        alphabet = (0, 1, 2)
        datasets = [t for n in range(5) for t in product(alphabet, repeat=n)]
        checked = 0
        for left in datasets:
            for right in datasets:
                true_rows = sym_diff_rows(left, right)
                l0, l1, li = select_distance([(frozenset(), true_rows)])
                true_groups = int(Counter(left) != Counter(right))
                self.assertLessEqual(true_groups, l0)
                self.assertLessEqual(true_rows, l1)
                self.assertLessEqual(true_rows, li)
                checked += 1
        self.assertEqual(checked, 14641)

    def test_randomized_contributions_and_cost_additivity(self):
        rng = random.Random(20261123)
        for _ in range(10000):
            left = tuple(rng.randrange(8) for _ in range(rng.randrange(15)))
            right = tuple(rng.randrange(8) for _ in range(rng.randrange(15)))
            d = sym_diff_rows(left, right)
            mapped = select_distance([(frozenset(), d)])
            coeffs = [Fraction(rng.randrange(11), 4)
                      for _ in range(rng.randrange(1, 8))]
            self.assertEqual(compose_costs(coeffs, mapped), sum(coeffs) * d)
            self.assertLessEqual(int(Counter(left) != Counter(right)), mapped[0])


if __name__ == "__main__":
    unittest.main()
