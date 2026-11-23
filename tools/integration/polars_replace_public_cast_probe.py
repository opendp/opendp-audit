"""Compiled Polars 1.36.1 cast probes for public replacement keys.

Diagnostic checks only. Casting public Binary/temporal/numeric keys to String
may fail or change equality, independent of private input values. Probe the
pinned native behavior before claiming a privacy or constructor defect.
"""
import math
import polars as pl


def main():
    assert pl.__version__ == "1.36.1", pl.__version__

    for name, keys in [
        ("nearby_f64", pl.Series("old", [1.0, math.nextafter(1.0, math.inf)], dtype=pl.Float64)),
        ("signed_int", pl.Series("old", [-1, 1], dtype=pl.Int64)),
        ("binary_utf8", pl.Series("old", [b"a", b"b"], dtype=pl.Binary)),
    ]:
        before = keys.n_unique()
        try:
            after_values = keys.cast(pl.String, strict=True)
            after = after_values.n_unique()
            print(f"PUBLIC_CAST_PROBE {name}: BEFORE={before} AFTER={after} VALUES={after_values.to_list()!r}")
            if after < before:
                print(f"PUBLIC_CAST_PROBE {name}: CAST_COLLISION")
        except pl.exceptions.PolarsError as error:
            print(f"PUBLIC_CAST_PROBE {name}: CAST_ERROR={type(error).__name__}: {error}")

    invalid_old = pl.Series("old", [b"\xff"], dtype=pl.Binary)
    valid_new = pl.Series("new", ["replacement"], dtype=pl.String)
    for values in [["a"], ["unrelated"]]:
        expr = pl.col("x").replace(invalid_old, valid_new)
        lf = pl.DataFrame({"x": values}).lazy().with_column(expr)
        try:
            value = lf.collect()["x"].to_list()
            print(f"PUBLIC_CAST_PROBE INVALID_UTF8: EXEC_OK INPUT={values!r} OUTPUT={value!r}")
        except pl.exceptions.PolarsError as error:
            print(f"PUBLIC_CAST_PROBE INVALID_UTF8: DEFERRED_ERROR INPUT={values!r} {type(error).__name__}: {error}")


if __name__ == "__main__":
    main()
