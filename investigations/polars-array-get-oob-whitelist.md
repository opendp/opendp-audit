---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Polars array.get(false) passes an infallibility gate despite data-dependent OOB errors

## Invariant, scope and security relevance

A stable grouped query or contribution-truncation plan must not allow a fallible expression to fail as a function of protected records. `check_infallible` is the common syntactic gate for aggregation expressions in `make_stable_group_by` and `truncate_domain`. This review is limited to `FunctionExpr::ArrayExpr(ArrayFunction::Get(bool))`, not the full whitelist, all aggregation functions, or an end-to-end differential-privacy proof.

A public array column width of 2 and a private integer index can give success for index 0 but an out-of-bounds error for index 2. The difference in returned error status is potentially privacy-relevant when visible to a caller. **This is a source-confirmed admission mismatch and a potential privacy side channel; a compiled OpenDP private-release reproduction was not executed.**

## Pinned upstream cross-file trace

1. [OpenDP source audit](../source/rust/src/transformations/make_stable_lazyframe/group_by/mod.rs.md), [`check_infallible_function`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/group_by/mod.rs): `ArrayFunction::Get(_)` is accepted alongside `ArrayFunction::Join(_)` and others, then `check_inputs!(aligned_rows)` recurses on operands. The Boolean `null_on_oob` value is ignored. By contrast the `ListFunction::Get(null_on_oob)` arm explicitly rejects `false` with `MakeTransformation`.
2. [OpenDP `make_stable_group_by`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/group_by/mod.rs) calls `check_infallible(agg, Resize::Allow)` on every aggregate expression before constructing its advertised stability map. [`truncate_domain`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/truncate/mod.rs) applies the same check to aggregate expressions in its final group-by.
3. [OpenDP `rust/Cargo.toml`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/Cargo.toml) pins Polars `=0.52.0` and `py-1.36.1` as the patched git tag. The exact [Polars enum](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-plan/src/dsl/function_expr/array.rs) includes `Get(bool)`, and [Polars' `ArrayNameSpace::get`](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-plan/src/dsl/array.rs) constructs `Get(null_on_oob)`.
4. Polars itself classifies [`IRArrayFunction::Get(false) => true` in `AExpr::is_fallible_top_level`](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-plan/src/plans/aexpr/mod.rs), alongside `IRListFunction::Get(false)`. The pinned [array-get implementation](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-ops/src/chunked_array/array/get.rs) forwards the flag to the array indexing operation, while the pinned [Polars tests](https://github.com/pola-rs/polars/blob/py-1.36.1/py-polars/tests/unit/operations/namespaces/array/test_array.py) assert a `ComputeError` for out-of-bounds **series-valued** indices with `false` and a null result with `true`.

## Minimal property witness

Take a fixed-width `Array(Int64, 2)` public-schema column `a`, a public group key `k`, and a private integral column `idx`. Consider the `ArrayFunction::Get(false)` expression `col("a").arr().get(col("idx"), false)` inside a group-by aggregate. Two adjacent inputs have the same single row with `a=[5,6]`, `k=0`, and `idx=0` versus `idx=2`. The first index is valid, the second is out of bounds.

The pinned Polars dependency recognizes this expression as potentially fallible. A **compiled Polars 1.36.1 runtime regression** now reproduces the grouped index-column behavior: index 0 succeeds, index 2 raises `ComputeError` with `null_on_oob=false`, and index 2 returns null with `true`. OpenDP's whitelist admits both variants and only checks their inputs for permitted structure. The input index is not a statically known literal, so the additional Polars schema-time literal-index checks do not establish that every value lies in bounds.

**Observation boundary:** This witness establishes **potential data-dependent failure** in a path admitted by OpenDP's syntactic check. Whether a particular public `make_private_lazyframe` construction allows this exact aggregate and reveals an error at collection time requires a compiled integration test. Do not label a privacy guarantee violation as reproduced on OpenDP without that integration check.

## Executed verification and disposition

**Actually executed:** A standalone Python standard-library [source model](../tools/tests/test_array_get_oob_whitelist_model.py) compared OpenDP's unconditional `Get(_)` acceptance with fallible `Get(false)` indexing across 20,672 deterministic boundary/random cases. The audit repository's local schema validator and 25 Python unit tests passed. Separately, the audit's [real Polars 1.36.1 runtime regression](../tools/integration/polars_array_get_runtime.py) ran **four compiled-Polars tests successfully** in [GitHub Actions run #45108716569](https://github.com/opendp/opendp-audit/actions/runs/45108716569). Those tests exercise grouped fixed-size array indexing with a column-valued index. In the same successful run, the [compiled native OpenDP constructor regression](../tools/integration/polars_array_get_open_dp.rs) confirmed that the stable group-by constructor **accepts** the fallible `ArrayFunction::Get(false)` expression on pinned main `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` and **rejects** it on unmerged PR #3155 head `63a32139856e16b7d415766e6a9becc25aa748e1`. The pinned main/PR Rust job and the four Polars tests all completed successfully in [CI #45108716569](https://github.com/opendp/opendp-audit/actions/runs/45108716569). This **reproduces constructor admission and the backend's error behavior, but not a private LazyFrame release**.

**Additional source inspected:** OpenDP and Polars source and Polars' checked-in `test_array_get` tests. Both the OpenDP constructor comparison and the grouped Polars runtime behavior were subsequently executed natively, as described above. An initial targeted issue/PR search missed [upstream PR #3155](https://github.com/opendp/opendp/pull/3155) because its title refers broadly to stable group-by hardening. Its reviewed, **unmerged** head `63a32139856e16b7d415766e6a9becc25aa748e1` removes `check_infallible` and replaces it with a restrictive `check_permutation_invariance` traversal that rejects `ArrayFunction` variants not explicitly allowed. This is a proposed fix, not a fix on upstream main.

**Finding:** [Audit issue #71](https://github.com/opendp/opendp-audit/issues/71) (labeled `privacy`) was closed after discovery of the open fix PR. Verification is now **Reproduced for the OpenDP constructor-admission defect** and the separate Polars data-dependent runtime error; the **privacy channel remains Candidate**, because an OpenDP private-release execution has not been confirmed. Upstream disposition: **Pending PR** [#3155](https://github.com/opendp/opendp/pull/3155), not merged or fixed on the pinned main SHA. This is separate from the earlier [group-by influence-bound audit](polars-groupby-influence-bound.md), which explicitly assumed total aggregation expressions and excluded the whitelist.

## Follow-up

The [native CI constructor comparison](https://github.com/opendp/opendp-audit/actions/runs/45108716569) **passed** for both pinned main (accepted) and PR #3155 (rejected). Next, test whether an actual private LazyFrame can evaluate this expression and expose a data-dependent error to a caller, including the contribution-truncation route; extend native tests beyond the stable constructor. No quantitative privacy claim is supported yet.
