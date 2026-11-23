---
schema_version: 1
source: rust/src/transformations/b_ary_tree/consistency_postprocessor/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/b_ary_tree/consistency_postprocessor/mod.rs`

## Scope and assumptions

- **Audit scope:** `make_consistent_b_ary_tree`, the public, non-deprecated postprocessor that converts noisy breadth-first b-ary counts into reconciled leaves. Reviewed its finite-precision bottom-up/top-down arithmetic, missing-leaf handling, output shape, and supported `RoundCast<i128> for f32` input type.
- **Invariants:** For finite integer inputs for which the real-arithmetic consistent leaf estimates are finite and representable in the requested floating output type, processing should yield finite leaves or an explicit error instead of silently returning NaN. Missing leaves should have zero variance and should not appear as released leaves.
- **Assumptions:** The tree is encoded breadth first, is complete except for trailing missing nodes, and uses standard IEEE-754 `f32` operations. Ordinary integer values are accepted by `RoundCast` as documented. This does **not** assert finite outputs for arbitrary invalid floating inputs or privacy accounting.
- **Pinned source:** [postprocessor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/b_ary_tree/consistency_postprocessor/mod.rs), [numeric casts](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/cast/mod.rs), and [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/b_ary_tree/test.rs).
- **Related records:** [Audit candidate #33](https://github.com/opendp/opendp-audit/issues/33), [audit task #31](https://github.com/opendp/opendp-audit/issues/31), and [prior b-ary tree construction audit](https://github.com/opendp/opendp-audit/blob/main/source/rust/src/transformations/b_ary_tree/mod.rs.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_consistent_b_ary_tree` | correctness/f32-intermediate-overflow | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Finite input, NaN leaves](#finite-input-nan-leaves) |
| `make_consistent_b_ary_tree` | correctness/incomplete-tree-padding | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Padding and output length](#padding-and-output-length) |

## Analysis

### Finite input, NaN leaves

**Finding:** The function can yield `Ok([NaN, NaN])` instead of finite leaves for a valid three-node tree containing only finite integer counts. For `TIA = i128`, `TOA = f32`, `branching_factor = 2`, invoke the postprocessor on `[i128::MAX, i128::MAX, i128::MAX]` (root, left child, right child).

The [`RoundCast` implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/cast/mod.rs) accepts integer-to-float conversion through `NumCast`. `i128::MAX` rounds to `2^127 ≈ 1.7014118346046923e38`, a **finite** `f32`. The bottom-up `child_val = tree[1..3].iter().sum()` adds those two values in `f32` and overflows to `+infinity`. With child variance 2 and parent variance 1, the weighted parent becomes `+infinity`. The top-down `correction = h_b[0] - sum(children)` evaluates `infinity - infinity`, producing NaN. That correction propagates into both leaf values; the closure returns `Ok` without validating output finiteness.

The expected **real-arithmetic** variance-weighted parent is `(2/3)M + (1/3)(2M) = (4/3)M`, and its child correction is `(4/3)M - 2M = -(2/3)M`, divided equally between the two children. Thus the corrected leaves are `2M/3`, approximately `1.134274556e38`, which fits in finite binary32. The failure is avoidable intermediate overflow, not an inherently unrepresentable result.

**Independent execution:** A Python 3 **standard-library** binary32 model using `struct.pack/unpack` after each individual `f32` operation returned `[nan, nan]` for this input. It also returned `[1, 2]` for a small consistent input `[3, 1, 2]`. The dependency-free [regression test](https://github.com/opendp/opendp-audit/blob/main/tools/tests/test_bary_consistency_f32_model.py) retains the demonstration. **Not executed:** Compiled OpenDP Rust, native `RoundCast`, or FFI. This distinction is why [issue #33](https://github.com/opendp/opendp-audit/issues/33) is marked **Candidate** pending an upstream invocation test.

**Conclusion:** A high-confidence source-supported numerical utility/correctness defect, not a DP violation. The `Audited` scope is only this explicit `f32` overflow path and the associated arithmetic model, not full postprocessor correctness.

### Native Rust arithmetic regression

A second, independent regression was compiled with native `rustc --edition=2021 --test` in the audit repository's CI. The [std-only reproducer](https://github.com/opendp/opendp-audit/blob/main/tools/tests/bary_consistency_float_overflow.rs) copies the **three-node bottom-up weighted average and top-down correction arithmetic** from the pinned implementation, but uses primitive `f32` operations directly rather than importing OpenDP.

The three Rust tests check that `i128::MAX as f32` is finite but the sum of two such values overflows to infinity and produces NaN final leaves; that the mathematically expected `(2/3)M` leaf value fits within `f32`; and that small consistent counts `[3, 1, 2]` stay unchanged. All three tests passed in [GitHub Actions run #45100869596](https://github.com/opendp/opendp-audit/actions/runs/45100869596), together with the audit repository's existing tests and report validator. The reproducer was introduced in [commit `d8fe885`](https://github.com/opendp/opendp-audit/commit/d8fe885437b40bbeba7157642634bf7f0069d3c4).

This **confirms the native Rust primitive arithmetic path**, independently of the prior Python model, but is **not a compiled OpenDP integration test**. The upstream `make_consistent_b_ary_tree` invocation, `RoundCast` dispatch, and FFI conversions remain unexecuted, so the issue's verification status remains **Candidate**.

### Padding and output length

The function validates `branching_factor >= 2` and rejects an empty vector at invocation. It computes the minimum complete-tree node count covering `arg.len()` with checked node arithmetic, appends zero-valued phantom nodes, and marks missing last-layer and empty-subtree variances as zero. The final slice excludes phantom leaves. The model's basic controls include a one-node tree, a two-node partially missing tree, and two incomplete three-layer trees; these returned finite leaves with the expected lengths.

The code uses inverses of summed child variance, and a top-down correction distributed over child variances. Its intended zero-variance branches are visible in the source, but the model has not exhaustively enumerated all shapes, exactness, or extreme finite input types.

**Conclusion:** No additional padding or shape defect established in the checked controls; **Partial** because the full input-shape and numeric boundary space was not verified.

## Findings

**[Issue #33](https://github.com/opendp/opendp-audit/issues/33):** Finite `i128` inputs can produce NaN `f32` leaves through intermediate arithmetic overflow. Verification: source-supported candidate with an independently executed binary32 control-flow model; native OpenDP execution pending. **Upstream disposition: Unreported**; searches found no matching upstream issue or corrective PR. Earlier [PR #3068](https://github.com/opendp/opendp/pull/3068) fixed a different *tree-construction* issue.

## Next checks

- Compile the actual `make_consistent_b_ary_tree::<i128, f32>(2)` invocation, assert that the current output is nonfinite, and test a finite-output remedy or a structured overflow error.
- Test equivalent `f64` numeric boundaries, incomplete trees with absent children, and exceptional conversions, ideally with property-based checks of reconciled parent/child consistency.
- Review whether intermediate rescaling, wider internal arithmetic, or overflow detection best preserves utility without changing the deterministic postprocessing privacy guarantee.
