"""Probe data-dependent integer arithmetic faults in OpenDP's Polars binary expressions.

Tests the pinned Polars version in an isolated GitHub runner. Prints raw Polars
results, stable-expression acceptance, and complete private-release outcomes.
Do not infer a DP leak from a numerical wrap alone; require divergent errors.
"""
import polars as pl
import opendp.prelude as dp

CASE_VALUES = (0, -(2**63))

def expr_for(case):
    x = pl.col("x")
    minus_one = pl.lit(-1, dtype=pl.Int64)
    zero = pl.lit(0, dtype=pl.Int64)
    return {
        "floor_div_min_minus_one": lambda: x // minus_one,
        "mod_min_minus_one": lambda: x % minus_one,
        "floor_div_zero": lambda: x // zero,
        "mod_zero": lambda: x % zero,
    }[case]()

def invoke(label, callable_):
    try:
        result = callable_()
        print(label, "SUCCESS", repr(result), flush=True)
        return True, result
    except BaseException as error:
        print(label, "ERROR", type(error).__name__, str(error)[:1200], flush=True)
        return False, error

def probe_case(case):
    expr = expr_for(case)
    seed = pl.LazyFrame(schema={"x": pl.Int64})
    public_domain = dp.lazyframe_domain([
        dp.series_domain("x", dp.atom_domain(T="i64"))
    ])
    metric = dp.symmetric_distance()
    invoke(
        f"stable transformation {case}",
        lambda: dp.t.make_stable_lazyframe(
            public_domain, metric, seed.select(expr.alias("out"))
        ),
    )

    for x in CASE_VALUES:
        data = pl.LazyFrame({"x": pl.Series("x", [x], dtype=pl.Int64)})
        invoke(f"raw {case} x={x}", lambda: data.select(expr.alias("out")).collect())

        def private_release():
            context = dp.Context.compositor(
                data=data,
                privacy_unit=dp.unit_of(contributions=1),
                privacy_loss=dp.loss_of(epsilon=1.0),
                margins=[dp.polars.Margin(max_length=1)],
            )
            # Clip the arithmetic expression to make a bounded private sum.
            sanitized = expr.fill_null(0).clip(-5, 5)
            return (
                context.query(epsilon=1.0)
                .select(sanitized.dp.sum((-5, 5)))
                .release()
                .collect()
            )

        invoke(f"private release {case} x={x}", private_release)

if __name__ == "__main__":
    dp.enable_features("contrib", "idealized-numerics")
    print("Polars", pl.__version__, flush=True)
    for case in (
        "floor_div_min_minus_one",
        "mod_min_minus_one",
        "floor_div_zero",
        "mod_zero",
    ):
        probe_case(case)
