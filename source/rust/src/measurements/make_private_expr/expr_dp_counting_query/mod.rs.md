---
schema_version: 1
source: rust/src/measurements/make_private_expr/expr_dp_counting_query/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/make_private_expr/expr_dp_counting_query/mod.rs`

## Scope and assumptions

Reviewed the non-deprecated counting-query shim macro used by `dp_len` in the Polars `dp_mean` constructor. The initial review covered the optional `signed` argument and default unsigned output in the DP mean denominator; the 2026-11-23 review additionally covers public **signed-mode shim schema** versus the private rewritten output across all four generated counting operators. It does not establish all count/n_unique semantics or noise sampling. Pinned OpenDP revision: `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`.

- [Shim source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_dp_counting_query/mod.rs), [`match_shim` behavior](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/mod.rs), [integer noise saturation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/integer/mod.rs), [investigation](../../../../../../investigations/polars-dp-mean-filler-and-denominator.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::make_private_expr::expr_dp_counting_query::make_expr_dp_len` | correctness/default-unsigned-output | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Argument padding and dtype](#argument-padding-and-dtype) |
| `measurements::make_private_expr::expr_dp_counting_query::make_expr_dp_len` | privacy/noisy-count-bound | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file investigation](../../../../../../investigations/polars-dp-mean-filler-and-denominator.md) |
| `DPLenShim::get_field` (generated) | correctness/signed-count-schema | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Signed schema discrepancy](#signed-schema-discrepancy); [issue #129](https://github.com/opendp/opendp-audit/issues/129) |
| `DPCountShim::get_field` (generated) | correctness/signed-count-schema | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Signed schema discrepancy](#signed-schema-discrepancy) |
| `DPNullCountShim::get_field` (generated) | correctness/signed-count-schema | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Signed schema discrepancy](#signed-schema-discrepancy) |
| `DPNUniqueShim::get_field` (generated) | correctness/signed-count-schema | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Signed schema discrepancy](#signed-schema-discrepancy) |
| `new_make_expr_counting_query!::$constructor` (four generated constructors) | correctness/signed-count-rewrite-dtype | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Signed schema discrepancy](#signed-schema-discrepancy) |
| `new_make_expr_counting_query!::$constructor` | privacy/noise-calibration-signedness | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Signed schema discrepancy](#signed-schema-discrepancy) |

## Analysis

### Argument padding and dtype

The macro-generated `make_expr_dp_len` calls `match_shim::<DPLenShim,3>`, which expects `[input,scale,signed]`. The generic `match_shim` pads **missing** trailing arguments to `lit(NULL)`, instead of failing an arity check. The shim's `signed` extraction uses `lit.bool().unwrap_or(false)`, so null or missing `signed` is interpreted as **false**. It then uses `input.len()` without an `Int64` cast; `signed=true` would explicitly add `.cast(DataType::Int64)`. The subsequent `NoiseShim` operates on the actual typed aggregation expression.

This is important because `make_expr_dp_mean` constructs a two-argument `DPLenShim` and therefore silently chooses an unsigned denominator, rather than failing construction. The [cross-file investigation](../../../../../../investigations/polars-dp-mean-filler-and-denominator.md) and [independent model](../../../../../../tools/tests/test_polars_dp_mean_model.py) cover resulting unsigned clipping bias. The existing upstream issue is [#3217](https://github.com/opendp/opendp/issues/3217).

No incorrect privacy map was demonstrated: the unsigned clipping is postprocessing of the noisy count. Full counting-query mechanism/FFI behavior is **Partial** pending native Rust/Polars execution.

### Signed schema discrepancy

**Additional scoped review at [upstream `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/measurements/make_private_expr/expr_dp_counting_query/mod.rs).** The generated `AnonymousColumnsUdf::get_field` accepts three input fields, including `signed`, but always returns `Field::new(input.name().clone(), DataType::UInt32)`. In contrast, the generated `make_expr_*` constructor parses `signed` and applies `aggregate.cast(DataType::Int64)` before wrapping in `NoiseShim` when `signed=true`. The same macro instantiates `DPLenShim`, `DPCountShim`, `DPNullCountShim`, and `DPNUniqueShim`. Thus public raw Polars planning metadata reports `UInt32` while the rewritten signed release reports `Int64`.

The [Rust DPExpr constructors](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/polars/mod.rs) pass a signed Boolean literal, and the [native rewritten tests](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/measurements/make_private_expr/expr_dp_counting_query/test.rs) explicitly expect `Int64` when true. The raw schema test only covers `signed=false`. The constant callback and conditional rewrite are direct source evidence; **a native raw `collect_schema()` call and any downstream optimizer effects were not executed**. Distinguishing the boolean's **value** cannot be accomplished by checking the literal expression's `Boolean` **dtype** alone.

**Correctness/metadata candidate:** [Audit #129](https://github.com/opendp/opendp-audit/issues/129), cross-file [investigation](https://github.com/opendp/opendp-audit/blob/main/investigations/polars-signed-count-shim-schema.md). No data-dependent failure or privacy-budget under-accounting is established: the noise plugin is constructed from the rewritten, signed `Int64` stable aggregate; full privacy implications remain **Partial**. This differs from the prior reviewed `dp_mean` denominator's default unsigned behavior: the newly reviewed invariant is the discrepancy **when `signed=true` is explicitly requested**.

## Next checks

- Native tests for two-argument and three-argument length shims, output dtypes, and the `dp_mean` caller.
- Explicitly pass `signed=true` from `dp_mean` when a noisy denominator is used; test conversion behavior around negative counts.

- Add a raw Polars `collect_schema()` test with `signed=true` for all four generated shims and compare with the emitted rewritten `Int64` output. A schema-aware optimizer/postprocessing failure is not yet demonstrated.
