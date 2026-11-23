//! Pinned native OpenDP/Polars probes for public RangeLiteralValue replacement keys.
//! Audit task #81. Probes emit explicit EARLY_REJECTED / DEFERRED_ERROR verdicts
//! so the test remains diagnostic until the construction-time contract is known.
//! These tests are installed only in the temporary CI checkout of pinned OpenDP.

use opendp::domains::{AtomDomain, LazyFrameDomain, SeriesDomain};
use opendp::error::Fallible;
use opendp::metrics::{FrameDistance, SymmetricDistance};
use opendp::transformations::make_stable_lazyframe;
use polars::prelude::*;
use polars_plan::plans::{LiteralValue, RangeLiteralValue};

#[test]
fn public_range_with_string_dtype_is_rejected_or_errors_on_evaluation() -> Fallible<()> {
    let domain = LazyFrameDomain::new(vec![SeriesDomain::new(
        "x",
        AtomDomain::<String>::default(),
    )])?;
    let lf = df!("x" => ["a", "b"])?.lazy();
    let old = Expr::Literal(LiteralValue::Range(RangeLiteralValue {
        low: 0,
        high: 2,
        dtype: DataType::String,
    }));
    let query = lf.clone().with_column(col("x").replace(old, lit("new")));

    match make_stable_lazyframe(domain, FrameDistance(SymmetricDistance), query) {
        Ok(t) => match t.invoke(&lf)?.collect() {
            Ok(df) => panic!("unexpected successful string-typed range: {df:?}"),
            Err(e) => eprintln!("RANGE_PROBE_STRING: DEFERRED_ERROR: {e}"),
        },
        Err(e) => eprintln!("RANGE_PROBE_STRING: EARLY_REJECTED: {e}"),
    }
    Ok(())
}

#[test]
fn public_uint32_range_with_negative_bound_is_rejected_or_errors_on_evaluation() -> Fallible<()> {
    let domain = LazyFrameDomain::new(vec![SeriesDomain::new(
        "x",
        AtomDomain::<u32>::default(),
    )])?;
    let lf = df!("x" => [0_u32, 1_u32])?.lazy();
    let old = Expr::Literal(LiteralValue::Range(RangeLiteralValue {
        low: -1,
        high: 2,
        dtype: DataType::UInt32,
    }));
    let query = lf.clone().with_column(col("x").replace(old, lit(10_u32)));

    match make_stable_lazyframe(domain, FrameDistance(SymmetricDistance), query) {
        Ok(t) => match t.invoke(&lf)?.collect() {
            Ok(df) => panic!("unexpected successful negative UInt32 range: {df:?}"),
            Err(e) => eprintln!("RANGE_PROBE_UINT32: DEFERRED_ERROR: {e}"),
        },
        Err(e) => eprintln!("RANGE_PROBE_UINT32: EARLY_REJECTED: {e}"),
    }
    Ok(())
}

#[test]
fn public_valid_int32_range_can_replace_three_keys() -> Fallible<()> {
    let domain = LazyFrameDomain::new(vec![SeriesDomain::new(
        "x",
        AtomDomain::<i32>::default(),
    )])?;
    let lf = df!("x" => [1_i32, 2_i32, 3_i32, 4_i32])?.lazy();
    let old = Expr::Literal(LiteralValue::Range(RangeLiteralValue {
        low: 1,
        high: 4,
        dtype: DataType::Int32,
    }));
    let query = lf.clone().with_column(col("x").replace(old, lit(10_i32)));
    let t = make_stable_lazyframe(domain, FrameDistance(SymmetricDistance), query)?;
    assert_eq!(t.invoke(&lf)?.collect()?, df!("x" => [10_i32, 10_i32, 10_i32, 4_i32])?);
    Ok(())
}
