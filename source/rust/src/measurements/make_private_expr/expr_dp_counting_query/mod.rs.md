---
schema_version: 1
source: rust/src/measurements/make_private_expr/expr_dp_counting_query/mod.rs
updated: 2026-11-22
---

# `rust/src/measurements/make_private_expr/expr_dp_counting_query/mod.rs`

## Scope and assumptions

Reviewed the non-deprecated counting-query shim macro used by `dp_len` in the Polars `dp_mean` constructor. The property is the interpretation of the optional `signed` argument and the resulting integer output dtype, not all distinct count/n_unique semantics or noise sampling. Pinned OpenDP revision: `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`.

- [Shim source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_dp_counting_query/mod.rs), [`match_shim` behavior](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/mod.rs), [integer noise saturation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/integer/mod.rs), [investigation](../../../../../../investigations/polars-dp-mean-filler-and-denominator.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::make_private_expr::expr_dp_counting_query::make_expr_dp_len` | correctness/default-unsigned-output | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Argument padding and dtype](#argument-padding-and-dtype) |
| `measurements::make_private_expr::expr_dp_counting_query::make_expr_dp_len` | privacy/noisy-count-bound | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file investigation](../../../../../../investigations/polars-dp-mean-filler-and-denominator.md) |

## Analysis

### Argument padding and dtype

The macro-generated `make_expr_dp_len` calls `match_shim::<DPLenShim,3>`, which expects `[input,scale,signed]`. The generic `match_shim` pads **missing** trailing arguments to `lit(NULL)`, instead of failing an arity check. The shim's `signed` extraction uses `lit.bool().unwrap_or(false)`, so null or missing `signed` is interpreted as **false**. It then uses `input.len()` without an `Int64` cast; `signed=true` would explicitly add `.cast(DataType::Int64)`. The subsequent `NoiseShim` operates on the actual typed aggregation expression.

This is important because `make_expr_dp_mean` constructs a two-argument `DPLenShim` and therefore silently chooses an unsigned denominator, rather than failing construction. The [cross-file investigation](../../../../../../investigations/polars-dp-mean-filler-and-denominator.md) and [independent model](../../../../../../tools/tests/test_polars_dp_mean_model.py) cover resulting unsigned clipping bias. The existing upstream issue is [#3217](https://github.com/opendp/opendp/issues/3217).

No incorrect privacy map was demonstrated: the unsigned clipping is postprocessing of the noisy count. Full counting-query mechanism/FFI behavior is **Partial** pending native Rust/Polars execution.

## Next checks

- Native tests for two-argument and three-argument length shims, output dtypes, and the `dp_mean` caller.
- Explicitly pass `signed=true` from `dp_mean` when a noisy denominator is used; test conversion behavior around negative counts.
