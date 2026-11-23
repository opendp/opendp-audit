---
schema_version: 1
upstream_commit: 7acfb2cdcee7d39fc26a6ade7edac15249c52f4b
updated: 2026-11-23
status: Partial
---

# Signed Polars DP counting shim schema and private rewrite

## Threat model and invariant

A public Polars expression using `signed=true` should expose a schema consistent with the released value's dtype. The public input to the planning shim includes a Boolean literal `signed`. OpenDP must not silently certify the same count expression as `UInt32` during planning while emitting `Int64` after replacing its non-evaluable privacy shim, unless that mismatch is explicitly designed and its consequences safely isolated. The more privacy-critical question is whether a schema discrepancy changes calibration, data-dependent error behavior, or postprocessing. **None of those downstream privacy effects was established.**

## Upstream cross-file source trace

1. [Rust DSL constructors](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/polars/mod.rs): `dp_len(scale,signed)` and `DPExpr::{len,count,null_count,n_unique}(scale,signed)` pass the Boolean literal into their shims.
2. [`DPFrameLenShim`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/measurements/make_private_expr/expr_dp_frame_len/mod.rs): `get_field` ignores both inputs, returning `Field("len", UInt32)`. `make_expr_dp_frame_len` instead uses `len().cast(Int64)` for `signed=true`.
3. [`DPLenShim`, `DPCountShim`, `DPNullCountShim`, `DPNUniqueShim`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/measurements/make_private_expr/expr_dp_counting_query/mod.rs): the shared `get_field` macro returns `UInt32` for every three-field input. Its corresponding private constructors cast the aggregate to `Int64` for `signed=true`.
4. [`NoiseShim` rewriter](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/measurements/make_private_expr/expr_noise/mod.rs): after rewrite, the noise plugin's output field inherits its numeric input field, so the signed `Int64` cast propagates through the DP noise expression, rather than being forced back to `UInt32`.
5. [Existing native tests for frame count](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/measurements/make_private_expr/expr_dp_frame_len/test.rs) and [expression counts](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/measurements/make_private_expr/expr_dp_counting_query/test.rs): verify that rewritten signed output is `Int64`, but raw-shim `collect_schema()` tests cover only `signed=false`.

## Source-level counterexample

The original source's `get_field` functions do not inspect the **value** of `signed`. Therefore for a valid raw plan `lf.select([dp_len(Some(0.0), true)])`, the schema callback will report `len: UInt32`, while `make_expr_dp_frame_len` produces an expression `len().cast(Int64)` passed to the noise plugin. The same contradiction holds for `col("A").dp().count(Some(0.0), true)` and other signed count variants.

A decisive **proposed** native regression is:

```rust
let lf = df!("A" => [1i32, 2, 3])?.lazy();
let expr = dp_len(Some(0.0), true);
let raw_schema = lf.select([expr]).collect_schema()?;
assert_eq!(raw_schema.get("len"), Some(&DataType::Int64));
```

This assertion is contradicted by the currently pinned callback, but the native test was **not executed** in this audit. The existing rewritten `test_dp_frame_len_types` and `test_dp_count_types` assert signed `Int64` runtime output.

## Assessment

- **Source-confirmed discrepancy:** The callbacks' unconditional `UInt32` type conflicts with their paired rewrite constructors' conditional `Int64`.
- **Practical effect:** A pre-rewrite `collect_schema()` or a planner relying on these fields can receive incorrect signed-count metadata. No concrete Polars optimizer corruption, data-dependent error, privacy overrun, or under-noising was demonstrated.
- **Upstream history:** [Merged PR #2761](https://github.com/opendp/opendp/pull/2761) added signed count casts without changing the constant `UInt32` shim schema callbacks. Targeted current open/closed upstream issue and all-state PR searches found no equivalent fix/report.
- **Disposition:** [Audit correctness candidate #129](https://github.com/opendp/opendp-audit/issues/129), verification **Candidate** pending pinned compiled/native reproduction. Coordination task [#127](https://github.com/opendp/opendp-audit/issues/127).

## Next checks

1. Add pinned upstream Rust tests for **raw** `collect_schema()` with `signed=true` and `signed=false` for all five operations, together with signed rewritten output-schema assertions.
2. Evaluate whether a signed DP count can participate in downstream schema-dependent postprocessing or optimizations **before** shim rewrite, causing incorrect query behavior.
3. Repair the public schema contract using an API that can distinguish the signed flag in planning (e.g. distinct signed/unsigned shim types), without changing unsigned `UInt32` outputs. Since `get_field` ordinarily sees argument *dtypes* rather than their literal *values*, examining `Boolean` field dtype alone is insufficient.

**Executed:** GitHub source/history/issue inspection; static control-flow comparison. **Not executed:** OpenDP native Rust, Polars `collect_schema()`, or an end-to-end privacy test. Neither `opendp` nor `polars` was installed in the audit container.
