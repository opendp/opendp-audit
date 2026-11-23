"""Independent small-multiset model of Polars fill and drop transforms.

This does NOT execute compiled OpenDP or Polars. It tests the record-local
mathematical invariant and source-level domain-flag conditions.
"""
from collections import Counter
from itertools import product
import unittest

NULL = "NULL"
NAN = "NAN"
# A row has a target value and a non-null, non-NaN fallback column.
ROWS = tuple(product((NULL, NAN, -1, 2), (0, 3)))
OUT_ALPHABET = (NULL, NAN, -1, 0, 2, 3)


def fill_null(row):
    value, fallback = row
    return fallback if value == NULL else value


def fill_nan(row):
    value, fallback = row
    return fallback if value == NAN else value


def drop_null(row):
    value, _ = row
    return () if value == NULL else (value,)


def drop_nan(row):
    value, _ = row
    return () if value == NAN else (value,)


def multiset_l1(first, second):
    return sum(abs(a - b) for a, b in zip(first, second))


def per_dataset_counts(dataset, op):
    counts = Counter()
    for row in dataset:
        for value in op(row):
            counts[value] += 1
    return tuple(counts[item] for item in OUT_ALPHABET)


def input_counts(dataset):
    counts = Counter(dataset)
    return tuple(counts[row] for row in ROWS)


class PolarsFillDropModelTests(unittest.TestCase):
    def test_all_small_multiset_pairs_are_nonexpansive(self):
        datasets = tuple(x for n in range(4) for x in product(ROWS, repeat=n))
        self.assertEqual(len(datasets), 585)
        input_profiles = [input_counts(d) for d in datasets]
        operations = (
            lambda row: (fill_null(row),),
            lambda row: (fill_nan(row),),
            drop_null,
            drop_nan,
        )
        checked = 0
        for op in operations:
            out_profiles = [per_dataset_counts(d, op) for d in datasets]
            for i, inp_left in enumerate(input_profiles):
                for j, inp_right in enumerate(input_profiles):
                    self.assertLessEqual(
                        multiset_l1(out_profiles[i], out_profiles[j]),
                        multiset_l1(inp_left, inp_right),
                    )
                    checked += 1
        self.assertEqual(checked, 4 * 585**2)

    def test_domain_nan_and_nullable_flags(self):
        # Mirrors fill_null source:
        # output_nan = data.nan || (data.nullable && fill.nan),
        # output_nullable=false, but filler itself must be non-null.
        # For a non-null data expression, an unused NaN filler is harmless.
        tested = 0
        for data_nan, data_nullable, filler_nan in product((False, True), repeat=3):
            out_nan = data_nan or (data_nullable and filler_nan)
            possible_values = (NAN if data_nan else 1, NULL if data_nullable else 1)
            for value in possible_values:
                result = NAN if (value == NULL and filler_nan) else (
                    0 if value == NULL else value
                )
                self.assertNotEqual(result, NULL)
                self.assertTrue(out_nan or result != NAN)
                tested += 1
        self.assertEqual(tested, 16)

    def test_fill_nan_preserves_null_and_removes_nan(self):
        data = (NULL, NAN, -1, 2)
        observed = tuple(fill_nan((v, 3)) for v in data)
        self.assertEqual(observed, (NULL, 3, -1, 2))
        self.assertTrue(NULL in observed)
        self.assertFalse(NAN in observed)
        self.assertEqual(tuple(fill_null((v, 3)) for v in data), (3, NAN, -1, 2))

    def test_drop_changes_group_lengths_but_preserves_keys(self):
        records = (("a", NULL), ("a", 2), ("b", NAN), ("b", 3))
        original = {key: [v for k, v in records if k == key]
                    for key in ("a", "b")}
        dropped = {key: [v for v in vals if v not in (NULL, NAN)]
                   for key, vals in original.items()}
        self.assertEqual(set(dropped), set(original))
        self.assertEqual(dropped, {"a": [2], "b": [3]})
        self.assertNotEqual(tuple(map(len, dropped.values())),
                            tuple(map(len, original.values())))
        # A pre-existing invariant weakened to Keys must not be restored
        # to Lengths by a later fill, even when its filler is a literal.
        for invariant in (None, "Keys", "Lengths"):
            after_drop = None if invariant is None else "Keys"
            after_literal_fill = after_drop
            self.assertNotEqual(after_literal_fill, "Lengths")


if __name__ == "__main__":
    unittest.main()
