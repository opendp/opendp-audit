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

#[test]
fn patched_u128_max_direct_to_f64_avoids_initial_f32_infinity() -> Fallible<()> {
    // u128::MAX cannot round to finite f32, but 2*M/3 can.
    let max = u128::MAX;
    assert!(!(max as f32).is_finite());
    let expected = (max as f64) * (2.0 / 3.0);
    assert!((expected as f32).is_finite());

    let post = make_consistent_b_ary_tree::<u128, f32>(2)?;
    let leaves = post.eval(&vec![max; 3])?;
    assert_eq!(leaves.len(), 2);
    assert!(leaves.iter().all(|v| v.is_finite()), "{leaves:?}");
    for leaf in leaves {
        let relative_error = ((leaf as f64) - expected).abs() / expected;
        assert!(relative_error < 2e-7, "{leaf} relative_error={relative_error}");
    }
    Ok(())
}

#[test]
fn patched_output_cast_reports_unrepresentable_f32_leaf() -> Fallible<()> {
    // A one-node tree returns the original single leaf. It does not fit in
    // finite f32, so the postprocessor must return Err, not Ok([infinity]).
    let post = make_consistent_b_ary_tree::<u128, f32>(2)?;
    assert!(post.eval(&vec![u128::MAX]).is_err());
    Ok(())
}

#[test]
fn patched_signed_i128_min_and_single_leaf_remain_finite() -> Fallible<()> {
    let post = make_consistent_b_ary_tree::<i128, f32>(2)?;
    let values = post.eval(&vec![i128::MIN; 3])?;
    assert_eq!(values.len(), 2);
    assert!(values.iter().all(|v| v.is_finite()), "{values:?}");
    let reference = (i128::MIN as f64) * (2.0 / 3.0);
    assert!((values[0] as f64 - reference).abs() / reference.abs() < 2e-7);

    assert_eq!(post.eval(&vec![0])?, vec![0.0]);
    Ok(())
}
