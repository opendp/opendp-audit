//! End-to-end native OpenDP release regression for audit issue #71.
//!
//! Pinned OpenDP main ef1a238634d6196b01a1a1e77d3d5ad2340e3094
//! Polars 0.52.0 / py-1.36.1 as patched by the pinned OpenDP Cargo.toml.
//!
//! Keep the possibly fallible group-by expression live by selecting a private
//! noisy SUM of its output. Test errors at OnceFrame::collect, not just
//! constructor admission. This test does not establish a quantitative
//! epsilon/delta privacy loss.

use opendp::domains::LazyFrameDomain;
use opendp::error::Fallible;
use opendp::measurements::make_private_lazyframe;
use opendp::measures::MaxDivergence;
use opendp::metrics::{FrameDistance, SymmetricDistance};
use opendp::polars::PrivacyNamespace;
use polars::prelude::*;

fn public_schema() -> Schema {
    Schema::from_iter([
        Field::new("k".into(), DataType::Int32),
        Field::new("a".into(), DataType::Array(Box::new(DataType::Int64), 2)),
        Field::new("idx".into(), DataType::Int64),
    ])
}

fn input_frame(private_index: i64) -> Fallible<LazyFrame> {
    // Impode the primitive elements to List(Int64), then cast to a fixed-width
    // Array(Int64, 2), just as in the pinned Polars array indexing tests.
    let array = Series::new("a".into(), &[5_i64, 6_i64])
        .implode()?
        .into_series()
        .cast(&DataType::Array(Box::new(DataType::Int64), 2))?;
    let mut df = df!("k" => [0_i32], "idx" => [private_index])?;
    df.with_column(array)?;
    Ok(df.lazy())
}

fn private_query(input: LazyFrame, null_on_oob: bool) -> LazyFrame {
    input
        .group_by([col("k")])
        .agg([
            col("a")
                .arr()
                .get(col("idx"), null_on_oob)
                .first()
                .alias("picked"),
        ])
        // This private DP sum depends on the grouped array-get result:
        // projection pruning cannot remove the potentially failing expression.
        .select([
            col("picked")
                .dp()
                .sum((lit(0_i64), lit(10_i64)), Some(1.0))
                .alias("released"),
        ])
}

#[test]
fn private_release_exposes_oob_status_for_get_false() -> Fallible<()> {
    let domain = LazyFrameDomain::new_from_schema(public_schema())?;
    let valid = input_frame(0)?;
    let invalid = input_frame(2)?;

    let measurement = make_private_lazyframe(
        domain,
        FrameDistance(SymmetricDistance),
        MaxDivergence,
        private_query(valid.clone(), false),
        Some(1.0),
        None,
    )?;

    // Two neighboring private datasets have the same public schema, shape,
    // key and array values. Only the index changes from 0 to 2.
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
    let domain = LazyFrameDomain::new_from_schema(public_schema())?;
    let valid = input_frame(0)?;
    let invalid = input_frame(2)?;

    let measurement = make_private_lazyframe(
        domain,
        FrameDistance(SymmetricDistance),
        MaxDivergence,
        private_query(valid.clone(), true),
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
