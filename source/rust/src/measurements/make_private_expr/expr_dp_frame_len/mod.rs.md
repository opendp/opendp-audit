---
schema_version: 1
source: rust/src/measurements/make_private_expr/expr_dp_frame_len/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/make_private_expr/expr_dp_frame_len/mod.rs`

## Scope and assumptions

- **Scope:** `DPFrameLenShim::get_field` metadata for signed and unsigned DP frame lengths, its `make_expr_dp_frame_len` rewrite, and how `NoiseShim` propagates the rewritten input dtype. The actual sampler's privacy law is out of scope.
- **Invariant:** Public planner schema for `dp_len(scale,signed=true)` should agree with the produced signed `Int64` DP release. The unsigned mode should preserve `UInt32`.
- **Reviewed revision:** [upstream `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/measurements/make_private_expr/expr_dp_frame_len/mod.rs).
- **Evidence:** [Cross-file investigation](https://github.com/opendp/opendp-audit/blob/main/investigations/polars-signed-count-shim-schema.md), [audit issue #129](https://github.com/opendp/opendp-audit/issues/129), [audit task #127](https://github.com/opendp/opendp-audit/issues/127).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `DPFrameLenShim::get_field` | correctness/signed-count-schema | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Planner schema is fixed unsigned](#planner-schema-is-fixed-unsigned); [issue #129](https://github.com/opendp/opendp-audit/issues/129) |
| `make_expr_dp_frame_len` | correctness/signed-count-rewrite-dtype | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Rewritten signed output](#rewritten-signed-output) |
| `make_expr_dp_frame_len` | privacy/noise-calibration-signedness | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Privacy interpretation](#privacy-interpretation) |

## Analysis

### Planner schema is fixed unsigned

The `DPFrameLenShim::get_field` callback ignores its schema and input fields and returns `Field::new("len", DataType::UInt32)` unconditionally. It does not distinguish `signed=true` from `signed=false`; `rust/src/polars/mod.rs` forwards `lit(signed)` as the second shim argument. Thus the raw signed DP expression is advertised to Polars as `UInt32` even though its documented post-rewrite output is `Int64`.

### Rewritten signed output

`make_expr_dp_frame_len` matches the two-argument shim, extracts the signed Boolean literal, and builds `len().cast(DataType::Int64)` when it is true, otherwise `len()`. It wraps that exact expression in `NoiseShim`, whose rewriter preserves its numeric input field type. Therefore signed output is `Int64` and unsigned output is `UInt32` after private rewriting.

The existing upstream `test_dp_frame_len_types` tests both signed and unsigned rewritten execution and explicitly expects `Int64` for signed; the separate `test_dp_frame_len_shim_schema` tests raw `collect_schema()` for **unsigned only**. The mismatch for signed is a source-confirmed planning contract defect, tracked in [#129](https://github.com/opendp/opendp-audit/issues/129). The same macro-pattern affects four expression-count operations, independently recorded in the sibling source report.

### Privacy interpretation

The private rewrite feeds a signed `Int64` aggregate to the noise mechanism, so the schema mismatch does **not** itself establish that noise is calibrated to `UInt32` or that negative noisy counts are clamped. The noise plugin's privacy map derives from the stabilized rewritten aggregate and its metric; a separate data-dependent failure would require demonstrating an unsafe interaction with Polars planner/optimizer or postprocessing. No such interaction was executed or shown. The privacy assessment is **Partial**.

## Verification and next checks

**Source inspection only:** matched the pinned unconditional `get_field` branch to the signed rewrite and inspected native Rust tests; no native OpenDP/Polars execution or privacy experiment. Add `dp_len(Some(0.0), true)` to raw `collect_schema()` tests and compare with the rewritten output field. Verify downstream optimizer behavior under the pinned Polars version. The issue is distinct from grouped-length domain issue [#78](https://github.com/opendp/opendp-audit/issues/78) and integer-count overflow concerns.
