//! Direct integration tests against the pinned OpenDP crate.
//!
//! Unlike tools/tests/bary_consistency_float_overflow.rs, this imports the
//! actual OpenDP public constructor and evaluates its returned Function.
//! Audit issue: https://github.com/opendp/opendp-audit/issues/33
//! Target upstream revision: ef1a238634d6196b01a1a1e77d3d5ad2340e3094

use opendp::error::Fallible;
use opendp::transformations::make_consistent_b_ary_tree;

#[test]
fn i128_max_to_f32_returns_nan_leaves_in_pinned_opendp() -> Fallible<()> {
    let post = make_consistent_b_ary_tree::<i128, f32>(2)?;
    let leaves = post.eval(&vec![i128::MAX; 3])?;
    assert_eq!(leaves.len(), 2);
    assert!(
        leaves.iter().all(|v| v.is_nan()),
        "expected NaN leaves from current upstream implementation: {leaves:?}"
    );
    Ok(())
}

#[test]
fn small_consistent_counts_remain_unchanged() -> Fallible<()> {
    let post = make_consistent_b_ary_tree::<i128, f32>(2)?;
    assert_eq!(post.eval(&vec![3, 1, 2])?, vec![1.0, 2.0]);
    Ok(())
}

#[test]
fn expected_real_arithmetic_leaves_are_finite() {
    // The exact tree projection for [M, M, M] is [2M/3, 2M/3].
    // f64 easily represents these values; this reference only checks
    // representability in f32, not exact roundtrip equality.
    let m = i128::MAX as f64;
    let exact_leaf_reference = m * (2.0 / 3.0);
    assert!(exact_leaf_reference.is_finite());
    assert!((exact_leaf_reference as f32).is_finite());
}
