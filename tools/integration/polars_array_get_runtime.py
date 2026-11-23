"""Actual Polars 1.36.1 grouped array-get runtime check for audit #71."""
import unittest
import polars as pl


def aggregate(index: int, null_on_oob: bool):
    data = pl.DataFrame({
        'k': pl.Series('k', [0], dtype=pl.Int32),
        'a': pl.Series('a', [[5, 6]], dtype=pl.Array(pl.Int64, 2)),
        'idx': pl.Series('idx', [index], dtype=pl.Int64),
    })
    return data.lazy().group_by('k').agg(
        pl.col('a').arr.get(pl.col('idx'), null_on_oob=null_on_oob)
        .first().alias('picked')
    ).collect()['picked'].item()


class GroupedArrayGetRuntime(unittest.TestCase):
    def test_pinned_polars_version(self):
        self.assertEqual(pl.__version__, '1.36.1')

    def test_grouped_valid_index_is_success(self):
        self.assertEqual(aggregate(0, False), 5)
        self.assertEqual(aggregate(1, False), 6)

    def test_grouped_private_index_can_trigger_error(self):
        with self.assertRaisesRegex(pl.exceptions.ComputeError, 'get index is out of bounds'):
            aggregate(2, False)

    def test_null_on_oob_prevents_error(self):
        self.assertIsNone(aggregate(2, True))


if __name__ == '__main__':
    unittest.main(verbosity=2)
