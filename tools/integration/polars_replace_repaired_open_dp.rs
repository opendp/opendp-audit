//! Experimental early-validation repair for audit issue #56.
//!
//! Pinned OpenDP is patched *only* in an ephemeral audit CI checkout;
//! this test must never be interpreted as an upstream merge.
//! Baseline (unpatched) regression: tools/integration/polars_replace_open_dp.rs.

use opendp::domains::{AtomDomain, LazyFrameDomain, OptionDomain, SeriesDomain};
use opendp::error::Fallible;
use opendp::metrics::{FrameDistance, SymmetricDistance};
use opendp::transformations::make_stable_lazyframe;
use polars::prelude::*;

#[test]
fn duplicate_public_old_keys_are_rejected_during_construction() -> Fallible<()> {
    let domain = LazyFrameDomain::new(vec![SeriesDomain::new(
        "x",
        AtomDomain::<i32>::default(),
    )])?;

    for values in [[1_i32, 2_i32], [7_i32, 8_i32]] {
        let lf = df!("x" => values)?.lazy();
        let query = lf.clone().with_column(col("x").replace(
            lit(Series::new("old".into(), [1_i32, 1_i32])),
            lit(Series::new("new".into(), [10_i32, 20_i32])),
        ));
        let result = make_stable_lazyframe(
            domain.clone(),
            FrameDistance(SymmetricDistance),
            query,
        );
        let error = match result {
            Ok(_) => panic!("duplicate keys were accepted for input {values:?}"),
            Err(e) => e,
        };
        assert!(
            format!("{error:?}").contains("public old literal keys must be unique"),
            "unexpected construction error: {error:?}",
        );
    }
    Ok(())
}

#[test]
fn duplicate_null_keys_are_rejected_during_construction() -> Fallible<()> {
    let domain = LazyFrameDomain::new(vec![SeriesDomain::new(
        "x",
        OptionDomain::new(AtomDomain::<i32>::default()),
    )])?;
    let lf = df!("x" => [None, Some(1_i32)])?.lazy();
    let query = lf.clone().with_column(col("x").replace(
        lit(Series::new("old".into(), [None::<i32>, None])),
        lit(Series::new("new".into(), [10_i32, 20_i32])),
    ));
    let result = make_stable_lazyframe(domain, FrameDistance(SymmetricDistance), query);
    assert!(result.is_err(), "two public null keys must be rejected");
    Ok(())
}

#[test]
fn duplicate_nan_keys_are_rejected_during_construction() -> Fallible<()> {
    let domain = LazyFrameDomain::new(vec![SeriesDomain::new(
        "x",
        AtomDomain::<f64>::default(),
    )])?;
    let lf = df!("x" => [f64::NAN, 1_f64])?.lazy();
    let query = lf.clone().with_column(col("x").replace(
        lit(Series::new("old".into(), [f64::NAN, f64::NAN])),
        lit(Series::new("new".into(), [10_f64, 20_f64])),
    ));
    let result = make_stable_lazyframe(domain, FrameDistance(SymmetricDistance), query);
    assert!(result.is_err(), "duplicate public NaN keys must be rejected");
    Ok(())
}

#[test]
fn distinct_keys_and_null_imputation_still_work() -> Fallible<()> {
    let domain = LazyFrameDomain::new(vec![SeriesDomain::new(
        "x",
        OptionDomain::new(AtomDomain::<i32>::default()),
    )])?;
    let lf = df!("x" => [Some(1_i32), None, Some(2_i32)])?.lazy();
    let query = lf.clone().with_column(col("x").replace(
        lit(Series::new("old".into(), [Some(1_i32), None])),
        lit(Series::new("new".into(), [10_i32, 0_i32])),
    ));
    let t = make_stable_lazyframe(domain, FrameDistance(SymmetricDistance), query)?;
    assert!(!t.output_domain.series_domain("x".into())?.nullable);
    assert_eq!(
        t.invoke(&lf)?.collect()?,
        df!("x" => [10_i32, 0_i32, 2_i32])?
    );
    Ok(())
}

#[test]
fn single_scalar_key_remains_valid() -> Fallible<()> {
    let domain = LazyFrameDomain::new(vec![SeriesDomain::new(
        "x",
        AtomDomain::<i32>::default(),
    )])?;
    let lf = df!("x" => [1_i32, 2_i32])?.lazy();
    let query = lf.clone().with_column(col("x").replace(lit(1_i32), lit(10_i32)));
    let t = make_stable_lazyframe(domain, FrameDistance(SymmetricDistance), query)?;
    assert_eq!(t.invoke(&lf)?.collect()?, df!("x" => [10_i32, 2_i32])?);
    Ok(())
}
