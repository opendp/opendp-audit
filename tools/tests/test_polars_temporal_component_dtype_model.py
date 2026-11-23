"""Source-guard model: OpenDP temporal-component construction versus pinned Polars.

Pinned OpenDP SHA ef1a238634d6196b01a1a1e77d3d5ad2340e3094.
Pinned Polars dependency py-1.36.1; series TemporalMethods::year/hour.
This is not an execution of either Rust library.
"""

import unittest


CALENDAR = frozenset({"Year", "Month"})
TIME_OF_DAY = frozenset({"Hour", "Minute"})
RECOGNIZED = CALENDAR | TIME_OF_DAY
TEMPORAL = frozenset({"Date", "Time", "DatetimeNs"})


def opendp_constructor_allows(dtype: str, function: str) -> bool:
    """Projection of the two independent matches in make_expr_datetime_component."""
    return function in RECOGNIZED and dtype in TEMPORAL


def polars_series_allows(dtype: str, function: str) -> bool:
    """Pinned Polars TemporalMethods match arms for calendar/time methods."""
    if function in CALENDAR:
        return dtype in {"Date", "DatetimeNs", "DatetimeUs", "DatetimeMs"}
    if function in TIME_OF_DAY:
        return dtype in {"Time", "DatetimeNs", "DatetimeUs", "DatetimeMs"}
    return False


class TestTemporalComponentCompatibility(unittest.TestCase):
    def test_time_year_is_wrongly_accepted(self):
        self.assertTrue(opendp_constructor_allows("Time", "Year"))
        self.assertFalse(polars_series_allows("Time", "Year"))

    def test_date_hour_is_wrongly_accepted(self):
        self.assertTrue(opendp_constructor_allows("Date", "Hour"))
        self.assertFalse(polars_series_allows("Date", "Hour"))

    def test_valid_pairs_pass_both_guards(self):
        for dtype, function in [
            ("Date", "Year"),
            ("Date", "Month"),
            ("Time", "Hour"),
            ("Time", "Minute"),
            ("DatetimeNs", "Year"),
            ("DatetimeNs", "Hour"),
        ]:
            with self.subTest(dtype=dtype, function=function):
                self.assertTrue(opendp_constructor_allows(dtype, function))
                self.assertTrue(polars_series_allows(dtype, function))

    def test_all_calendar_time_cross_pairs_fail_backend(self):
        for function in CALENDAR:
            self.assertTrue(opendp_constructor_allows("Time", function))
            self.assertFalse(polars_series_allows("Time", function))
        for function in TIME_OF_DAY:
            self.assertTrue(opendp_constructor_allows("Date", function))
            self.assertFalse(polars_series_allows("Date", function))

    def test_ms_us_datetime_rejected_by_opendp_as_independent_range_guard(self):
        for dtype in ("DatetimeMs", "DatetimeUs"):
            for function in RECOGNIZED:
                self.assertFalse(opendp_constructor_allows(dtype, function))
                self.assertTrue(polars_series_allows(dtype, function))

    def test_non_temporal_and_unrecognized_functions_rejected(self):
        for dtype in ("Int32", "String", "Boolean"):
            for function in RECOGNIZED:
                self.assertFalse(opendp_constructor_allows(dtype, function))
        for dtype in TEMPORAL:
            self.assertFalse(opendp_constructor_allows(dtype, "Resample"))


if __name__ == "__main__":
    unittest.main()
