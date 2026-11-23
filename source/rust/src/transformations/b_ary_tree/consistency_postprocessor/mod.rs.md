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
| `make_consistent_b_ary_tree` | correctness/f64-intermediate-overflow | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Native f64 maximum reproduction](#native-f64-maximum-reproduction) |

## Analysis

### Finite input, NaN leaves

**Finding:** The function can yield `Ok([NaN, NaN])` instead of finite leaves for a valid three-node tree containing only finite integer counts. For `TIA = i128`, `TOA = f32`, `branching_factor = 2`, invoke the postprocessor on `[i128::MAX, i128::MAX, i128::MAX]` (root, left child, right child).

The [`RoundCast` implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/cast/mod.rs) accepts integer-to-float conversion through `NumCast`. `i128::MAX` rounds to `2^127 ≈ 1.7014118346046923e38`, a **finite** `f32`. The bottom-up `child_val = tree[1..3].iter().sum()` adds those two values in `f32` and overflows to `+infinity`. With child variance 2 and parent variance 1, the weighted parent becomes `+infinity`. The top-down `correction = h_b[0] - sum(children)` evaluates `infinity - infinity`, producing NaN. That correction propagates into both leaf values; the closure returns `Ok` without validating output finiteness.

The expected **real-arithmetic** variance-weighted parent is `(2/3)M + (1/3)(2M) = (4/3)M`, and its child correction is `(4/3)M - 2M = -(2/3)M`, divided equally between the two children. Thus the corrected leaves are `2M/3`, approximately `1.134274556e38`, which fits in finite binary32. The failure is avoidable intermediate overflow, not an inherently unrepresentable result.

**Independent execution:** A Python 3 **standard-library** binary32 model using `struct.pack/unpack` after each individual `f32` operation returned `[nan, nan]` for this input. It also returned `[1, 2]` for a small consistent input `[3, 1, 2]`. The dependency-free [regression test](https://github.com/opendp/opendp-audit/blob/main/tools/tests/test_bary_consistency_f32_model.py) retains the demonstration. **Direct native OpenDP execution:** The [pinned integration test](https://github.com/opendp/opendp-audit/blob/main/tools/integration/bary_consistency_open_dp.rs) checked out upstream commit `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` and compiled the actual public `make_consistent_b_ary_tree::<i128, f32>(2)` with `cargo test --no-default-features --features contrib`. Its three tests passed in [GitHub Actions run #45101194889](https://github.com/opendp/opendp-audit/actions/runs/45101194889), including the assertion that both returned leaves are NaN. This directly reproduces the function-level failure and confirms the numeric cast path on the reviewed revision. **Not executed:** R or Python language-binding integration.

**Conclusion:** A high-confidence source-supported numerical utility/correctness defect, not a DP violation. The `Audited` scope is only this explicit `f32` overflow path and the associated arithmetic model, not full postprocessor correctness.

### Native Rust arithmetic regression

A second, independent regression was compiled with native `rustc --edition=2021 --test` in the audit repository's CI. The [std-only reproducer](https://github.com/opendp/opendp-audit/blob/main/tools/tests/bary_consistency_float_overflow.rs) copies the **three-node bottom-up weighted average and top-down correction arithmetic** from the pinned implementation, but uses primitive `f32` operations directly rather than importing OpenDP.

The three Rust tests check that `i128::MAX as f32` is finite but the sum of two such values overflows to infinity and produces NaN final leaves; that the mathematically expected `(2/3)M` leaf value fits within `f32`; and that small consistent counts `[3, 1, 2]` stay unchanged. All three tests passed in [GitHub Actions run #45100869596](https://github.com/opendp/opendp-audit/actions/runs/45100869596), together with the audit repository's existing tests and report validator. The reproducer was introduced in [commit `d8fe885`](https://github.com/opendp/opendp-audit/commit/d8fe885437b40bbeba7157642634bf7f0069d3c4).

This independently **confirms the native Rust primitive arithmetic path**. A subsequent [direct OpenDP integration CI run #45101194889](https://github.com/opendp/opendp-audit/actions/runs/45101194889) also compiled the pinned upstream crate and invoked the public postprocessor, observing the predicted NaN leaves. The native library-level defect is therefore **Reproduced**; FFI conversions remain unexecuted.

### Padding and output length

The function validates `branching_factor >= 2` and rejects an empty vector at invocation. It computes the minimum complete-tree node count covering `arg.len()` with checked node arithmetic, appends zero-valued phantom nodes, and marks missing last-layer and empty-subtree variances as zero. The final slice excludes phantom leaves. The model's basic controls include a one-node tree, a two-node partially missing tree, and two incomplete three-layer trees; these returned finite leaves with the expected lengths.

The code uses inverses of summed child variance, and a top-down correction distributed over child variances. Its intended zero-variance branches are visible in the source, but the model has not exhaustively enumerated all shapes, exactness, or extreme finite input types.

**Conclusion:** No additional padding or shape defect established in the checked controls; **Partial** because the full input-shape and numeric boundary space was not verified.

### Native f64 maximum reproduction

The same source-level failure occurs at the **largest finite binary64 value**, independently of any integer-to-`f32` conversion. Calling `make_consistent_b_ary_tree::<f64, f64>(2)` on the finite three-node tree `[f64::MAX; 3]` produces `Ok([NaN, NaN])`. The bottom-up child sum `f64::MAX + f64::MAX` is infinity; the top-down correction `+∞ - +∞` is NaN. In exact arithmetic, the reconciled leaves are `(2/3)f64::MAX`, each finite and representable.

This precise witness is **natively reproduced in the unchanged OpenDP library** by [`tools/integration/bary_consistency_open_dp.rs`](https://github.com/opendp/opendp-audit/blob/main/tools/integration/bary_consistency_open_dp.rs). [GitHub Actions run #45104456779](https://github.com/opendp/opendp-audit/actions/runs/45104456779) compiled upstream `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` and passed **4/4 baseline tests** (including the new `f64::MAX` NaN assertion). This is the **same intermediate-overflow defect as [issue #33](https://github.com/opendp/opendp-audit/issues/33)**, not a duplicate issue.

### Experimental selective normalization at f64 limits

The [current CI-only patch script](https://github.com/opendp/opendp-audit/blob/main/tools/integration/patch_bary_consistency_wide.py) extends the earlier direct-`f64` approach with **selective magnitude normalization**. After casting all source atoms into `f64` and checking finiteness, it finds the maximum absolute input `M`. If `M > f64::MAX / (4 × num_nodes)`, it divides the tree's values by `M` before the inverse-variance bottom-up and top-down scans, and rescales the reconciled leaves by `M` at the end. Otherwise, it uses scale 1 to avoid changing ordinary-scale calculations. Final `TOA` casts and nonfinite-output rejection remain in place.

The normalization is motivated by the linearity of least-squares consistency projection in the observed node values; its correctness for every combination of parameters is **not proven** here. A numerical reduction uses `f64` and is thus subject to finite-precision cancellation and loss of subnormal contributions when large and small counts coexist.

**Executed tests:** [GitHub Actions run #45104281161](https://github.com/opendp/opendp-audit/actions/runs/45104281161) passed the original three baseline tests and **11/11 patched-library tests**. The patched tests add finite-output checks for `±f64::MAX` in three-node trees, `f64::MAX` in a seven-node tree whose exact leaves are `(3/7)f64::MAX`, and zero-sum cancellation of opposite extreme leaves. They also compare **200 deterministic complete-tree inputs** against an independent four-leaf normal-equation least-squares solver with absolute tolerance `1e-9`. [Run #45104456779](https://github.com/opendp/opendp-audit/actions/runs/45104456779) subsequently passed **4/4 baseline** and **11/11 patched** tests after adding the second native NaN witness. The code is stored in [the audit repository](https://github.com/opendp/opendp-audit/blob/main/tools/integration/bary_consistency_wide_open_dp.rs), and the patch is applied only to the temporary pinned checkout within CI. The upstream repository is unchanged.

**Remaining gaps:** This is a **limited experimental correction**, not a production patch or privacy proof. The added `f64: RoundCast<TIA>` bound can change generic API compatibility, the heuristic scaling threshold is not a formally verified bound for all tree shapes, and exact consistency after rounding, extreme dynamic range, large tree sizes, and all supported `TIA/TOA` combinations remain unverified. [Issue #33](https://github.com/opendp/opendp-audit/issues/33) stays open.

### Experimental widened-intermediate correction

The [CI-only patch script](https://github.com/opendp/opendp-audit/blob/main/tools/integration/patch_bary_consistency_wide.py) applies an experimental correction to a **temporary checkout of pinned OpenDP**: cast input atoms directly into `f64` using `f64::round_cast`, reconcile the tree and variances in `f64`, then convert the resulting leaves to the requested `TOA` and reject nonfinite outputs. It adds the bound `f64: RoundCast<TIA>` to the experimental public constructor. This is **not a production patch or a change to opendp/opendp**. The original first-stage version cast `TIA → TOA → f64`; it addressed the `i128::MAX → f32` intermediate overflow but still failed where the **initial** `u128::MAX → f32` cast produces infinity.

**Current native integration results:** At upstream SHA `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`, [GitHub Actions run #45103722322](https://github.com/opendp/opendp-audit/actions/runs/45103722322) passed **3/3 unchanged baseline tests** (including the original NaN witness) and **7/7 experimental patched-library tests**. The [patched test suite](https://github.com/opendp/opendp-audit/blob/main/tools/integration/bary_consistency_wide_open_dp.rs) verifies:

- `i128::MAX` yields finite `f32` leaves within relative error `2e-7` of the real-arithmetic reference; `i128::MIN` also produces finite, appropriately signed leaves.
- `u128::MAX` as every entry of a three-node binary tree yields finite `f32` leaves even though `u128::MAX as f32` itself is infinite; the mathematically corrected `2M/3` fits in `f32`, and the relative error is below `2e-7`.
- The one-node tree `[u128::MAX]` returns a typed error instead of `Ok([+∞])`, because the final leaf is genuinely unrepresentable as finite `f32`.
- Small complete and several incomplete binary trees yield the expected finite results and output lengths; the `i128::MAX → f64` case is finite and within `2e-15` relative error.

The first experiment's `f64` type-inference error was corrected before [run #45102495396](https://github.com/opendp/opendp-audit/actions/runs/45102495396) passed its earlier four patched tests. The subsequently expanded [commit `f96a132`](https://github.com/opendp/opendp-audit/commit/f96a132c38bc42599b377a9b50ba8a4a7e904faf) adds direct input-to-`f64` casting and the three new boundary tests. [Audit validation run #45103722326](https://github.com/opendp/opendp-audit/actions/runs/45103722326) also passed the Python unit suite and report validator.

**Limitations:** These passing tests do **not** certify generic API compatibility, since the experimental `f64: RoundCast<TIA>` bound may restrict user-defined input types. Nor do they prove full postprocessor accuracy, finite arithmetic under adversarial cancellation, exact consistency after output rounding, performance or allocation limits at large branching factors, or safety of every `TIA/TOA` combination. The upstream implementation remains unchanged, and [issue #33](https://github.com/opendp/opendp-audit/issues/33) remains open pending production review.


### Mixed-magnitude counterexample to the CI-only normalization

**Finding: the experimental global-normalization patch is not valid for arbitrary dynamic range, even on an already-consistent input.** Consider a three-level, seven-node binary tree `[M, M, 0, M, 0, s, -s]` in breadth-first order, with `M = 2^1023` (finite binary64) and `s = 1e-20` (finite, normal binary64). Every parent exactly equals the sum of its children, so its unique real-arithmetic least-squares consistency projection is the identity on leaves `[M, 0, s, -s]`.

At this magnitude the CI-only patch selects `scale = M`. Dividing `s` by `M` gives approximately `1.1e-328`, below the smallest positive binary64 subnormal; both small nodes round to zero **before** the reconciliation scans. The output is `[M, 0, 0, 0]`, silently deleting both valid nonzero leaves. This also occurs in a four-level, fifteen-node consistent tree with leaves `[M, 0, 0, 0, s, -s, 0, 0]`; the patched output replaces `s` and `-s` with zeros.

**Native library evidence:** The [baseline OpenDP integration tests](https://github.com/opendp/opendp-audit/blob/main/tools/integration/bary_consistency_open_dp.rs) verify that pinned, **unmodified** OpenDP preserves all the leaves of these two power-of-two mixed-scale trees. The [patched OpenDP integration tests](https://github.com/opendp/opendp-audit/blob/main/tools/integration/bary_consistency_wide_open_dp.rs) verify the corresponding underflow and leaf deletion. Both groups ran against the actual upstream crate with the patch applied only to the second, temporary checkout. [GitHub Actions run #45107690780](https://github.com/opendp/opendp-audit/actions/runs/45107690780) passed **6/6 baseline** and **13/13 patched** tests, including these four new *characterization* tests. The audit repository validator and unit suite passed in [run #45107690726](https://github.com/opendp/opendp-audit/actions/runs/45107690726).

An earlier exploratory run used `M = f64::MAX` instead of an exact power of two. It exposed a **separate ordinary floating-rounding effect** in unmodified OpenDP: the implementation returned a spurious approximately `-9.98e291` second leaf despite a zero expected leaf, while retaining the `±s` leaves. The strict full-vector identity test consequently failed ([exploratory run #45107482247](https://github.com/opendp/opendp-audit/actions/runs/45107482247)). Switching to the exactly representable `M = 2^1023` removes that confounder while still triggering the normalization underflow. The current passing regression has this deliberately narrower scope.

**Disposition:** This is **not a second upstream bug filed for the normalization**: the loss exists only in the unpublished, CI-only experimental fix, which should **not** be considered production-ready. The original upstream NaN overflow issue [#33](https://github.com/opendp/opendp-audit/issues/33) remains open. A general correction must preserve lower-magnitude subtrees, perhaps via an exact or extended-range arithmetic representation, a per-subtree strategy with an error analysis, or explicitly documented precision limitations. Simple global division followed by multiplication in the same `f64` type cannot preserve these values.

## Findings

**[Issue #33](https://github.com/opendp/opendp-audit/issues/33):** Finite `i128` inputs can produce NaN `f32` leaves through intermediate arithmetic overflow. Verification: **Reproduced**, via the native OpenDP library integration test at the pinned commit ([CI run #45101194889](https://github.com/opendp/opendp-audit/actions/runs/45101194889)) and independent Python/standalone Rust arithmetic models. **Upstream disposition: Unreported**; searches found no matching upstream issue or corrective PR. Earlier [PR #3068](https://github.com/opendp/opendp/pull/3068) fixed a different *tree-construction* issue.

## Next checks

- Add and test a correction to the production postprocessor that either avoids intermediate overflow or returns an explicit error for nonfinite results; update the native integration regression to assert finite leaves where mathematically representable.
- Test equivalent `f64` numeric boundaries, incomplete trees with absent children, and exceptional conversions, ideally with property-based checks of reconciled parent/child consistency.
- Treat the CI-only global-normalization patch as **unsuitable for arbitrary mixed-magnitude inputs** (confirmed by the power-of-two consistent-tree counterexample). Investigate exact or extended-range arithmetic, scale-separated subtree corrections, and explicit output error controls; also review generic type compatibility, large tree complexity, and the accuracy of post-rounding consistency before any upstream change.
