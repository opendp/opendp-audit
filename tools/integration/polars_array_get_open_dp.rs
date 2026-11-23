//! Compiled OpenDP group-by constructor regression for audit issue #71.
//! Run against both pinned OpenDP main and the unmerged proposed PR #3155.
//! The public fixed-width Array schema is sufficient to check constructor validation;
//! grouped execution with actual private index values is tested by the companion
//! pinned Polars runtime regression.

use opendp::core::Transformation;
use opendp::domains::LazyFrameDomain;
use opendp::error::Fallible;
use opendp::metrics::{FrameDistance, SymmetricDistance};
use opendp::transformations::make_stable_lazyframe;
use polars::prelude::*;

#[test]
fn group_by_array_get_false_constructor_gate() -> Fallible<()> {
    let schema = Schema::from_iter([
        Field::new("k".into(), DataType::Int32),
        Field::new("a".into(), DataType::Array(Box::new(DataType::Int64), 2)),
        Field::new("idx".into(), DataType::Int64),
    ]);
    let domain = LazyFrameDomain::new_from_schema(schema.clone())?;
    let input = DataFrame::empty_with_schema(&schema).lazy();
    let query = input.group_by([col("k")]).agg([
        col("a")
            .arr()
            .get(col("idx"), false)
            .first()
            .alias("picked"),
    ]);
    let constructed: Fallible<
        Transformation<_, _, _, FrameDistance<SymmetricDistance>>,
    > = make_stable_lazyframe(domain, FrameDistance(SymmetricDistance), query);
    let expect_rejection = std::env::var("EXPECT_REJECTION").as_deref() == Ok("1");
    let rejected = constructed.is_err();
    assert_eq!(
        rejected,
        expect_rejection,
        "pinned upstream accept/reject mismatch: {:?}",
        constructed.err()
    );
    Ok(())
}
