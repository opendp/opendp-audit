---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_fill_nan/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_fill_nan/mod.rs`

## Scope and assumptions

Reviewed non-deprecated `make_expr_fill_nan` and `match_fill_nan` at upstream revision `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. The properties are NaN-removing output-domain flags, preserved input nullability, literal/column filler restrictions and context propagation. Source: [implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_fill_nan/mod.rs), [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_fill_nan/test.rs), and [cross-file investigation](../../../../../../investigations/polars-fill-drop-domain-stability.md). Full privacy relies on successful deterministic row-local Polars execution; native code was not run.

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `transformations::make_stable_expr::expr_fill_nan::make_expr_fill_nan` | correctness/non-nan-output-and-nullability | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Domain checks](#domain-checks) |
| `transformations::make_stable_expr::expr_fill_nan::make_expr_fill_nan` | privacy/aggregation-invariant-preservation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Stability and context](#stability-and-context) |
| `transformations::make_stable_expr::expr_fill_nan::match_fill_nan` | correctness/ternary-shape-recognition | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Matcher](#matcher) |

## Analysis

### Domain checks

The constructor accepts only floating-point data (`Float32`/`Float64`) and non-nullable numeric fillers whose domains exclude NaN. It infers the output dtype, resets the output's float element domain to a fresh **non-NaN, unbounded** atom domain, and retains the original nullable flag. Thus a null survives `fill_nan`, while a NaN is replaced by the non-NaN filler. Resetting old numerical bounds is conservative when a fill or coercion changes possible values. The [independent reference model](../../../../../../tools/tests/test_polars_fill_drop_model.py) asserts that `[NULL, NaN, -1, 2]` filled with a value of 3 produces `[NULL, 3, -1, 2]`, still nullable but not NaN-able.

### Stability and context

A column-referencing filler forces row-by-row stabilization; a broadcastable scalar literal uses the existing context. For scalar filler, the output copies `data_domain.context`, preserving any prior `Keys` downgrade. For column fill, the original input context is copied **only after** the nested expression is restricted to row-by-row operations. Equality of output metrics is checked. This prevents the previously reported reintroduction of public-length invariants in nested filtered expressions ([upstream issue #3039](https://github.com/opendp/opendp/issues/3039)) within the supported construction paths.

Deterministic record-local replacement is nonexpansive under multiset symmetric distance, as tested in the [finite model](../../../../../../tools/tests/test_polars_fill_drop_model.py). It does not prove successful native execution for all numeric conversions, null-bitmaps, or exceptional Polars expressions, so privacy coverage remains **Partial**.

### Matcher

`match_fill_nan` recognizes a specific `Expr::Ternary` shape whose predicate equals `truthy.is_not_nan().or(truthy.is_null())`; it returns the matched `truthy` data and `falsy` fill expressions or `None`. The literal structure check does not authorize arbitrary ternary expressions as `fill_nan`.

## Findings and next checks

No new defect in the examined source contract and independent model. Run the upstream native tests on `f32/f64` extremes, nullable arrays, float coercion and optimizer rewrites; verify the `match_fill_nan` structural assumption under future Polars versions. [Audit task #53](https://github.com/opendp/opendp-audit/issues/53).
