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

The constructor rejects `Any` and `All` aggregation and all other unreviewed Boolean functions, preventing those operators from being certified as ordinary row-wise functions. A second identity map is composed after the recursively stable input expression, so the local predicates cannot inflate row counts *assuming their documented Polars semantics*. A distinct input/operator dtype mismatch was established for `Not`: OpenDP's constructor admits public `Float32`, `Float64`, and `String` column types, while pinned Polars `py-1.36.1` rejects `Not` on each. The constructor has no explicit dtype guard and select traversal does not infer the expression dtype during stabilization. See [candidate #103](https://github.com/opendp/opendp-audit/issues/103) and the [source report](../source/rust/src/transformations/make_stable_expr/expr_boolean_function/mod.rs.md#not-dtype-precondition-mismatch). The failure is determined by a **public schema** and is not evidence of a privacy leak.

### What actually ran

This investigation inspected commit-pinned Rust implementations, their native Rust tests, `SeriesDomain`, and composition paths. Following the initial source-only review, a [pinned-Polars 1.36.1 regression](../tools/integration/polars_boolean_not_dtype.py) was **executed successfully** by [GitHub Actions run 45111889610](https://github.com/opendp/opendp-audit/actions/runs/45111889610): `Not` rejected Float32, Float64, and String, while nullable Int64 and Boolean succeeded. Pinned-Polars planner and runtime sources confirm the same dtype restriction. **No compiled OpenDP constructor or end-to-end OpenDP release was executed.** Thus the Polars-side error is reproduced, but OpenDP acceptance is established by static control-flow analysis, not native execution.

## Findings

- **New low-severity constructor/availability mismatch:** [candidate issue #103](https://github.com/opendp/opendp-audit/issues/103) tracks `Not` on non-Boolean/non-integer types. Polars' rejection is reproduced, and OpenDP constructor acceptance follows directly from source. This does **not** establish a private-data-dependent failure or DP violation.
- **No additional defect identified** in the reviewed nullability branches for `IsNull`, `IsNotNull`, numeric predicates, column selection, literals, and aliases.
- **Partial integration assurance:** Other dtype/operator pairs, optimizer changes, duplicate schemas, arbitrary literal broadcasting, and full `ExprDomain` membership remain unverified.

## Unresolved questions

Add an OpenDP-native constructor regression for `col("x").not()` with Float64/Float32/String domains: construction should reject unsupported public dtypes (or otherwise yield an executable expression). Preserve positive tests for nullable Boolean and integer inputs. Continue to exercise other supported predicates and the full dtype matrix, and verify resulting `ExprDomain::member` behavior. Revisit after Polars upgrades or changes to BooleanFunction variants.
