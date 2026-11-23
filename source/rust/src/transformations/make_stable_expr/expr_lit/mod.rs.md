---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_lit/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_lit/mod.rs`

## Scope and assumptions

- **Scope:** Public scalar `Expr::Literal` construction and declared dtype/NaN/nullable characteristics.
- **Invariant:** Literal support is restricted to recognized scalar types, including an explicit NaN-enabled floating domain for a floating NaN. Literal evaluation is independent of private records and therefore must have stability bound at most identity.
- **Assumptions:** `LiteralValue::materialize()` correctly preserves the scalar's value, null representation, and dtype. Dtype-specific Polars handling of infinity and literals in full plans was not executed.
- **Upstream:** [implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_lit/mod.rs), [literal tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_lit/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_expr_lit` | correctness/scalar-literal-domain | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Literal dispatch](#literal-dispatch) and [cross-file investigation](../../../../../../investigations/polars-rowwise-leaf-alias-boolean.md) |
| `make_expr_lit` | privacy/public-literal-stability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Privacy and execution boundary](#privacy-and-execution-boundary) |

## Analysis

### Literal dispatch

The function requires an `Expr::Literal` whose materialized representation is `LiteralValue::Scalar` and rejects all unsupported literal forms before constructing a transformation. It recognizes boolean, string, primitive integer, and float scalar variants. Floating `NaN` is detected by `v.is_nan().then(NaN::new)` and sets the element domain's NaN permission accordingly. It does not allow arbitrary literal arrays to pass as supported scalars. The output context is cloned from input and the output field name is taken from `expr_output_name`.

### Privacy and execution boundary

The expression contains a fixed public scalar and reads no input column. The implementation returns `Function::from_expr(expr)` with an identity stability map rather than the tight zero map; this is conservative for row-aligned constant expressions. Actual Polars literal broadcasting, null-scalar API coverage, and optimizer effects were not exercised in this review. These are **Partial** cross-file checks, not an identified privacy failure.

## Next checks

Run the native literal tests, including scalar NaN and infinity, against the pinned Polars planner. No defect identified within the bounded constructor scope.
