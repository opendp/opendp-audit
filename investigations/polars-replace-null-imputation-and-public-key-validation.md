---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Polars replace null imputation and public key validation

## Invariant and threat model

A private query's stable `replace(old,new)` expression must conservatively declare output nullability. Null values must not be introduced in a domain advertised as non-nullable; nor may valid private input cause an unaccounted data-dependent execution failure. Malformed **public** replacement maps should be rejected promptly, but a deterministic failure on every private input is a correctness/availability problem, not by itself a differential privacy leak.

Reviewed OpenDP `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` and the exact locally patched Polars Python-tag `py-1.36.1` at `2a151c10fa76790711c2f75e6d012dd69c627ddd`. Scope is the ordinary non-deprecated `replace`, not `replace_strict` or all optimizations.

## Affected symbols and source audits

- [Primary source report](../source/rust/src/transformations/make_stable_expr/expr_replace/mod.rs.md) and [pinned OpenDP constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_replace/mod.rs).
- [Pinned Polars implementation](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-ops/src/series/ops/replace.rs) contains `replace`, `validate_old`, `replace_by_single`, and `replace_by_multiple`.
- [Polars `Expr::replace` AST constructor](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-plan/src/dsl/mod.rs) and [list-implode optimizer rewrite](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-plan/src/plans/conversion/type_coercion/mod.rs).
- [Existing OpenDP tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_replace/test.rs).

## Reasoning and evidence

### Nullability

The OpenDP formula is `nullable = input_nullable || new_has_null`; if `old_has_null && !new_has_null`, it forces `nullable = false`. For public *unique* old keys this is conservative:

1. With no null old key, null source values (if allowed) survive; the output descriptor inherits source nullability.
2. With at least one null new value, the output admits null even if that mapping key is absent from some datasets.
3. With a null old key and no null new values, every source null maps to a non-null value and other rows are non-null or map to non-null. The pinned single-value Polars path fills null matching masks as true when old contains null; the multi-value left join sets `nulls_equal: true`.

**Executed independent model:** JavaScript enumerated the finite alphabet `{NULL,-1,0,1}`: all 65 unique ordered old-key lists of lengths 0–4, their permitted corresponding new values or one broadcast replacement, and both source-nullability values with all admissible input row values. This produced **8,133** valid mapping configurations and **56,931** row/domain checks, with **zero** outcomes where a null result was advertised as non-nullable. The model uses exact equality and mapping semantics, not compiled Polars. No statement is made about other dtypes, NaN matching, casting or the optimizer.

### Duplicate public keys

OpenDP requires the mapping expressions to be public literals and checks only their length and datatype compatibility, not uniqueness. The literal mapping `old=[1,1]`, `new=[10,20]` with `Int32` input has matching lengths and dtypes and passes the visible constructor predicates. Pinned Polars' `replace` explodes the old list, calls `validate_old(&old)?`, and requires `old.n_unique()? == old.len()`. Since there is one unique key in two positions, execution returns an `InvalidOperation` error. The `Expr::replace` API creates an AST node without this check; the Polars planner's type-coercion handling wraps non-list arguments with `Implode` but does not enforce uniqueness.

**Finding:** [Audit candidate #56](https://github.com/opendp/opendp-audit/issues/56) tracks this low-severity deferred public-input validation problem. Its **full OpenDP constructor-to-collection path is Reproduced**: the compiled Polars 1.36.1 executor and native pinned-OpenDP Rust integration each passed. The accepted-but-failing malformed public mapping is a confirmed behavioral observation, not a privacy leak. Unlike nullability soundness errors, this is not evidence of private-data-dependent output/error behavior.

### Compiled Polars runtime reproduction

The [pinned-runtime integration script](https://github.com/opendp/opendp-audit/blob/0c8a70b192a444f1cb32d53bbbcecbd6c80a7c6e/tools/integration/polars_replace_runtime.py) ran against the **compiled Polars 1.36.1 wheel** and [passed all four tests in CI](https://github.com/opendp/opendp-audit/actions/runs/45104162426). Both a dataset with matching keys `[1,2]` and a dataset with no matching keys `[7,8]` raised `InvalidOperationError` at `collect()` for the same duplicate public keys `old=[1,1]`. The distinct-key control returned `[10,20]`, and `old=[NULL,1], new=[0,10]` imputed `[NULL,1,2]` to `[0,10,2]`. The runtime version assertion was `1.36.1`.

The companion [pinned OpenDP Rust integration test](https://github.com/opendp/opendp-audit/blob/0c8a70b192a444f1cb32d53bbbcecbd6c80a7c6e/tools/integration/polars_replace_open_dp.rs) **passed all three tests** in [the same GitHub Actions workflow](https://github.com/opendp/opendp-audit/actions/runs/45104162426) (compiled against OpenDP `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` and its patched Polars dependency). In `public_duplicate_old_keys_construct_but_fail_at_collection`, the OpenDP fallible constructor returns `Ok` for duplicate `old=[1,1]`, `new=[10,20]`, and collection returns an error mentioning `duplicates` on both datasets `[1,2]` and `[7,8]`. `distinct_public_keys_are_accepted` and `replacing_public_null_key_removes_nullity` also pass. The latter checks both the output data and the declared `nullable=false` descriptor. The native job completed successfully at **2026-11-23 03:15 UTC**; no upstream OpenDP source files were altered.

### Evidence limitations

The pinned source and existing tests were read using the GitHub connector. The finite-alphabet JavaScript model was executed independently; the three duplicate-key examples `[1,1]`, `[NULL,NULL]`, and `[1,NULL,1]` were also checked for nonuniqueness in the model. Compiled Polars was invoked in the dedicated CI integration job. Native OpenDP Rust compilation and constructor execution succeeded for the three scoped regression tests. This does not establish all Polars dtype/optimizer paths or a general privacy theorem. Existing unit tests exercise valid mapping/null imputation and mismatched dtypes but omit duplicate public patterns.

## Findings

- **No nullability underapproximation** in the 56,931 modeled row/domain combinations; completeness remains Partial due to untested compiled backend and casting.
- **Reproduced correctness defect:** pinned native OpenDP constructs a stable transformation for duplicate public old keys and then fails at Polars collection on both matching and nonmatching input values. The compiled Polars 1.36.1 wheel confirms the same behavior; [issue #56](https://github.com/opendp/opendp-audit/issues/56) remains open for an upstream constructor-time validation fix.
- **No new privacy leak established** within the limited review.

## Unresolved questions

- Implement constructor-time validation for duplicate *public* old keys in upstream OpenDP, with null/NaN semantics matching Polars, and change the native regression to require an early `MakeTransformation` error; recheck against the pinned Polars runtime.
- Check NULL/NaN key equality and string, float, integer cast behavior under optimized execution.
- Explore aggregation `fill` mapping and optimizer-specific behavior not included in the rowwise model.
