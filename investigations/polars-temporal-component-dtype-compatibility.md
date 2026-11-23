---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Audited
---

# Polars temporal component constructor accepts incompatible public dtypes

## Invariant and threat model

`make_expr_datetime_component` is a stable row-wise transformation constructor. It must ensure that a recognized temporal function is executable on the declared public temporal dtype; a valid domain should not contain only values for which expression evaluation fails. This is a **public-schema contract / availability** issue. It neither discloses protected input values nor demonstrates a privacy-bound underestimate.

## Affected symbols and source audits

- [Scoped source report](https://github.com/opendp/opendp-audit/blob/main/source/rust/src/transformations/make_stable_expr/namespace_dt/expr_datetime_component/mod.rs.md) and [pinned OpenDP constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/namespace_dt/expr_datetime_component/mod.rs).
- [OpenDP Rust tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/namespace_dt/expr_datetime_component/test.rs) and [Cargo patch pinning Polars `py-1.36.1`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/Cargo.toml).
- [Pinned Polars `TemporalMethods` on `Series`](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-time/src/series/mod.rs), [expression dispatcher](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-expr/src/dispatch/datetime.rs), and [DSL documentation](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-plan/src/dsl/dt.rs).
- [Standalone reference-model tests](https://github.com/opendp/opendp-audit/blob/main/tools/tests/test_polars_temporal_component_dtype_model.py).

## Reasoning and evidence

The constructor enforces two separate conditions: `match_datetime_component(temporal_function)` must recognize the operation, and `middle_domain.column.dtype()` must be one of `Time`, `Date`, `Datetime(Nanoseconds,_)`. No match connects **the chosen operation** to **the chosen dtype**. Thus `Time` with `Year` is accepted, and `Date` with `Hour` is accepted, and the function creates an expression transformation with `StabilityMap::new(Clone::clone)`.

The pinned Polars Series implementation contradicts these combinations directly:

- `TemporalMethods::year`: `Date` → `year()`, `Datetime` → `year()`, otherwise `polars_bail!(opq = year, dt)`; **Time is not a supported input**.
- `TemporalMethods::hour`: `Datetime` → `hour()`, `Time` → `hour()`, otherwise `polars_bail!(opq = hour, dt)`; **Date is not a supported input**.

The Polars expression dispatcher calls the Series methods, so the mismatch occurs at runtime or schema evaluation, even though OpenDP has already accepted the transformation. The Arrow-level `time_like!` macro has broader internals, but that does **not** override the high-level `TemporalMethods::hour` dtype guard used by the Polars expression dispatcher.

The existing OpenDP test matrix covers `Time→{Hour,Minute,Second,Millisecond,Microsecond,Nanosecond}`, `Date→{Millennium,Century,Year,IsoYear,Quarter,Month,Week,WeekDay,Day,OrdinalDay}`, and all those components on `Datetime(ns)`. The missing tests are the **cross-product** such as `Time→Year` and `Date→Hour`.

**Executed:** Six Python 3 standard-library tests translated the reviewed OpenDP and pinned Polars source predicates for a representative four-operation subset; the model checks both false-positive constructor acceptances, valid positive cases, unsupported-function exclusion, and the independent ms/us timestamp restriction. The local audit validator passed. **Not executed:** compiled OpenDP or Polars, real FFI or private evaluation; no observed end-to-end privacy impact.

## Findings

**Source-confirmed dtype/function compatibility mismatch; candidate pending compiled Rust confirmation**, tracked as [audit issue #66](https://github.com/opendp/opendp-audit/issues/66). Upstream disposition **Unreported**. Historical upstream PR #2159 documents proof coverage rather than a corrective change. The issue is a correctness and availability defect because a successfully constructed transformation has a public-schema-determined evaluation failure.

## Unresolved questions

- Compile and execute the two witnesses with the exact OpenDP+Polars feature configuration, proving the expected structured error and confirming its timing (schema resolution versus collection).
- Enforce operation/dtype compatibility during OpenDP construction rather than leaving backend validation until invocation. Keep the existing nanosecond-only datetime range check.
- Check other temporal functions individually for narrower dtype restrictions or exceptional behavior, without inferring support solely from a generic `TemporalFunction` enum.
