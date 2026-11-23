---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Polars stable row-wise expression lineage: column, literal, alias, Boolean predicates

## Invariant and threat model

A non-deprecated `StableExpr` that selects a column, introduces a public scalar, aliases a result, or applies a supported Boolean predicate must preserve the output schema and nullability claims. In particular, incorrect removal of nullable/NaN membership constraints could allow a downstream privacy-map proof to rely on an invalid input domain. Pure row-wise expressions must not add/drop rows, and their stability map must be conservative. These checks focus on local constructors; no broad DP mechanism proof is attempted.

## Affected symbols and source audits

- [`make_expr_col`](../source/rust/src/transformations/make_stable_expr/expr_col/mod.rs.md) — public-schema name lookup and descriptor reuse; [pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_col/mod.rs).
- [`make_expr_lit`](../source/rust/src/transformations/make_stable_expr/expr_lit/mod.rs.md) — scalar-only dispatch and NaN flag; [pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_lit/mod.rs).
- [`make_expr_alias`](../source/rust/src/transformations/make_stable_expr/expr_alias/mod.rs.md) — output name update without descriptor changes; [pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_alias/mod.rs).
- [`make_expr_boolean_function`](../source/rust/src/transformations/make_stable_expr/expr_boolean_function/mod.rs.md) — restricted operator set, nullability and bitwise `Not`; [pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_boolean_function/mod.rs).
- [`SeriesDomain::set_dtype`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/series/mod.rs) refreshes element domains; the prior field's `nullable` bit is a separate property.

## Reasoning and evidence

### Column selection and aliases

`make_expr_col` constructs the output `ExprDomain` from the exact public name match and clones the column domain and expression context. Missing fields fail at construction, rather than examining private rows. `make_expr_alias` composes a prior stable expression with an identity stability map and only changes the output column name. The [column tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_col/test.rs) check successful and missing lookups; the [alias tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_alias/test.rs) include new names, same names, and cross-name shadowing. A public schema with duplicate column names was not examined.

### Public literal typing

`make_expr_lit` materializes scalar literals and dispatches only on supported Boolean/String/integer/float scalar values. Float NaN creates a NaN-permitting domain instead of a falsely non-NaN domain. Non-scalar and unsupported values are rejected. `Function::from_expr` with identity stability is conservative for a data-independent literal; correctness depends on the planner's literal broadcasting semantics. Null literal support is not covered by this whitelist.

### Boolean nullability, bitwise negation, and row alignment

`IsNull` and `IsNotNull` set the result to non-null, even when the input can be null. Numeric finite/infinite/NaN checks retain nullability, consistent with the pinned native [Boolean tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_boolean_function/test.rs). The Boolean result's element descriptor is reset by `set_dtype`. For `Not`, both Boolean logical negation and integer bitwise negation preserve dtype and input nullability while dropping unsuitable bounds descriptors (e.g., signed `!0=-1`).

The constructor rejects `Any` and `All` aggregation and all other unreviewed Boolean functions, preventing those operators from being certified as ordinary row-wise functions. A second identity map is composed after the recursively stable input expression, so the local predicates cannot inflate row counts *assuming their documented Polars semantics*. An input/operator dtype pair unsupported by Polars may still cause a public-schema-determined runtime error. Such combinations were not dynamically verified here.

### What actually ran

This investigation inspected commit-pinned Rust implementations, the corresponding native Rust test source, the Polars `SeriesDomain` implementation, and composition paths. **No compiled OpenDP/Polars code, Python proxy of native operators, or new runtime test was executed.** This is a bounded negative source review, not an assertion that the native test suite passed.

## Findings

- **No new defect identified** in supported row-wise column/alias/literal/Boolean nullability branches within the stated scope.
- **Partial integration assurance:** Unsupported dtype/operator pair behavior, optimizer changes, duplicate schemas, arbitrary literal broadcasting and full `ExprDomain` membership were not verified. No new GitHub bug issue was opened because none was confirmed.

## Unresolved questions

Run the native Polars unit tests, exercise signed/unsigned `Not` and nullable NaN fixtures across the complete compatible dtype matrix, and verify the resulting `ExprDomain::member` behavior. Revisit if upstream adds or changes BooleanFunction variants.
