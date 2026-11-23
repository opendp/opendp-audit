//! Native pinned-OpenDP/Polars integration regression for audit issue #56.
//!
//! Tests the existing upstream constructor/executor behavior; this is not a
//! proposed repair and must run in a temporary CI checkout of pinned OpenDP.
//! OpenDP: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
//! Polars: py-1.36.1 (from the OpenDP Cargo.toml patch).

use opendp::domains::{AtomDomain, LazyFrameDomain, OptionDomain, SeriesDomain};
use opendp::error::Fallible;
use opendp::metrics::{FrameDistance, SymmetricDistance};
use opendp::transformations::make_stable_lazyframe;
use polars::prelude::*;

#[test]
fn public_duplicate_old_keys_construct_but_fail_at_collection() -> Fallible<()> {
    let domain = LazyFrameDomain::new(vec![SeriesDomain::new(
        "x",
        AtomDomain::<i32>::default(),
    )])?;

    // Both public mappings have the correct lengths and Int32 dtypes, but
    // the old keys are duplicated. The input values do not affect the error.
    for values in [[1_i32, 2_i32], [7_i32, 8_i32]] {
        let lf = df!("x" => values)?.lazy();
        let query = lf.clone().with_column(col("x").replace(
            lit(Series::new("old".into(), [1_i32, 1_i32])),
            lit(Series::new("new".into(), [10_i32, 20_i32])),
        ));
        let t = make_stable_lazyframe(
            domain.clone(),
            FrameDistance(SymmetricDistance),
            query,
        )?;
        let released = t.invoke(&lf)?;
        let error = released
            .collect()
            .expect_err("duplicate public keys should trigger Polars error");
        assert!(
            error.to_string().contains("duplicates"),
            "unexpected Polars error for {values:?}: {error}"
        );
    }
    Ok(())
}

#[test]
fn distinct_public_keys_are_accepted() -> Fallible<()> {
    let domain = LazyFrameDomain::new(vec![SeriesDomain::new(
        "x",
        AtomDomain::<i32>::default(),
    )])?;
    let lf = df!("x" => [1_i32, 2_i32])?.lazy();
    let query = lf.clone().with_column(col("x").replace(
        lit(Series::new("old".into(), [1_i32, 2_i32])),
        lit(Series::new("new".into(), [10_i32, 20_i32])),
    ));
    let t = make_stable_lazyframe(domain, FrameDistance(SymmetricDistance), query)?;
    assert_eq!(t.invoke(&lf)?.collect()?, df!("x" => [10_i32, 20_i32])?);
    Ok(())
}

#[test]
fn replacing_public_null_key_removes_nullity() -> Fallible<()> {
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
