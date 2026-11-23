---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_discrete_quantile_score/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_discrete_quantile_score/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated `make_expr_discrete_quantile_score`, `validate` and `match_discrete_quantile_score`; downstream `DiscreteQuantileScorePlugin` field inference and delegation to shared `score_candidates` are traced. OpenDP revision `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`.
- **Invariant:** The scorer must operate only on numeric, non-null, non-NaN input values and a nonempty, strictly ordered public candidate series; its output schema must describe one `Array<UInt64,candidates.len()>` per group, with a score sensitivity that contains actual score changes.
- **Assumptions:** The passed `StableExpr` handles its input domain correctly, Polars `strict_cast` and array fields have the pinned semantics, and the existing `score_candidates` sensitivity proof applies to validated inputs. A singleton NaN candidate violates the intended precondition at this upstream revision and is explicitly excluded from any unconditional proof assertion.
- **Sources:** [Scorer implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_discrete_quantile_score/mod.rs), [plugin glue](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_discrete_quantile_score/plugin_dq_score.rs), [shared score function](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/quantile_score_candidates/mod.rs), and [native Rust scorer tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_discrete_quantile_score/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_expr_discrete_quantile_score` | privacy/quantile-score-sensitivity | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Score map and output domain](#score-map-and-output-domain), [independent model](../../../../../../tools/tests/test_dp_median_delegation_model.py) |
| `make_expr_discrete_quantile_score` | correctness/quantile-score-output-schema | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Score map and output domain](#score-map-and-output-domain) |
| `validate` | correctness/candidate-preconditions | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Candidate and input validation](#candidate-and-input-validation), [upstream PR #3243](https://github.com/opendp/opendp/pull/3243) |
| `match_discrete_quantile_score` | correctness/literal-arity-and-type | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Argument extraction](#argument-extraction) |

## Analysis

### Candidate and input validation

The constructor first checks the stabilized input column is non-nullable and excludes NaN for floating types, then strictly casts public candidates to the input dtype and rejects candidate nulls. `validate` supports UInt32/UInt64, signed Int8/Int16/Int32/Int64 and Float32/Float64, but rejects UInt8/UInt16 and unsupported types. It then uses shared `check_candidates` to require nonempty, increasing candidates.

**Known gap:** `check_candidates` only compares adjacent pairs; a **singleton NaN** has no pair, so it currently passes the validator despite the total-order premise. This is already [audit #45](https://github.com/opendp/opendp-audit/issues/45) (closed as addressed by open [PR #3243](https://github.com/opendp/opendp/pull/3243)), **not a new issue** or a claim that upstream main is patched. A multi-element NaN candidate is rejected by the existing `partial_cmp` check.

### Score map and output domain

The constructor requires a finite upper group-length bound, derives `(alpha_num,alpha_den,size_limit)`, and creates an `Array<UInt64,candidates.len()>` field. Its output is an aggregation expression with `max_length=1`. The score plugin computes the shared quantile histogram and returns one fixed-size array of unsigned score values, with a public zero-array fill for absent groups.

The map derives the per-group `LInfDistance` change from `score_candidates_map` and carries the affected-group `L0` bound through unchanged. For the median special case with `alpha=1/2`, the uncapped score is `|#(x<c)-#(x>c)|` at each candidate. Its sensitivity is at most 1 per record insertion/deletion and 2 per fixed-length replacement. The [finite model](../../../../../../tools/tests/test_dp_median_delegation_model.py) verifies these bounds for small integer-valued datasets. This does not independently check Polars plugin execution or the preconditions of every composition.

**Known proof discrepancy:** The [`score_candidates.tex` postcondition](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/quantile_score_candidates/score_candidates.tex) uses `alpha_den` instead of `alpha_den-alpha_num` in the less-than coefficient. The shared implementation and bounded model use the latter. This is [audit issue #9](https://github.com/opendp/opendp-audit/issues/9), already reported.

### Argument extraction

`match_discrete_quantile_score` recognizes precisely three plugin inputs: `data,alpha,candidates`; `alpha` must extract as a public `f64` literal and `candidates` as a public `Series` literal. Missing or wrong argument types are rejected. The private quantile constructor builds this plugin through `apply_plugin`, preserving the candidate series and arguments for the subsequent private noisy-max stage.

## Findings and next checks

**No novel defect established.** Known shared candidate-validation and proof issues already have upstream/audit tracking. Compile and run the pinned scorer plugin with actual nullable/nonnullable, signed/unsigned and floating inputs, verify inferred array fields, test unmerged PR #3243 and check all scale/alpha edge cases. Current verification **Partial** because the executable numerical model is not a native OpenDP/Polars run.
