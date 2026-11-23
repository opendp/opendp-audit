//! Experimental wide-intermediate consistency tests against a *locally patched*
//! checkout of pinned OpenDP ef1a238634d6196b01a1a1e77d3d5ad2340e3094.
//!
//! This never modifies the upstream repository. See issue #33.
//! The separate baseline integration test documents the original NaN failure.

use opendp::error::Fallible;
use opendp::transformations::make_consistent_b_ary_tree;

#[test]
fn patched_extreme_i128_counts_return_finite_f32_leaves() -> Fallible<()> {
    let post = make_consistent_b_ary_tree::<i128, f32>(2)?;
    let leaves = post.eval(&vec![i128::MAX; 3])?;
    let exact_reference = (i128::MAX as f64) * (2.0 / 3.0);
    let expected = exact_reference as f32;
    assert_eq!(leaves.len(), 2);
    assert!(leaves.iter().all(|x| x.is_finite()), "{leaves:?}");
    for actual in leaves {
        let relative_error = ((actual as f64) - exact_reference).abs() / exact_reference;
        assert!(
            relative_error < 2.0e-7,
            "actual={actual}, expected={expected}, relative_error={relative_error}"
        );
    }
    Ok(())
}

#[test]
fn patched_small_complete_tree_stays_consistent() -> Fallible<()> {
    let post = make_consistent_b_ary_tree::<i128, f32>(2)?;
    assert_eq!(post.eval(&vec![3, 1, 2])?, vec![1.0, 2.0]);
    assert_eq!(post.eval(&vec![6, 2, 4])?, vec![2.0, 4.0]);
    Ok(())
}

#[test]
fn patched_small_incomplete_trees_have_finite_output_and_expected_shape() -> Fallible<()> {
    let post = make_consistent_b_ary_tree::<i128, f32>(2)?;
    assert_eq!(post.eval(&vec![7])?, vec![7.0]);
    assert_eq!(post.eval(&vec![10, 7])?, vec![8.5]);
    for values in [
        vec![10, 7, 0, 5],
        vec![10, 7, 0, 5, 0],
        vec![10, 7, 0, 5, 0, 0],
    ] {
        let output = post.eval(&values)?;
        assert!(output.iter().all(|v| v.is_finite()), "{output:?}");
    }
    Ok(())
}

#[test]
fn patched_f64_output_has_finite_extreme_i128_leaves() -> Fallible<()> {
    let post = make_consistent_b_ary_tree::<i128, f64>(2)?;
    let leaves = post.eval(&vec![i128::MAX; 3])?;
    let expected = (i128::MAX as f64) * (2.0 / 3.0);
    assert_eq!(leaves.len(), 2);
    assert!(leaves.iter().all(|v| v.is_finite()), "{leaves:?}");
    for actual in leaves {
        assert!(((actual - expected).abs() / expected) < 2.0e-15);
    }
    Ok(())
}
