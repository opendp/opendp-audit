"""Pinned Polars runtime witness for OpenDP's boolean Not dtype guard.

OpenDP constructor-side reasoning is recorded in the source audit, not
executed here. This checks the actual Polars behavior at the compatible
Python tag (1.36.1).
"""

import polars as pl


def check_unsupported(dtype: pl.DataType, values: list) -> None:
    source = pl.DataFrame({"x": pl.Series("x", values, dtype=dtype)}).lazy()
    try:
        source.select(pl.col("x").not_()).collect()
    except pl.exceptions.InvalidOperationError as exc:
        assert "not supported in 'not' operation" in str(exc), str(exc)
    else:
        raise AssertionError(f"Polars unexpectedly accepted Not on {dtype}")


def main() -> None:
    assert pl.__version__ == "1.36.1", pl.__version__

    check_unsupported(pl.Float64, [1.5, None, -2.0])
    check_unsupported(pl.Float32, [1.5, None, -2.0])
    check_unsupported(pl.String, ["A", None, "B"])

    integers = pl.DataFrame({"x": pl.Series("x", [0, 1, None], dtype=pl.Int64)})
    assert integers.lazy().select(pl.col("x").not_()).collect()["x"].to_list() == [
        -1,
        -2,
        None,
    ]
    booleans = pl.DataFrame({"x": pl.Series("x", [True, None, False], dtype=pl.Boolean)})
    assert booleans.lazy().select(pl.col("x").not_()).collect()["x"].to_list() == [
        False,
        None,
        True,
    ]
    print("Polars 1.36.1: Not rejected on Float32/Float64/String; accepted on Int64/Boolean")


if __name__ == "__main__":
    main()
