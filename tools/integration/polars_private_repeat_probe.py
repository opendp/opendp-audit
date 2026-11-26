"""Native source-equivalent privacy counterexample for OpenDP's repeat preflight.

The two one-row inputs differ by one substitution under ChangeOneDistance.
The same epsilon=1 query releases on n=1 but raises before noise on n=-1.
"""
import polars as pl
import opendp.prelude as dp


def release(n: int):
    data = pl.LazyFrame({
        "k": pl.Series("k", [0], dtype=pl.Int32),
        "n": pl.Series("n", [n], dtype=pl.Int64),
    })
    context = dp.Context.compositor(
        data=data,
        privacy_unit=dp.unit_of(changes=1),
        privacy_loss=dp.loss_of(epsilon=1.0),
        margins=[dp.polars.Margin(max_length=1)],
    )
    return (
        context.query(epsilon=1.0)
        .group_by("k")
        .agg(pl.repeat(1, n=pl.col("n").first()).first().alias("v"))
        .select(pl.col("v").dp.sum((0, 2)))
        .release()
        .collect()
    )


if __name__ == "__main__":
    dp.enable_features("contrib")
    assert pl.__version__ == "1.36.1"
    print("n=1: noisy private release succeeds:", release(1), flush=True)
    try:
        release(-1)
    except pl.exceptions.ComputeError as err:
        assert "could not parse value '-1' as a size" in str(err)
        print("n=-1: deterministic pre-noise ComputeError:", err, flush=True)
    else:
        raise AssertionError("expected a data-dependent pre-noise exception")
