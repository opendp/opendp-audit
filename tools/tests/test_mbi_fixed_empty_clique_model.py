"""Zero-clique Fixed MBI source model at upstream a010591f55b1713c926f8e355091471634480307.

Models Count's acceptance rules and the pinned Polars DataFrame[()] dispatcher
without importing OpenDP or Polars. NumPy-specific pivot checks skip when the
optional dependency is absent. Native OpenDP and pinned Polars not executed.

Polars source: py-1.36.1 commit 2a151c10fa76790711c2f75e6d012dd69c627ddd.
"""
import unittest

try:
    import numpy as np
except ImportError:
    np = None


class SourceModelFrame:
    """Narrow model of the relevant pinned Polars getitem/clear/to_numpy path."""

    def __init__(self, n_rows: int, n_columns: int):
        self.n_rows = n_rows
        self.n_columns = n_columns

    def clear(self):
        # Polars DataFrame.clear() retains the column schema, but zeroes rows.
        return SourceModelFrame(n_rows=0, n_columns=self.n_columns)

    def __getitem__(self, key):
        # py-1.36.1 get_df_item_by_key -> _select_rows for tuple != length 2;
        # empty Sequence key -> df.clear(), *not* an empty column projection.
        if isinstance(key, tuple) and len(key) == 0:
            return self.clear()
        raise TypeError("model only covers empty tuple indexing")

    def to_numpy(self):
        if np is None:
            raise RuntimeError("NumPy optional")
        return np.zeros((self.n_rows, self.n_columns), dtype=np.int64)


class TestFixedEmptyCliqueSourceModel(unittest.TestCase):
    def test_empty_clique_passes_count_validation(self):
        # Count.__post_init__ checks all columns are strings; []/() passes.
        clique = ()
        self.assertTrue(all(isinstance(col, str) for col in clique))
        self.assertEqual(tuple(str(col) for col in clique), ())
        self.assertTrue(bool([clique]))  # Fixed requires >= 1 query
        self.assertEqual(tuple(()), ())  # make_stable_marginals shape(clique)

    def test_pinned_polars_empty_index_selects_rows(self):
        frame = SourceModelFrame(n_rows=1, n_columns=1)
        cleared = frame[()]
        self.assertEqual(cleared.n_rows, 0)
        self.assertEqual(cleared.n_columns, 1)

    @unittest.skipIf(np is None, "NumPy optional in audit CI")
    def test_pivot_cannot_index_zero_dimensional_array(self):
        frame = SourceModelFrame(n_rows=1, n_columns=1)
        clique = ()
        y = np.zeros((), dtype=np.int32)
        key_indices = tuple(frame[clique].to_numpy().T)
        self.assertEqual(len(key_indices), 1)
        self.assertEqual(key_indices[0].shape, (0,))
        with self.assertRaisesRegex(IndexError, "too many indices"):
            y[key_indices] = np.array([4], dtype=np.int32)

    @unittest.skipIf(np is None, "NumPy optional in audit CI")
    def test_corrected_scalar_assignment(self):
        y = np.zeros((), dtype=np.int32)
        y[()] = np.int32(4)
        self.assertEqual(y.shape, ())
        self.assertEqual(y.item(), 4)


if __name__ == "__main__":
    unittest.main()
