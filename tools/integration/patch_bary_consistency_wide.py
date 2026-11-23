"""Experimentally reconcile lossy-scale trees with exact rational arithmetic.

Applies only to a checkout of the pinned upstream OpenDP revision in CI.
Never commits changes to opendp/opendp. Every substitution is fail-closed.
"""

import pathlib
import sys


def replace_exact(text, before, after, expected=1):
    count = text.count(before)
    if count != expected:
        raise RuntimeError(
            f"Expected {expected} copies of {before!r}, found {count}; "
            "refusing to patch a different OpenDP source revision"
        )
    return text.replace(before, after)


def main():
    path = pathlib.Path(sys.argv[1])
    original = path.read_text()
    source = original

    # Direct input-to-f64 casting avoids the original range loss from
    # first casting u128::MAX to f32 (which produces infinity).
    source = replace_exact(
        source,
        "    TOA: Float + RoundCast<TIA>,\n{",
        "    TOA: Float + RoundCast<TIA>,\n    f64: RoundCast<TIA>,\n{",
    )
    source = replace_exact(
        source,
        "let mut vars = vec![TOA::one(); num_nodes];",
        "let mut vars = vec![1.0_f64; num_nodes];",
    )
    source = replace_exact(
        source,
        """let mut tree: Vec<TOA> = arg
            .iter()
            .cloned()
            .map(|v| TOA::round_cast(v))
            .chain((0..zero_leaves).map(|_| Ok(TOA::zero())))
            .collect::<Fallible<_>>()?;""",
        """let mut tree: Vec<f64> = arg
            .iter()
            .cloned()
            .map(f64::round_cast)
            .chain((0..zero_leaves).map(|_| Ok(0.0_f64)))
            .collect::<Fallible<_>>()?;""",
    )
    # Avoid overflowing *f64* intermediate sums as well. Keep normal-scale
    # inputs untouched; rescale only if even a conservative number-of-nodes
    # sum bound could cross the largest finite binary64 value.
    source = replace_exact(
        source,
        ".collect::<Fallible<_>>()?;\n\n        // zero out all zero variance zero nodes on the tree",
        """.collect::<Fallible<_>>()?;

        if !tree.iter().all(|v| v.is_finite()) {
            return fallible!(FailedFunction, "input atom is nonfinite");
        }
        let max_abs = tree.iter().copied().map(f64::abs).fold(0.0_f64, f64::max);
        let scale = if max_abs > f64::MAX / (4.0 * num_nodes as f64) {
            max_abs
        } else {
            1.0_f64
        };
        if scale != 1.0 {
            // The scaled representation may lose tiny but valid values.
            // When that happens, recognize a complete EXACTLY consistent
            // tree using arbitrary-precision rational representations of
            // the input floats. Its LS projection is the original leaves,
            // so there is no need to scale or reconcile it.
            let lossy = tree.iter().any(|v| (v / scale) * scale != *v);
            if lossy {
                let leaf_start = num_nodes_from_num_layers(layers - 1, branching_factor);
                // Experimental exact-rational fallback: perform weighted
                // least-squares reconciliation without global rescaling.
                // This is intentionally a slow, audit-only reference path.
                fn ratio_to_f64(v: &num::BigRational) -> Option<f64> {
                    use num::{Signed, Zero};
                    if v.is_zero() { return Some(0.0); }
                    fn high_bytes(bytes: &[u8]) -> (f64, i32) {
                        let count = bytes.len().min(8);
                        let mut head: u64 = 0;
                        for byte in &bytes[..count] {
                            head = (head << 8) | u64::from(*byte);
                        }
                        (head as f64, ((bytes.len() - count) * 8) as i32)
                    }
                    let (_, n_bytes) = v.numer().abs().to_bytes_be();
                    let (_, d_bytes) = v.denom().abs().to_bytes_be();
                    let (n_head, n_exp) = high_bytes(&n_bytes);
                    let (d_head, d_exp) = high_bytes(&d_bytes);
                    let mut value = if v.numer().is_negative() { -1.0 } else { 1.0 }
                        * (n_head / d_head);
                    let mut exp = n_exp - d_exp;
                    while exp > 0 {
                        let step = exp.min(512);
                        value *= 2.0_f64.powi(step);
                        if !value.is_finite() { return None; }
                        exp -= step;
                    }
                    while exp < 0 {
                        let step = (-exp).min(512);
                        value /= 2.0_f64.powi(step);
                        exp += step;
                    }
                    Some(value)
                }
                use num::{One, Zero};
                let mut exact_tree = tree
                    .iter()
                    .copied()
                    .map(num::BigRational::from_float)
                    .collect::<Option<Vec<_>>>()
                    .ok_or_else(|| err!(FailedFunction, "cannot rationalize finite input"))?;
                let mut exact_vars = vec![num::BigRational::one(); num_nodes];
                for l in 0..layers {
                    let zeros = zero_leaves / branching_factor.pow((layers - l - 1) as u32);
                    let end = num_nodes_from_num_layers(l + 1, branching_factor);
                    exact_vars[end - zeros..end].fill(num::BigRational::zero());
                    exact_tree[end - zeros..end].fill(num::BigRational::zero());
                }
                // Exact bottom-up inverse-variance-weighted reconciliation.
                for l in (0..layers - 1).rev() {
                    let start = num_nodes_from_num_layers(l, branching_factor);
                    for offset in 0..branching_factor.pow(l as u32) {
                        let i = start + offset;
                        if exact_vars[i].is_zero() { continue; }
                        let children = i * branching_factor + 1
                            ..i * branching_factor + 1 + branching_factor;
                        let child_var: num::BigRational =
                            exact_vars[children.clone()].iter().cloned().sum();
                        let child_sum: num::BigRational =
                            exact_tree[children].iter().cloned().sum();
                        let old_var = exact_vars[i].clone();
                        let total = &old_var + &child_var;
                        if total.is_zero() {
                            return fallible!(FailedFunction, "zero total rational variance");
                        }
                        let alpha = &child_var / &total;
                        exact_vars[i] = old_var * &alpha;
                        exact_tree[i] = &alpha * &exact_tree[i]
                            + (num::BigRational::one() - alpha) * child_sum;
                    }
                }
                // Exact top-down correction.
                let mut exact_out = exact_tree.clone();
                for l in 0..layers - 1 {
                    let start = num_nodes_from_num_layers(l, branching_factor);
                    for offset in 0..branching_factor.pow(l as u32) {
                        let i = start + offset;
                        let children = i * branching_factor + 1
                            ..i * branching_factor + 1 + branching_factor;
                        let child_sum: num::BigRational =
                            exact_tree[children.clone()].iter().cloned().sum();
                        let correction = &exact_out[i] - child_sum;
                        if correction == num::BigRational::zero() { continue; }
                        let total_var: num::BigRational =
                            exact_vars[children.clone()].iter().cloned().sum();
                        if total_var.is_zero() {
                            return fallible!(FailedFunction, "zero child rational variance");
                        }
                        for c in children {
                            exact_out[c] += &correction * &exact_vars[c] / &total_var;
                        }
                    }
                }
                let leaf_start = num_nodes_from_num_layers(layers - 1, branching_factor);
                let leaf_end = num_nodes_from_num_layers(layers, branching_factor) - zero_leaves;
                return exact_out[leaf_start..leaf_end]
                    .iter()
                    .map(|v| {
                        let value = ratio_to_f64(v).ok_or_else(|| {
                            err!(FailedFunction, "rational projected leaf is not finite f64")
                        })?;
                        let out = TOA::round_cast(value)?;
                        if !out.is_finite() {
                            return fallible!(FailedFunction, "rational leaf overflows output");
                        }
                        Ok(out)
                    })
                    .collect::<Fallible<Vec<TOA>>>();

            }
            tree.iter_mut().for_each(|v| *v /= scale);
        }

        // zero out all zero variance zero nodes on the tree""",
    )
    source = replace_exact(
        source, ".fill(TOA::zero());", ".fill(0.0_f64);", expected=2
    )
    source = replace_exact(
        source, "if vars[i].is_zero() {", "if vars[i] == 0.0 {"
    )
    source = replace_exact(
        source, "let child_var: TOA =", "let child_var: f64 ="
    )
    source = replace_exact(
        source, "let child_val: TOA =", "let child_val: f64 ="
    )
    source = replace_exact(
        source,
        "(TOA::one() - alpha) * child_val",
        "(1.0_f64 - alpha) * child_val",
    )
    source = replace_exact(
        source,
        "let correction = h_b[i] - tree[child_slice.clone()].iter().sum();",
        "let correction: f64 = h_b[i] - tree[child_slice.clone()].iter().copied().sum::<f64>();",
    )
    source = replace_exact(
        source,
        "if correction.is_zero() {",
        "if correction == 0.0 {",
    )
    source = replace_exact(
        source,
        "let sum_var = child_vars.iter().sum();",
        "let sum_var: f64 = child_vars.iter().sum();",
    )
    source = replace_exact(
        source,
        "Ok(h_b[leaf_start..leaf_end].to_vec())",
        """h_b[leaf_start..leaf_end]
            .iter()
            .cloned()
            .map(|v| {
                if !v.is_finite() {
                    return fallible!(FailedFunction, "nonfinite reconciled leaf");
                }
                let out = TOA::round_cast(v * scale)?;
                if !out.is_finite() {
                    return fallible!(FailedFunction, "reconciled leaf overflows output type");
                }
                Ok(out)
            })
            .collect::<Fallible<Vec<TOA>>>()""",
    )
    if source == original:
        raise RuntimeError("Patch made no changes")
    path.write_text(source)
    print("Applied experimental exact-rational fallback and guarded f64 normalization")


if __name__ == "__main__":
    main()
