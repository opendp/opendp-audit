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

#[test]
fn patched_f64_max_three_node_counts_are_finite() -> Fallible<()> {
    // Even f64 intermediate summation overflows without normalization:
    // child_sum = f64::MAX + f64::MAX. Yet each reconciled leaf is 2M/3.
    for magnitude in [f64::MAX, -f64::MAX] {
        let post = make_consistent_b_ary_tree::<f64, f64>(2)?;
        let leaves = post.eval(&vec![magnitude; 3])?;
        let expected = magnitude * (2.0 / 3.0);
        assert_eq!(leaves.len(), 2);
        assert!(leaves.iter().all(|v| v.is_finite()), "{leaves:?}");
        for actual in leaves {
            assert!(
                ((actual - expected).abs() / expected.abs()) < 3e-15,
                "actual={actual}, expected={expected}"
            );
        }
    }
    Ok(())
}

#[test]
fn patched_f64_max_seven_node_counts_are_finite() -> Fallible<()> {
    // Fully symmetric height-3 tree with all seven noisy nodes equal to M.
    // Independent least-squares projection: 4 leaves each equal to 3M/7.
    let post = make_consistent_b_ary_tree::<f64, f64>(2)?;
    let leaves = post.eval(&vec![f64::MAX; 7])?;
    let expected = f64::MAX * (3.0 / 7.0);
    assert_eq!(leaves.len(), 4);
    for actual in leaves {
        assert!(actual.is_finite(), "{actual}");
        assert!(((actual - expected).abs() / expected) < 3e-15);
    }
    Ok(())
}

#[test]
fn patched_opposite_f64_extreme_leaves_cancel_without_nan() -> Fallible<()> {
    let post = make_consistent_b_ary_tree::<f64, f64>(2)?;
    // These three measurements are already consistent: root=0, children=±M.
    let leaves = post.eval(&vec![0.0, f64::MAX, -f64::MAX])?;
    assert_eq!(leaves, vec![f64::MAX, -f64::MAX]);
    Ok(())
}

fn four_leaf_least_squares_reference(observed: &[i128; 7]) -> [f64; 4] {
    // Rows of a complete 2-ary tree: root, two parents, four leaf nodes.
    const ROWS: [[f64; 4]; 7] = [
        [1.0, 1.0, 1.0, 1.0],
        [1.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 1.0],
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ];
    // Solve AᵀAx=Aᵀy independently with Gauss-Jordan elimination.
    let mut normal = [[0.0_f64; 4]; 4];
    let mut rhs = [0.0_f64; 4];
    for (row, &value) in ROWS.iter().zip(observed.iter()) {
        for i in 0..4 {
            rhs[i] += row[i] * (value as f64);
            for j in 0..4 {
                normal[i][j] += row[i] * row[j];
            }
        }
    }
    for pivot in 0..4 {
        let selected = (pivot..4)
            .max_by(|&a, &b| normal[a][pivot].abs().total_cmp(&normal[b][pivot].abs()))
            .unwrap();
        normal.swap(pivot, selected);
        rhs.swap(pivot, selected);
        let diagonal = normal[pivot][pivot];
        assert!(diagonal.abs() > 0.01);
        for j in pivot..4 {
            normal[pivot][j] /= diagonal;
        }
        rhs[pivot] /= diagonal;
        for i in 0..4 {
            if i == pivot { continue; }
            let weight = normal[i][pivot];
            for j in pivot..4 {
                normal[i][j] -= weight * normal[pivot][j];
            }
            rhs[i] -= weight * rhs[pivot];
        }
    }
    rhs
}

#[test]
fn patched_200_complete_tree_inputs_match_independent_least_squares() -> Fallible<()> {
    let post = make_consistent_b_ary_tree::<i128, f64>(2)?;
    let mut state = 0x1234_5678_9abc_def0_u64;
    for trial in 0..200 {
        let mut observed = [0_i128; 7];
        for value in &mut observed {
            // Fixed-seed xorshift: reproducible diverse signed counts.
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            *value = (state % 601) as i128 - 300;
        }
        let expected = four_leaf_least_squares_reference(&observed);
        let actual = post.eval(&observed.to_vec())?;
        assert_eq!(actual.len(), 4);
        for i in 0..4 {
            assert!(
                (actual[i] - expected[i]).abs() < 1.0e-9,
                "trial={trial}, leaf={i}, actual={}, oracle={}",
                actual[i], expected[i]
            );
        }
    }
    Ok(())
}

#[test]
fn normalized_patch_loses_small_leaves_of_consistent_mixed_scale_tree() -> Fallible<()> {
    // Characterization test of an UNSOLVED regression in the CI-only patch.
    // The exact input is internally consistent, so its unique LS projection
    // is the original leaf vector [M, 0, s, -s].
    let m = 2.0_f64.powi(1023);
    let s = 1.0e-20_f64;
    let normalized_small = s / m;
    assert_eq!(normalized_small, 0.0, "small leaf must underflow when scaled");
    let post = make_consistent_b_ary_tree::<f64, f64>(2)?;
    let leaves = post.eval(&vec![m, m, 0.0, m, 0.0, s, -s])?;
    assert_eq!(leaves.len(), 4);
    assert_eq!(leaves, vec![m, 0.0, 0.0, 0.0]);
    assert_ne!(leaves, vec![m, 0.0, s, -s]);
    Ok(())
}

#[test]
fn normalized_patch_also_loses_small_leaves_of_height_four_tree() -> Fallible<()> {
    // Same defect in a four-layer tree with eight leaves.
    let m = 2.0_f64.powi(1023);
    let s = 1.0e-20_f64;
    let post = make_consistent_b_ary_tree::<f64, f64>(2)?;
    let observed = vec![
        m, m, 0.0, m, 0.0, 0.0, 0.0,
        m, 0.0, 0.0, 0.0, s, -s, 0.0, 0.0,
    ];
    let leaves = post.eval(&observed)?;
    assert_eq!(leaves, vec![m, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]);
    assert_ne!(leaves, vec![m, 0.0, 0.0, 0.0, s, -s, 0.0, 0.0]);
    Ok(())
}
