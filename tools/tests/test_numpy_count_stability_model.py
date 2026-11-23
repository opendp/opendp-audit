"""Standalone row-count sensitivity model for OpenDP's NumPy count helper.

Upstream: a010591f55b1713c926f8e355091471634480307
Source: python/src/opendp/extras/numpy/_make_np_count/__init__.py

The test models rows as immutable tuples and symmetric distance as the
multiset insertion/deletion distance. It does not import or execute OpenDP.
Optional NumPy checks only establish source-equivalent row-axis behavior.
"""
from collections import Counter
from itertools import combinations_with_replacement, product
import unittest

try:
    import numpy as np
except ImportError:
    np = None


def modeled_count(rows, *, size=None):
    """Equivalent to lambda x: x.shape[0] if size is None else size."""
    return len(rows) if size is None else size


def modeled_map(d_in, *, size=None):
    """Equivalent to lambda d: d if size is None else 0."""
    return d_in if size is None else 0


def symmetric_distance(a, b):
    """Multiset add/remove distance over the same public column schema."""
    ca, cb = Counter(a), Counter(b)
    return sum((ca - cb).values()) + sum((cb - ca).values())


class TestNumPyCountSourceModel(unittest.TestCase):
    def test_exhaustive_unbounded_row_counts(self):
        checked = 0
        for width in range(4):
            atoms = list(product((0, 1), repeat=width))
            tables = [
                tuple(rows)
                for n in range(5)
                for rows in combinations_with_replacement(atoms, n)
            ]
            for a in tables:
                for b in tables:
                    d_in = symmetric_distance(a, b)
                    self.assertLessEqual(
                        abs(modeled_count(a) - modeled_count(b)),
                        modeled_map(d_in),
                    )
                    checked += 1
        self.assertGreater(checked, 10_000)

    def test_public_fixed_size_returns_constant_zero_sensitivity(self):
        for width in range(4):
            atoms = list(product((0, 1), repeat=width))
            for n in range(5):
                for rows in combinations_with_replacement(atoms, n):
                    self.assertEqual(modeled_count(rows, size=n), n)
                    for d_in in range(8):
                        self.assertEqual(modeled_map(d_in, size=n), 0)

    def test_zero_size_is_defined(self):
        for width in range(5):
            self.assertEqual(modeled_count([], size=0), 0)
            self.assertEqual(modeled_count([], size=None), 0)
            self.assertEqual(modeled_map(0, size=0), 0)

    def test_column_width_does_not_enter_count(self):
        for n in range(5):
            counts = [modeled_count([tuple([7] * width)] * n)
                      for width in range(6)]
            self.assertEqual(counts, [n] * 6)

    def test_permutation_and_value_independence(self):
        a = ((1, 2), (3, 4), (5, 6))
        b = tuple(reversed(a))
        c = ((100, 200), (300, 400), (500, 600))
        self.assertEqual(modeled_count(a), modeled_count(b))
        self.assertEqual(modeled_count(a), modeled_count(c))
        self.assertEqual(symmetric_distance(a, b), 0)
        self.assertEqual(abs(modeled_count(a) - modeled_count(c)), 0)

    @unittest.skipIf(np is None, "NumPy optional in audit CI")
    def test_numpy_row_axis_and_column_count_independence(self):
        for dtype in (np.float32, np.float64, np.int64):
            for width in range(5):
                for n in range(5):
                    x = np.zeros((n, width), dtype=dtype)
                    self.assertEqual(x.shape[0], modeled_count(x))
                    self.assertEqual(x.shape[0], modeled_count(x, size=n))
                    self.assertEqual(x.shape[0], n)


if __name__ == "__main__":
    unittest.main()
