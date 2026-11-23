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

#[test]
fn f64_max_to_f64_returns_nan_leaves_in_pinned_opendp() -> Fallible<()> {
    // This variant bypasses an integer-to-f32 cast: even f64 intermediate
    // child sums overflow, although each mathematically projected leaf is
    // (2/3)*f64::MAX, which is finite.
    let expected_leaf = f64::MAX * (2.0 / 3.0);
    assert!(expected_leaf.is_finite());
    let post = make_consistent_b_ary_tree::<f64, f64>(2)?;
    let leaves = post.eval(&vec![f64::MAX; 3])?;
    assert_eq!(leaves.len(), 2);
    assert!(
        leaves.iter().all(|x| x.is_nan()),
        "original pinned implementation unexpectedly changed: {leaves:?}"
    );
    Ok(())
}

#[test]
fn already_consistent_mixed_f64_scales_are_preserved_upstream() -> Fallible<()> {
    // Exact, already-consistent breadth-first binary tree:
    // root=M; parents=(M,0); leaves=(M,0,s,-s).
    // Every parent equals the sum of its children in real arithmetic
    // AND in f64. The least-squares projection must be the identity.
    let m = f64::MAX;
    let s = 1.0e-20_f64;
    assert!(s.is_normal());
    let post = make_consistent_b_ary_tree::<f64, f64>(2)?;
    let leaves = post.eval(&vec![m, m, 0.0, m, 0.0, s, -s])?;
    assert_eq!(leaves, vec![m, 0.0, s, -s]);
    Ok(())
}

#[test]
fn already_consistent_mixed_f64_scales_height_four_upstream() -> Fallible<()> {
    // A 4-layer binary tree with eight leaves. The right grandchild
    // subtree has small canceling leaves while the leftmost leaf is huge.
    let m = f64::MAX;
    let s = 1.0e-20_f64;
    let post = make_consistent_b_ary_tree::<f64, f64>(2)?;
    let observed = vec![
        m, m, 0.0, m, 0.0, 0.0, 0.0,
        m, 0.0, 0.0, 0.0, s, -s, 0.0, 0.0,
    ];
    let leaves = post.eval(&observed)?;
    assert_eq!(leaves, vec![m, 0.0, 0.0, 0.0, s, -s, 0.0, 0.0]);
    Ok(())
}
