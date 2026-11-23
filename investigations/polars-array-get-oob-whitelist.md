---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Polars array.get(false) passes an infallibility gate despite data-dependent OOB errors

## Invariant, scope and security relevance

A stable grouped query or contribution-truncation plan must not allow a fallible expression to fail as a function of protected records. `check_infallible` is the common syntactic gate for aggregation expressions in `make_stable_group_by` and `truncate_domain`. This review is limited to `FunctionExpr::ArrayExpr(ArrayFunction::Get(bool))`, not the full whitelist, all aggregation functions, or an end-to-end differential-privacy proof.

A public array column width of 2 and a private integer index can give success for index 0 but an out-of-bounds error for index 2. The difference in returned error status is potentially privacy-relevant when visible to a caller. **This is a source-confirmed admission mismatch and a potential privacy side channel; a compiled OpenDP private-release reproduction was not executed.**

## Pinned upstream cross-file trace

1. [OpenDP source audit](../source/rust/src/transformations/make_stable_lazyframe/group_by/mod.rs.md), [`check_infallible_function`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/group_by/mod.rs): `ArrayFunction::Get(_)` is accepted alongside `ArrayFunction::Join(_)` and others, then `check_inputs!(aligned_rows)` recurses on operands. The Boolean `null_on_oob` value is ignored. By contrast the `ListFunction::Get(null_on_oob)` arm explicitly rejects `false` with `MakeTransformation`.
2. [OpenDP `make_stable_group_by`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/group_by/mod.rs) calls `check_infallible(agg, Resize::Allow)` on every aggregate expression before constructing its advertised stability map. [`truncate_domain`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/truncate/mod.rs) applies the same check to aggregate expressions in its final group-by.
3. [OpenDP `rust/Cargo.toml`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/Cargo.toml) pins Polars `=0.52.0` and `py-1.36.1` as the patched git tag. The exact [Polars enum](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-plan/src/dsl/function_expr/array.rs) includes `Get(bool)`, and [Polars' `ArrayNameSpace::get`](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-plan/src/dsl/array.rs) constructs `Get(null_on_oob)`.
4. Polars itself classifies [`IRArrayFunction::Get(false) => true` in `AExpr::is_fallible_top_level`](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-plan/src/plans/aexpr/mod.rs), alongside `IRListFunction::Get(false)`. The pinned [array-get implementation](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-ops/src/chunked_array/array/get.rs) forwards the flag to the array indexing operation, while the pinned [Polars tests](https://github.com/pola-rs/polars/blob/py-1.36.1/py-polars/tests/unit/operations/namespaces/array/test_array.py) assert a `ComputeError` for out-of-bounds **series-valued** indices with `false` and a null result with `true`.

## Minimal property witness

Take a fixed-width `Array(Int64, 2)` public-schema column `a`, a public group key `k`, and a private integral column `idx`. Consider the `ArrayFunction::Get(false)` expression `col("a").arr().get(col("idx"), false)` inside a group-by aggregate. Two adjacent inputs have the same single row with `a=[5,6]`, `k=0`, and `idx=0` versus `idx=2`. The first index is valid, the second is out of bounds.

The pinned Polars dependency recognizes this expression as potentially fallible, and its native tests demonstrate the data-dependent indexing failure for an index series. OpenDP's whitelist admits both variants and only checks their inputs for permitted structure. The input index is not a statically known literal, so the additional Polars schema-time literal-index checks do not establish that every value lies in bounds.

**Observation boundary:** This witness establishes **potential data-dependent failure** in a path admitted by OpenDP's syntactic check. Whether a particular public `make_private_lazyframe` construction allows this exact aggregate and reveals an error at collection time requires a compiled integration test. Do not label a privacy guarantee violation as reproduced on OpenDP without that integration check.

## Executed verification and disposition

**Actually executed:** A standalone Python standard-library [source model](../tools/tests/test_array_get_oob_whitelist_model.py) compared OpenDP's unconditional `Get(_)` acceptance and Polars' fallible `Get(false)` indexing outcomes across 20,672 deterministic boundary/random cases. It checks that `Get(true)` yields a null for OOB, and that the analogous list-get false path is rejected. The audit repository's local schema validator and 25 Python unit tests passed. **These tests model the source; they do not compile or run Rust/Polars.**

**Inspected, not executed:** OpenDP and pinned Polars source and Polars' checked-in `test_array_get` regression that expects `ComputeError`. Upstream and audit issues and PRs, including open/closed searches for `arr.get`, `ArrayFunction::Get`, `null_on_oob`, `check_infallible`, and OOB behavior, had no matching corrective PR or prior defect issue.

**Finding:** [Audit candidate issue #71](https://github.com/opendp/opendp-audit/issues/71) (labeled `privacy`). Verification `Candidate` with a source-level control-flow contradiction; upstream disposition `Unreported` on the pinned SHA. This is separate from the earlier [group-by influence-bound audit](polars-groupby-influence-bound.md), which explicitly assumed total aggregation expressions and excluded the whitelist.

## Follow-up

Compile a native Rust regression for `check_infallible` both with `arr.get(col("idx"), false)` directly and inside `AggExpr::First`, compare `null_on_oob=true`, then evaluate stable group-by and truncation constructors on the same expression. Verify the error behavior in the final private LazyFrame execution path before making a quantitative privacy claim. Reject `ArrayFunction::Get(false)` just as `ListFunction::Get(false)` is rejected, unless a separate public proof establishes that all indices are in bounds.
