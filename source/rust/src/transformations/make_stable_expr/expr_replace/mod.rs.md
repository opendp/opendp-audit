---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_replace/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_replace/mod.rs`

## Scope and assumptions

Review `make_expr_replace` and its literal helpers for the ordinary non-deprecated Polars `replace(old,new)` operation: output nullability, public-pattern validation, and data-dependent failure. Input expression is assumed already stable; `old` and `new` are public literals. Source is [OpenDP at `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_replace/mod.rs), with [OpenDP tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_replace/test.rs) and pinned [Polars replacement kernels](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-ops/src/series/ops/replace.rs) (`py-1.36.1`). This is source inspection and executed independent modeling, **not native OpenDP/Polars testing**. `replace_strict` and arbitrary optimizer rewrites are excluded.

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `transformations::make_stable_expr::expr_replace::make_expr_replace` | correctness/replacement-nullability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Finite-alphabet model](../../../../../../investigations/polars-replace-null-imputation-and-public-key-validation.md): 56,931 row cases, no understated nullity in model; native test not run. |
| `transformations::make_stable_expr::expr_replace::make_expr_replace` | privacy/data-dependent-failure | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Source-path analysis](#analysis): inspected rejection and late failure paths depend on public literals; other Polars paths remain unchecked. |
| `transformations::make_stable_expr::expr_replace::make_expr_replace` | correctness/duplicate-pattern-validation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Candidate issue #56](https://github.com/opendp/opendp-audit/issues/56): public duplicate `old` keys accepted by OpenDP constructor but rejected by pinned Polars upon execution. |

## Analysis

The constructor requires literal `old` and `new` expressions, requires their lengths to match or permits one broadcast replacement, excludes categorical input, materializes dynamic list literals, and checks dtype compatibility. It calls `output_domain.column.set_dtype(dtype)` to discard stale value bounds, then computes nullable as `input_nullable || new_contains_null`, overriding this to **false** when `old_contains_null && !new_contains_null`.

For unique public replacement keys, this null-elimination rule agrees with pinned Polars: [`get_replacement_mask`](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-ops/src/series/ops/replace.rs) matches NULL explicitly, `replace_by_single` fills null mask positions as true if `old` contains null, and `replace_by_multiple` uses a join with `nulls_equal: true`. An independently executed JavaScript model exhausted all unique `old` sequences of lengths 0–4 over `{NULL,-1,0,1}`, permitted `new` lists/broadcast values, both source nullability descriptors, and row values allowed by the descriptor. **8,133 mappings / 56,931 row cases:** zero null results declared non-nullable. This models the intended replacement semantics; it is not proof of backend execution, casting, or optimizer behavior.

**Public duplicate keys:** OpenDP validates only literal shape, length and type, not uniqueness. For `old=[1,1]`, `new=[10,20]`, input `Int32`, these OpenDP constructor checks pass. Pinned Polars [`replace`](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-ops/src/series/ops/replace.rs) calls `validate_old`, which enforces `old.n_unique()? == old.len()` at **execution**. The [Polars expression DSL](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-plan/src/dsl/mod.rs) only constructs the AST; it does not validate public key uniqueness. This is a predictable data-independent execution error from an accepted public parameter, not a demonstrated privacy leak. It is [tracked as Candidate #56](https://github.com/opendp/opendp-audit/issues/56); native compilation is outstanding.

The existing upstream tests cover scalar/list mappings, null imputation, null-valued replacements, and wrong dtype, but do not test duplicate public `old` keys. They were **inspected, not executed**. See [cross-file investigation](../../../../../../investigations/polars-replace-null-imputation-and-public-key-validation.md).

## Next checks

- Run native `py-1.36.1` OpenDP/Polars reproduction for [issue #56](https://github.com/opendp/opendp-audit/issues/56); add constructor-time uniqueness validation consistent with Polars NULL/NaN equality.
- Run optimized Polars tests for `old=[NULL,1]`, empty maps, and public dtype coercion.
- Check aggregation-context fill propagation and other optimizer/runtime paths before upgrading privacy coverage.
