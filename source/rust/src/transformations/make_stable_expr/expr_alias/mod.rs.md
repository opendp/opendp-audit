---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_alias/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_alias/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated `make_expr_alias` on stable expressions and downstream schema names.
- **Invariant:** Aliasing changes only the name of the result column. Dtype, nullability, bound/NaN descriptors, aggregation context, and the underlying stability distance must remain unchanged.
- **Assumptions:** The prior expression respects its stability and domain contract. The surrounding Polars planner implements `Expr::Alias` as renaming without changing values. The validity of complete `with_columns` planning with duplicate targets is outside scope.
- **Upstream:** [implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_alias/mod.rs), [native alias tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_alias/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_expr_alias` | correctness/alias-domain-lineage | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Alias trace](#alias-trace) and [cross-file investigation](../../../../../../investigations/polars-rowwise-leaf-alias-boolean.md) |
| `make_expr_alias` | privacy/metric-identity | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Composed stability](#composed-stability) |

## Analysis

### Alias trace

The constructor accepts only `Expr::Alias`, recursively makes its input expression stable, clones the prior output domain, and writes only `output_domain.column.name = name.clone()`. The column dtype, nullability, element-domain constraints, and expression context are retained. This is consistent with the upstream tests for new, same-name and shadowing aliases (A to B, B to A), which compare materialized schema and output.

### Composed stability

A second transformation applies `expr.alias(name)` and has an identity stability map. `t_prior >> t_alias` composes the stable input with the rename. Under the ordinary Polars alias contract, distances between datasets cannot increase. Cross-column name collisions, optimizer rewrites, and native execution of the test suite were not independently checked; this scoped property is **Partial**.

## Next checks

Check alias-related optimizer rewrites against the exact Polars revision and cross-plan nested aliases. No source-level defect identified within scope.
