---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_drop_nan_or_null/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_drop_nan_or_null/mod.rs`

## Scope and assumptions

Reviewed non-deprecated `make_expr_drop_nan_or_null` for `Expr::Function` with `DropNans` or `DropNulls`. The operation filters individual expression values **inside an existing aggregation group**, not frame rows; its identity stability map assumes the input stable expression and successful Polars execution. Pinned [implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_drop_nan_or_null/mod.rs) and [native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_drop_nan_or_null/test.rs); [investigation](../../../../../../investigations/polars-fill-drop-domain-stability.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `transformations::make_stable_expr::expr_drop_nan_or_null::make_expr_drop_nan_or_null` | privacy/row-deletion-stability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Stability reasoning](#stability-reasoning), [reference model](../../../../../../tools/tests/test_polars_fill_drop_model.py) |
| `transformations::make_stable_expr::expr_drop_nan_or_null::make_expr_drop_nan_or_null` | correctness/key-length-margin-downgrade | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Aggregation margin](#aggregation-margin) |
| `transformations::make_stable_expr::expr_drop_nan_or_null::make_expr_drop_nan_or_null` | correctness/null-or-nan-domain-refinement | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Output-domain refinement](#output-domain-refinement) |

## Analysis

### Stability reasoning

A row-local predicate discarding null or NaN atoms cannot increase record-multiset symmetric distance: every individual occurrence is either retained or removed on both inputs. The constructor first stabilizes its input and composes a `DropNans` or `DropNulls` function with identity map on the intermediate metric. The [independent small-multiset model](../../../../../../tools/tests/test_polars_fill_drop_model.py) checked all ordered dataset pairs of length up to three on an eight-record alphabet; no violations were found. This does **not** exercise actual Rust or Polars runtime behavior or all supported `StableExpr` implementations.

### Aggregation margin

The constructor requires `input_domain.context.aggregation(...)` and sets the output context's invariant to `margin.invariant.map(|_| Invariant::Keys)`. Dropping atoms can decrease a group's number of values, invalidating `Lengths`, while the surrounding group key remains present even if its expression has no remaining values. The transformation retains other upper-bound margin fields. This matches the distinction already analyzed for [aggregation expression filtering](../expr_filter/mod.rs.md).

### Output-domain refinement

For `DropNulls`, the output domain is `nullable=false` but any NaN allowance remains unchanged. For `DropNans`, `set_non_nan()` removes NaN allowance while **preserving nullable state**. Unsupported function variants and arities are rejected. The independent model demonstrates that `drop_nulls` need not eliminate NaNs and `drop_nans` need not eliminate nulls.

## Findings and next checks

No new violation within the idealized row-deletion model and source controls. Privacy status **Partial** until native grouped execution, null-bitmaps and exceptional paths are verified. [Audit task #53](https://github.com/opendp/opendp-audit/issues/53).
