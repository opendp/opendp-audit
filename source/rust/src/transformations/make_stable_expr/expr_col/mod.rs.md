---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_col/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_col/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated `make_expr_col` selection of an existing named column in a Polars `WildExprDomain`.
- **Invariant:** A public-schema column lookup must preserve its `SeriesDomain` (dtype, nullability, element descriptors), expression context, and metric distance. Unknown columns must fail at construction without reading private rows.
- **Assumptions:** Input is a valid `WildExprDomain` built from a schema of uniquely named columns. Polars' `col(name)` selects that column without changing its row order or values. Cross-file membership and arbitrary user-constructed duplicate schemas are not independently established.
- **Upstream:** [implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_col/mod.rs), [native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_col/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_expr_col` | correctness/column-schema-lineage | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Selection trace](#selection-trace) and [cross-file investigation](../../../../../../investigations/polars-rowwise-leaf-alias-boolean.md) |
| `make_expr_col` | privacy/metric-identity | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Metric and execution assumptions](#metric-and-execution-assumptions) |

## Analysis

### Selection trace

The constructor matches only `Expr::Column(col_name)`. It selects the `SeriesDomain` by matching the public field name, clones it unchanged into the `ExprDomain`, and clones `input_domain.context`. An absent field raises `MakeTransformation` before building an executable expression. Both the successful lookup and rejection depend exclusively on the declared schema, not record values. The upstream tests check a matching expression and an unknown-name rejection.

### Metric and execution assumptions

The produced expression is `col(name)` and the associated stability map is identity under the unchanged input/output metric. This is appropriate for ordinary row-preserving column projection and is consistent with the [cross-file lineage review](../../../../../../investigations/polars-rowwise-leaf-alias-boolean.md). The native Polars engine, frame member checks, and duplicate-column conditions were not executed in this audit; the metric claim remains **Partial** rather than a runtime proof.

## Next checks

Exercise compiled Polars projected data with nullable, NaN-permitting and categorical columns, and verify that its `SeriesDomain` membership matches materialized results. No new defect identified within scope.
