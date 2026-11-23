"""SQLite/source-flow regression for the legacy Ibis adapter's empty SUM path.

This is NOT an OpenDP, Polars, Ibis, or compiled FFI integration test.
It models the integer SUM(CASE ...) SQL from polars-to-ibis and the scalar
extraction performed by OpenDP's legacy run_on_database adapter.
Pinned OpenDP main: a010591f55b1713c926f8e355091471634480307.
"""
import sqlite3
import unittest


# Bounded 0..10 row values with public null filler 5, as in the
# polars-to-ibis integer DP sum expression. The translator generates
# SUM of a nested CASE expression, without an outer COALESCE.
SUM_SQL = """
SELECT SUM(
    CASE WHEN ints IS NULL THEN 5
         WHEN ints < 0 THEN 0
         WHEN ints > 10 THEN 10
         ELSE ints END
) AS ints FROM private_data
"""


class TestIbisEmptySumSourceModel(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute("CREATE TABLE private_data (ints INTEGER)")

    def tearDown(self):
        self.connection.close()

    def sql_result(self, rows):
        self.connection.execute("DELETE FROM private_data")
        self.connection.executemany(
            "INSERT INTO private_data (ints) VALUES (?)", [(v,) for v in rows]
        )
        fetched = self.connection.execute(SUM_SQL).fetchall()
        self.assertEqual(len(fetched), 1)
        # Mirrors the list-valued dict produced by .to_polars(...).to_dict().
        return {"ints": [fetched[0][0]]}

    @staticmethod
    def legacy_scalar_extraction(private_result):
        # Verbatim scalar-extraction comprehension from run_on_database.
        private_items = [v[0] for v in private_result.values()]
        return private_items[0]

    def test_empty_and_one_record_sql_sums_are_different_carrier_types(self):
        empty = self.legacy_scalar_extraction(self.sql_result([]))
        one = self.legacy_scalar_extraction(self.sql_result([1]))
        self.assertIsNone(empty)
        self.assertIs(type(one), int)
        self.assertEqual(one, 1)

    def test_sql_sum_has_no_public_zero_fallback(self):
        self.assertNotIn("COALESCE(SUM(", SUM_SQL.upper())
        self.assertIsNone(self.legacy_scalar_extraction(self.sql_result([])))
        self.assertEqual(self.legacy_scalar_extraction(self.sql_result([0])), 0)

    def test_bounded_row_clipping_does_not_change_empty_sql_sum(self):
        self.assertIsNone(self.legacy_scalar_extraction(self.sql_result([])))
        self.assertEqual(self.legacy_scalar_extraction(self.sql_result([100])), 10)
        self.assertEqual(self.legacy_scalar_extraction(self.sql_result([-50])), 0)

    def test_type_sensitive_noise_stub_distinguishes_null_carrier(self):
        # This represents type checking at an integer noise input boundary.
        # It is NOT a reproduction of OpenDP's native measurement invocation.
        def strict_integer_noise_stub(value):
            if type(value) is not int:
                raise TypeError("not an integer carrier")
            return value

        with self.assertRaises(TypeError):
            strict_integer_noise_stub(
                self.legacy_scalar_extraction(self.sql_result([]))
            )
        self.assertEqual(
            strict_integer_noise_stub(
                self.legacy_scalar_extraction(self.sql_result([1]))
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
