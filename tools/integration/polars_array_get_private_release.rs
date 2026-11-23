//! End-to-end native OpenDP release regression for audit issue #71.
//!
//! Pinned OpenDP main ef1a238634d6196b01a1a1e77d3d5ad2340e3094
//! Polars 0.52.0 / py-1.36.1 as patched by pinned OpenDP Cargo.toml.
//!
//! Keep the fallible group-by expression live by selecting a private noisy
//! SUM of its output. The array is a PUBLIC LITERAL. Only primitive integer
//! columns belong to the PRIVATE INPUT DOMAIN, which allows checking domain
//! membership (Array SeriesDomain membership is currently unimplemented).
//! Observe the error through OnceFrame::collect. No quantitative privacy-loss
//! bound is claimed solely from this test.

use opendp::core::Domain;
use opendp::domains::LazyFrameDomain;
use opendp::error::Fallible;
use opendp::measurements::make_private_lazyframe;
use opendp::measures::MaxDivergence;
use opendp::metrics::{Bounds, FrameDistance, SymmetricDistance};
use opendp::polars::PrivacyNamespace;
use polars::prelude::*;

fn input_schema() -> Schema {
    Schema::from_iter([
        Field::new("k".into(), DataType::Int32),
        Field::new("idx".into(), DataType::Int64),
    ])
}

fn input_frame(private_index: i64) -> Fallible<LazyFrame> {
    Ok(df!("k" => [0_i32], "idx" => [private_index])?.lazy())
}

fn private_query(input: LazyFrame, null_on_oob: bool) -> Fallible<LazyFrame> {
    // Build a public constant Array(Int64, 2) with a single row.
    // A private int index selects from this public array.
    let public_array = Series::new("public_a".into(), &[5_i64, 6_i64])
        .implode()?
        .into_series()
        .cast(&DataType::Array(Box::new(DataType::Int64), 2))?;

    Ok(input
        .group_by([col("k")])
        .agg([
            lit(public_array)
                .arr()
                .get(col("idx"), null_on_oob)
                .first()
                .alias("picked"),
        ])
        // The private DP sum depends on the grouped array-get result:
        // projection pruning cannot remove the potentially failing expression.
        .select([
            col("picked")
                .dp()
                .sum((lit(0_i64), lit(10_i64)), Some(1.0))
                .alias("released"),
        ]))
}

#[test]
fn private_release_exposes_oob_status_for_get_false() -> Fallible<()> {
    let domain = LazyFrameDomain::new_from_schema(input_schema())?;
    let valid = input_frame(0)?;
    let invalid = input_frame(2)?;

    // No fixed-size Array input domain is needed: these are both valid
    // one-row (k, idx) frames, exactly one record replacement apart.
    assert!(domain.member(&valid)?);
    assert!(domain.member(&invalid)?);

    let measurement = make_private_lazyframe(
        domain,
        FrameDistance(SymmetricDistance),
        MaxDivergence,
        private_query(valid.clone(), false)?,
        Some(1.0),
        None,
    )?;

    // Replacing one record has symmetric distance two. Verify that the
    // measurement advertises a finite pure-DP privacy cost at this distance.
    let epsilon = measurement.map(&Bounds::from(2_u32))?;
    assert!(epsilon.is_finite(), "expected finite privacy cost: {epsilon:?}");

    let release = measurement.invoke(&valid)?.collect();
    assert!(release.is_ok(), "valid-index private release failed: {release:?}");

    let failure = measurement
        .invoke(&invalid)?
        .collect()
        .expect_err("out-of-bounds private index should be observable");
    assert!(
        failure.to_string().contains("out of bounds"),
        "unexpected error for private index 2: {failure:?}"
    );
    Ok(())
}

#[test]
fn private_release_get_true_does_not_raise_oob() -> Fallible<()> {
    let domain = LazyFrameDomain::new_from_schema(input_schema())?;
    let valid = input_frame(0)?;
    let invalid = input_frame(2)?;
    assert!(domain.member(&valid)?);
    assert!(domain.member(&invalid)?);

    let measurement = make_private_lazyframe(
        domain,
        FrameDistance(SymmetricDistance),
        MaxDivergence,
        private_query(valid.clone(), true)?,
        Some(1.0),
        None,
    )?;
    assert!(measurement.invoke(&valid)?.collect().is_ok());
    let release = measurement.invoke(&invalid)?.collect();
    assert!(
        release.is_ok(),
        "null_on_oob=true must not raise for invalid index: {release:?}"
    );
    Ok(())
}
