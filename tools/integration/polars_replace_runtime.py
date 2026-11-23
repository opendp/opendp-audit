"""Run against the actual compiled Python Polars 1.36.1 runtime.

This intentionally does *not* import OpenDP; its job is to confirm the
executor-side behavior identified by the pinned Polars source audit.
The OpenDP constructor is covered by the companion Rust integration test.
"""

import unittest

import polars as pl


OLD_DUPLICATE = pl.Series("old", [1, 1], dtype=pl.Int32)
NEW_DUPLICATE = pl.Series("new", [10, 20], dtype=pl.Int32)


def replace_query(values, old, new):
    data = pl.DataFrame({"x": pl.Series("x", values, dtype=pl.Int32)})
    # Construction of the Expr and LazyFrame does not evaluate replacements.
    return data.lazy().select(pl.col("x").replace(old, new).alias("out"))


class PinnedPolarsReplaceTests(unittest.TestCase):
    def test_exact_pinned_python_version(self):
        self.assertEqual(pl.__version__, "1.36.1")

    def test_duplicate_public_keys_fail_even_without_matching_input(self):
        for values in ([1, 2], [7, 8]):
            with self.subTest(values=values):
                plan = replace_query(values, OLD_DUPLICATE, NEW_DUPLICATE)
                with self.assertRaisesRegex(
                    pl.exceptions.InvalidOperationError, "duplicates"
                ):
                    plan.collect()

    def test_distinct_public_keys_work(self):
        plan = replace_query(
            [1, 2],
            pl.Series("old", [1, 2], dtype=pl.Int32),
            pl.Series("new", [10, 20], dtype=pl.Int32),
        )
        self.assertEqual(plan.collect()["out"].to_list(), [10, 20])

    def test_null_key_imputes_null(self):
        plan = replace_query(
            [None, 1, 2],
            pl.Series("old", [None, 1], dtype=pl.Int32),
            pl.Series("new", [0, 10], dtype=pl.Int32),
        )
        self.assertEqual(plan.collect()["out"].to_list(), [0, 10, 2])


if __name__ == "__main__":
    unittest.main(verbosity=2)
