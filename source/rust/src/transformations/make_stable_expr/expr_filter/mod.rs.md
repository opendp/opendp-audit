---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_filter/mod.rs
updated: 2026-11-22
---

# `rust/src/transformations/make_stable_expr/expr_filter/mod.rs`

## Scope and assumptions

Non-deprecated `make_expr_filter` for filtering values *within an aggregation*, distinguished from [frame filtering](../../make_stable_lazyframe/filter/mod.rs.md). Reviewed [upstream implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_filter/mod.rs) and [tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_filter/test.rs) at `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. Assume a deterministic record-local predicate and a Polars group-by operation that retains the group key when an expression filters all its values; no native code was executed.

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `transformations::make_stable_expr::expr_filter::make_expr_filter` | privacy/aggregation-filter-stability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Source reasoning](#source-reasoning), [model](../../../../../../investigations/polars-filter-stability-and-margins.md) |
| `transformations::make_stable_expr::expr_filter::make_expr_filter` | correctness/aggregation-margin-downgrade | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Source reasoning](#source-reasoning) |
| `transformations::make_stable_expr::expr_filter::make_expr_filter` | correctness/predicate-type-and-metric | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Type and metric guards](#type-and-metric-guards) |

## Analysis

### Source reasoning

The source requires `Context::Aggregation`, then stabilizes `input` and `by` under `Context::RowByRow`. It builds `input.expr.filter(by.expr)` with identity stability map. Row-local record selection is nonexpansive in multiset symmetric distance under successful execution. The output margin maps any input invariant to `Invariant::Keys`, and retains `None` as `None`: the enclosing group remains even when no elements pass, but its length can change. The [independent model](../../../../../../tools/tests/test_polars_filter_stability_model.py) checks 741,036 row/groupwise pair inequalities overall and a witness retaining an empty group.

### Type and metric guards

The source rejects non-boolean predicate dtype and requires the value/predicate transformations to have equal output metrics. The row-by-row context rules out aggregating predicates. These guards do not independently prove all supported subexpressions remain total or row-local.

## Findings

No new defect in the scoped source analysis; privacy/stability status remains **Partial** due to native execution and dependency assumptions. [Cross-file investigation](../../../../../../investigations/polars-filter-stability-and-margins.md); [audit task #43](https://github.com/opendp/opendp-audit/issues/43).

## Next checks

Run native Rust/Polars tests for empty groups, nullable predicates, and exceptional row expressions, and verify output margins against runtime grouping behavior.
