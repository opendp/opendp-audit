"""Experimentally normalize large b-ary values in f64 to avoid intermediate overflow.

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
    print("Applied experimental normalized-f64 fix to local CI checkout")


if __name__ == "__main__":
    main()
