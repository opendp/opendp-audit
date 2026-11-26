"""Probe a private repetition count in a stable grouped plan before DP noise.

Pinned wheel is an older build than upstream main. This is a diagnostic
integration probe: it records whether the constructor accepts the plan and
whether execution status differs for neighboring inputs.
"""
import polars as pl
import opendp.prelude as dp


def report(label, call):
    try:
        result = call()
        print(label, "OK", repr(result), flush=True)
        return True
    except BaseException as exc:
        print(label, "ERROR", type(exc).__name__, str(exc)[:800], flush=True)
        return False


def query_on(frame):
    expr = pl.repeat(1, n=pl.col("n").first()).first().alias("v")
    return frame.group_by("k").agg(expr)


def private_release(n):
    data = pl.LazyFrame({
        "k": pl.Series("k", [] if n is None else [0], dtype=pl.Int32),
        "n": pl.Series("n", [] if n is None else [n], dtype=pl.Int64),
    })
    context = dp.Context.compositor(
        data=data,
        privacy_unit=dp.unit_of(contributions=1),
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
    print("Polars", pl.__version__, flush=True)
    for n in (1, -1, None):
        data = pl.LazyFrame({
            "k": pl.Series("k", [] if n is None else [0], dtype=pl.Int32),
            "n": pl.Series("n", [] if n is None else [n], dtype=pl.Int64),
        })
        report(f"raw n={n}", lambda n=n, data=data: query_on(data).collect())
        report(f"private n={n}", lambda n=n: private_release(n))
