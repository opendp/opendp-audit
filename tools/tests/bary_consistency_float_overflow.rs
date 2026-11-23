//! Native Rust arithmetic reproducer for opendp/opendp-audit#33.
//!
//! Mirrors the *three-node* arithmetic in OpenDP's
//! rust/src/transformations/b_ary_tree/consistency_postprocessor/mod.rs
//! at ef1a238634d6196b01a1a1e77d3d5ad2340e3094.
//! This is NOT a compiled OpenDP integration test: it uses only std and
//! does not invoke make_consistent_b_ary_tree itself.

#![forbid(unsafe_code)]

fn three_node_consistent_leaves(nodes: [i128; 3]) -> [f32; 2] {
    // RoundCast<i128> for f32 currently delegates to NumCast.
    let mut tree = nodes.map(|node| node as f32);
    let mut vars = [1.0_f32; 3];

    // Bottom-up inverse-variance scan, equivalent to the one-parent loop.
    let child_var = vars[1..].iter().copied().sum::<f32>();
    let child_val = tree[1..].iter().copied().sum::<f32>();
    let mut alpha = vars[0].recip();
    vars[0] = (vars[0].recip() + child_var.recip()).recip();
    alpha *= vars[0];
    tree[0] = alpha * tree[0] + (1.0 - alpha) * child_val;

    // Top-down correction; both children have variance one.
    let mut reconciled = tree;
    let correction = reconciled[0] - tree[1..].iter().copied().sum::<f32>();
    if correction != 0.0 {
        let sum_var = vars[1..].iter().copied().sum::<f32>();
        for idx in 1..3 {
            reconciled[idx] += correction * vars[idx] / sum_var;
        }
    }
    [reconciled[1], reconciled[2]]
}

#[test]
fn extreme_i128_counts_produce_nan_via_f32_intermediate_overflow() {
    let m = i128::MAX as f32;
    assert!(m.is_finite(), "initial i128-to-f32 cast is finite");
    assert!((m + m).is_infinite(), "child sum exceeds f32::MAX");

    let leaves = three_node_consistent_leaves([i128::MAX; 3]);
    assert!(
        leaves.iter().all(|value| value.is_nan()),
        "source-mirrored arithmetic should yield NaN leaves: {leaves:?}"
    );
}

#[test]
fn exact_real_leaf_value_would_fit_f32() {
    // In real arithmetic, each corrected leaf is (2/3)*i128::MAX.
    // Use f64 as a wide reference for this small witness, not as a general
    // proof that f64 intermediate arithmetic is always safe.
    let expected_leaf = (i128::MAX as f64) * (2.0 / 3.0);
    assert!(expected_leaf.is_finite());
    assert!((expected_leaf as f32).is_finite());
    assert!(expected_leaf > 0.0);
}

#[test]
fn small_consistent_input_is_unchanged() {
    assert_eq!(three_node_consistent_leaves([3, 1, 2]), [1.0, 2.0]);
}
