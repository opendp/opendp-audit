"""Experimentally widen b-ary consistency intermediate arithmetic to f64.

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

    source = replace_exact(
        source,
        "use opendp_derive::bootstrap;",
        "use num::ToPrimitive;\nuse opendp_derive::bootstrap;",
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
            .map(|v| {
                let rounded = TOA::round_cast(v)?;
                rounded
                    .to_f64()
                    .ok_or_else(|| err!(FailedFunction, "cannot widen input to f64"))
            })
            .chain((0..zero_leaves).map(|_| Ok(0.0_f64)))
            .collect::<Fallible<_>>()?;""",
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
                let out = TOA::round_cast(v)?;
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
    print("Applied experimental wide-intermediate fix to local CI checkout")


if __name__ == "__main__":
    main()
