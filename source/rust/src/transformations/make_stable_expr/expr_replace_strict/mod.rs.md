---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_replace_strict/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_replace_strict/mod.rs`

## Scope and assumptions

- **Scope:** The output-domain datatype contract of `make_expr_replace_strict` when the Polars `replace_strict` expression specifies an explicit `return_dtype`. This is a single-property source audit of an active non-deprecated Polars transformation, not a review of all replacement semantics or an end-to-end privacy proof.
- **Invariant:** For every successfully constructed stable expression, the declared `ExprDomain.column.dtype()` must match the runtime Polars expression result datatype, so downstream transformations are not certified using the wrong type.
- **Assumptions:** Polars honors an explicitly supplied `return_dtype`, as stated in [its expression API documentation](https://docs.pola.rs/api/python/stable/reference/expressions/api/polars.Expr.replace_strict.html) and demonstrated by the regression in [upstream PR #3214](https://github.com/opendp/opendp/pull/3214). `DataType::Int32` and `DataType::String` are distinct; the input column and replacement literals are compatible with the current constructor's other guards.
- **Reviewed upstream:** `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`; [constructor and domain construction](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_replace_strict/mod.rs), [cast guard](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_replace/mod.rs), [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_replace_strict/test.rs), [`SeriesDomain::set_dtype`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/series/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `transformations::make_stable_expr::expr_replace_strict::make_expr_replace_strict` | correctness/output-dtype | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Accepted datatype mismatch](#accepted-datatype-mismatch); [upstream issue #3213](https://github.com/opendp/opendp/issues/3213) |

## Analysis

### Accepted datatype mismatch

**Finding (incorrect domain certification on upstream `main`):** The constructor validates the optional `return_dtype` against `new_dtype`, but then unconditionally records `new_dtype` as the output-domain datatype. When these differ and the cast guard accepts the conversion, the returned transformation advertises a datatype different from the actual Polars result.

A minimal source-level example, using the same inputs as the new upstream fix's test, is:

```rust
let expr = col("a").replace_strict(
    lit(1i32),
    lit(2i32),
    Some(lit(3i32)),
    Some(DataType::String),
);
```

Consider an input domain with column `a` typed `Int32`, and an input LazyFrame containing `a = [1, 2, 3]`. The prior expression is stable. The `old`, `new`, and `default` values are scalar literals of type `Int32`, so all length checks pass. The optional `return_dtype` is a literal `String`. In `expr_replace::is_cast_fallible`, a destination `String` returns `false` for the cast-fallibility predicate; the constructor therefore accepts `new_dtype = Int32` with `return_dtype = String`. The default's datatype equals the new datatype, so it also passes.

The constructor then executes `output_domain.column.set_dtype(new_dtype)?`, recording `Int32`, while the constructed output expression forwards `return_dtype: return_dtype.clone()` to Polars. Polars returns a string Series (the values are `["2", "3", "3"]`). Thus `output_domain.column.dtype() = Int32` but the runtime column dtype is `String`. The type mismatch violates the output-domain postcondition and can invalidate downstream type-based reasoning. This review does **not** establish a specific privacy-budget breach.

The existing [upstream unit-test helper](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_replace_strict/test.rs) checks result values and nullability but does not assert equality between the declared domain datatype and collected Polars schema; the differing-`return_dtype` case is absent.

### Upstream disposition and limitations

**Already reported / pending fix.** [Upstream issue #3213](https://github.com/opendp/opendp/issues/3213) describes this exact defect. [Upstream PR #3214](https://github.com/opendp/opendp/pull/3214), open and unmerged at review, replaces the unchecked `new_dtype` assignment with inferred output type, validates it, and adds an explicit `Int32`-to-`String` test asserting the declared domain dtype matches the collected schema. The PR contains related hardening changes that were not separately audited here. No duplicate defect issue is necessary in the audit repository. Coordination: [audit task #36](https://github.com/opendp/opendp-audit/issues/36).

**Verification:** The evidence is source-level control-flow analysis of the pinned OpenDP revision, the published Polars API contract, and inspection of the pending upstream regression. **No compiled OpenDP Rust or Polars runtime was executed in this audit session.** The defect's practical reach beyond downstream datatype assumptions has not been measured. The audited status covers the stated output-dtype invariant for this explicit case only.

## Next checks

- Execute the concrete upstream regression against the reviewed `main` revision, verifying the disagreement between the declared domain and collected output schema.
- After PR #3214 (or a successor) merges, re-evaluate `return_dtype` and implicit output-type inference; do not mark this issue fixed while the PR remains open.
- Audit replacement nullability, coercion failures, reserved names, and nested categoricals separately.
