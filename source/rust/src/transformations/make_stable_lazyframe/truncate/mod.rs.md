---
schema_version: 1
source: rust/src/transformations/make_stable_lazyframe/truncate/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_lazyframe/truncate/mod.rs`

## Scope and assumptions

Review the **non-deprecated** `make_stable_truncate` wrapper and `truncate_id_bound` arithmetic, narrowly limited to consumption of matched truncation certificates, identity/stability under unordered identifiers, and original versus materialized group-key coordinates. The internal matcher is separately covered in [the matcher report](matching/mod.rs.md). Upstream revision: `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`.

- **Invariant:** Stable truncation must satisfy the unordered identifier metric, including invariance to permutations within a user at zero input distance. Per-group row bound products and influenced-group bounds must be conservative, and source certificate keys must refer to the correct original groups before materializing output keys.
- **Assumptions:** Numeric `InfMul` rounds conservatively or errors, the input and aggregation `StableDslPlan` transformations satisfy their contracts, and supported Polars operations execute successfully. No compiled OpenDP execution in this review.
- Sources: [wrapper](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/truncate/mod.rs), [matcher](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/truncate/matching/mod.rs), [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/truncate/test.rs); [cross-file investigation](../../../../../../investigations/polars-identifier-truncation-permutation.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_stable_truncate` | privacy/identifier-truncation-permutation-invariance | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Matched truncation execution](#matched-truncation-execution) and [source-supported witness](../../../../../../investigations/polars-identifier-truncation-permutation.md) |
| `make_stable_truncate` | correctness/group-key-certificate-materialization | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Certificate mapping](#certificate-mapping) |
| `truncate_id_bound` | privacy/contribution-bound-product | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Certificate mapping](#certificate-mapping) |

## Analysis

### Matched truncation execution

The constructor calls `match_truncations` and builds a stable transformation of the plan preceding the recognized truncations. The resulting execution closure replays the **original** matched `Filter` predicates and optional final `GroupBy`, not rewritten stable expressions. For each certificate key it checks that a stable row-by-row expression can be constructed, but at this pinned revision does not require execution of that stable expression to reproduce precisely the original expression. Hence a proof concerning the stabilized expression does not necessarily certify the unmodified expression executed later. Open [PR #3270](https://github.com/opendp/opendp/pull/3270) adds explicit expression-equality and certificate validation checks, while [PR #3158](https://github.com/opendp/opendp/pull/3158) addresses permutation-invariance failures.

A positional `int_range` truncation can select different values after permuting rows of a single identifier. The wrapper then replays that predicate and can aggregate the differing values. The independent model exhibits differing sums at identifier distance zero; this is a **source-supported risk with upstream fixes in progress**, not an executed OpenDP privacy attack in this audit.

### Certificate mapping

The stability map iterates `truncation_bounds` independently of the number of truncation operations. Therefore a single `And` filter yielding two recognized certificates does not cause a `zip` truncation/bound mismatch. Every certificate looks up its **original grouping expression** in the input `id_bounds`; when the final truncation is a group-by, it then remaps the returned `by` to materialized output columns. This reflects the merged upstream [PR #3087](https://github.com/opendp/opendp/pull/3087) fixing an earlier computed-group-key privacy defect.

`truncate_id_bound` derives row contributions as `num_ids_per_group * rows_per_id_group` and group contributions as the smaller of available global-id × groups-per-id and an existing direct group bound. It uses fallible `InfMul` to avoid unchecked overflow. This source-level trace does not independently prove the arithmetic backend or all combinations of missing bounds.

## Findings and next checks

No new distinct unreported defect beyond ongoing upstream [issue #3157](https://github.com/opendp/opendp/issues/3157) and [PRs #3158](https://github.com/opendp/opendp/pull/3158)/[#3270](https://github.com/opendp/opendp/pull/3270). Numeric certificate arithmetic appears conservative under its documented contracts; permutation invariance and exact replay remain **Partial**.

Validate native Polars releases for order-permuted datasets, strict-cast keys and malformed rank structs. Do not claim complete privacy certification until pending hardening PRs are evaluated.
