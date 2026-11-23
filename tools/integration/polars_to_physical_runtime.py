"""Real Polars 1.36.1 executor tests, not native OpenDP construction."""
import datetime as dt
import math
import unittest

import polars as pl


def physical(values, dtype):
    series = pl.Series("x", values, dtype=dtype)
    return pl.DataFrame({"x": series}).lazy().select(pl.col("x").to_physical()).collect()["x"]


class PinnedPolarsToPhysicalTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(pl.__version__, "1.36.1")

    def test_signed_pre_epoch_dates(self):
        epoch = dt.date(1970, 1, 1)
        end = dt.date(2024, 1, 1)
        result = physical([dt.date(1969, 12, 31), epoch, None, end], pl.Date)
        self.assertEqual(result.dtype, pl.Int32)
        self.assertEqual(result.to_list(), [-1, 0, None, (end - epoch).days])

    def test_fixed_enum_widths_and_codes(self):
        for n, expected in ((4, pl.UInt8), (256, pl.UInt16), (65536, pl.UInt32)):
            with self.subTest(n=n):
                enum = pl.Enum([str(i) for i in range(n)])
                result = physical(["1", "0", None, "1", "3"], enum)
                self.assertEqual(result.dtype, expected)
                self.assertEqual(result.to_list(), [1, 0, None, 1, 3])

    def test_enum_mapping_independent_of_order(self):
        enum = pl.Enum(["B", "A", "C"])
        self.assertEqual(physical(["A", "B", "C"], enum).to_list(), [1, 0, 2])
        self.assertEqual(physical(["C", "B", "A"], enum).to_list(), [2, 0, 1])

    def test_categorical_codes_change_with_category_appearance(self):
        # OpenDP now rejects Categorical because its assignment may be data-dependent.
        self.assertFalse(pl.using_string_cache())
        before = physical(["red", "red"], pl.Categorical)
        after = physical(["blue", "red", "red"], pl.Categorical)
        self.assertEqual(before.dtype, pl.UInt32)
        self.assertEqual(after.dtype, pl.UInt32)
        self.assertNotEqual(before[0], after[1])

    def test_temporal_i64_storage(self):
        samples = [
            (pl.Time, [dt.time(0, 0, 1), None], [1_000_000_000, None]),
            (pl.Datetime("us"), [dt.datetime(1969, 12, 31, 23, 59, 59), None], [-1_000_000, None]),
            (pl.Duration("us"), [dt.timedelta(days=-1), None], [-86_400_000_000, None]),
        ]
        for dtype, values, expected in samples:
            with self.subTest(dtype=dtype):
                out = physical(values, dtype)
                self.assertEqual(out.dtype, pl.Int64)
                self.assertEqual(out.to_list(), expected)

    def test_identity_float_keeps_nan_and_null(self):
        out = physical([1.0, float("nan"), None], pl.Float64)
        self.assertEqual(out.dtype, pl.Float64)
        self.assertEqual(out[0], 1.0)
        self.assertTrue(math.isnan(out[1]))
        self.assertIsNone(out[2])


if __name__ == "__main__":
    unittest.main(verbosity=2)
