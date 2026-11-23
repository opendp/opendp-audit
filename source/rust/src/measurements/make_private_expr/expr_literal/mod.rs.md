---
schema_version: 1
source: rust/src/measurements/make_private_expr/expr_literal/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/make_private_expr/expr_literal/mod.rs`

## Scope and assumptions

Reviewed non-deprecated `make_expr_private_lit` at upstream `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. The claim is restricted to the **literal expression** returned by this measurement; it is not a zero-privacy certificate for the entire grouped frame in which that literal might subsequently be evaluated.

- [Pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_literal/mod.rs), [native source tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_literal/test.rs), [PrivateExpr leaf dispatch](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/mod.rs).
- [Cross-file investigation](../../../../../../investigations/polars-public-length-and-literal-privacy.md), [independent reference model](../../../../../../tools/tests/test_polars_privacy_free_expr_model.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_expr_private_lit` | privacy/public-literal-zero-cost | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Literal and privacy map](#literal-and-privacy-map) |
| `make_expr_private_lit` | correctness/expression-shape-validation | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Literal and privacy map](#literal-and-privacy-map) |
| `make_expr_private_lit` | privacy/composed-group-key-release | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Whole-plan caveat](#whole-plan-caveat) |

## Analysis

### Literal and privacy map

The constructor accepts only `Expr::Literal(_)`; all other expression AST variants are rejected. It emits `Function::from_expr(expr)` with `PrivacyMap::new(|_| MO::Distance::zero())`. A literal is fixed by the public query expression, not derived from private row values. Thus, when only the literal's **value** is considered, it has the same value for any two neighboring datasets, giving zero privacy loss. Existing native tests cover literal preservation and grouped literal emission, inspected but not run.

The [reference model](../../../../../../tools/tests/test_polars_privacy_free_expr_model.py) checks public literal values `0`, `17`, `-5` and `"public"` across 259 short datasets; every per-group literal value equals the corresponding public constant.

### Whole-plan caveat

An expression's zero-privacy map does not imply that a **full grouped result** containing that expression is privacy-free. For example, evaluating `group_by("private_key").agg(lit(17))` on a dataset containing only key `a` returns row `(a,17)`, while a dataset containing only key `b` yields `(b,17)`. The per-row literal remains constant, yet the **group-key presence** differs. The independent model makes this distinction explicit. The privacy of releasing keys and group structure belongs to higher-level private lazy-frame composition, not to this leaf's literal map.

The returned `ExprPlan` encapsulates query-plan context. This constructor is documented under the OpenDP honest-but-curious, single-evaluation contract; the audit does not assert privacy for arbitrary inspection, reuse, or serialization of that plan, nor did it execute the native grouped Polars behavior. Whole-query privacy remains **Partial**.

## Findings and next checks

No new defect in the literal value's source-level zero-privacy argument or AST guard. Test the native `make_private_lazyframe` composition path for private grouping keys and public literals, especially any query that emits group keys without public-key invariants. Confirm that the whole-frame privacy map accounts for the key release separately. [Coordination task #84](https://github.com/opendp/opendp-audit/issues/84).
