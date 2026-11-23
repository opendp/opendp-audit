---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Quantile candidate validation accepts a single NaN

## Invariant and threat model

The non-deprecated `check_candidates<T: Number>` helper must reject empty, non-strictly increasing, or **non-totally-ordered** public candidate sets. This precondition supports the rank-score proof used for discrete quantile selection. In particular, a singleton floating-point NaN must not be considered a valid strictly increasing, totally ordered set. A failure of this precondition is a correctness and proof-contract discrepancy; it is **not**, by itself, a differential-privacy violation.

## Affected symbols and source audits

- [Scorer source audit](../source/rust/src/transformations/quantile_score_candidates/mod.rs.md) and [pinned `check_candidates`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/quantile_score_candidates/mod.rs#L100-L122).
- [Proof theorem](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/quantile_score_candidates/check_candidates.tex) requires a totally ordered candidate set, claiming that unsuccessful pairwise comparisons are excluded.
- [`make_quantile_score_candidates`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/quantile_score_candidates/mod.rs#L48-L98) calls this helper and separately checks only that the *input* domain excludes NaN.
- [Non-deprecated Polars `make_expr_discrete_quantile_score::validate`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_discrete_quantile_score/mod.rs) checks candidates' null count, casts their dtype, and then calls the same helper. The broader Polars DP-quantile preprocessing/output-index study is reserved under [audit task #42](https://github.com/opendp/opendp-audit/issues/42); this investigation does not assert an end-to-end Polars release.

## Reasoning and evidence

**Minimal witness:** `check_candidates(&vec![f64::NAN])` (likewise `f32::NAN`). The source rejects an empty vector, then tests `candidates.windows(2).any(...)`. For a one-element vector, `windows(2)` produces **zero** windows; `.any(...)` is false without attempting a `partial_cmp` on NaN, so the function returns `Ok(())`. This contradicts the total-order postcondition and the theorem's statement that the comparison check establishes total order. With two elements and at least one NaN, `partial_cmp` returns `None` and the helper correctly rejects the set. A singleton candidate is therefore a missing branch, not a failure of the `partial_cmp` behavior.

**Actually executed:** The standard-library [Python source-control-flow regression model](../tools/tests/test_quantile_candidate_singleton_nan.py) asserts the singleton NaN discrepancy for float candidates, checks normal accepted/rejected boundaries, and characterizes 10,000 deterministic length-0-to-4 candidate sequences. It finds mismatches with an independently specified total-order contract **only** for singleton NaN in those modeled sequences. This tests a direct translation of Rust's window/comparison logic, **not compiled OpenDP Rust or Polars**. The audit validator and Python validator tests were executed locally as well.

**Contract and impact:** The public `make_quantile_score_candidates` can select an input domain excluding NaN and pass a separate NaN candidate to this validator. The Polars discrete scorer's `validate` also delegates its strictly ascending candidate check here; NaN is not a null. However, the full `make_expr_dp_quantile` path computes a candidate median first, and its precise runtime behavior for all-NaN candidates has not been independently executed. Do **not** infer a privacy loss, output-domain violation, or successful end-to-end DP-quantile release solely from this constructor-validation gap.

## Findings

- **Candidate-validation/total-order contract violated** in the singleton floating-point NaN case. [Audit issue #45](https://github.com/opendp/opendp-audit/issues/45), verification **Candidate** (source-level deterministic witness), upstream disposition **Pending PR**: [opendp/opendp#3243](https://github.com/opendp/opendp/pull/3243) is open and unmerged, with exactly the needed per-candidate self-comparison guard.
- This is **distinct** from [audit issue #9](https://github.com/opendp/opendp-audit/issues/9) (the missing proof coefficient for the rank score). An initial targeted search missed open upstream [PR #3243](https://github.com/opendp/opendp/pull/3243); its patch was subsequently inspected and verified to reject both singleton NaN types, and it adds regression tests. Audit issue #45 was closed on that evidence; do not treat the PR as fixed on upstream main.
- The shared checker is otherwise consistent with its ordering contract on the tested finite and multi-element float cases. No privacy-underestimation counterexample was found or claimed.

## Unresolved questions

Run the native Rust regressions already included in unmerged PR #3243, for `check_candidates(&vec![f32::NAN])` and `check_candidates(&vec![f64::NAN])`, ensuring they return `Err` while singleton ordinary values remain valid. The proposed correction verifies self-comparability of **each** candidate before comparing adjacent pairs; review whether such a restriction should be generic over all `Number` implementations. Independently exercise the non-deprecated Polars `make_expr_discrete_quantile_score` constructor with a singleton NaN candidate; coordinate broader DP-quantile effects with task #42.
