---
schema_version: 1
source: rust/src/measurements/make_private_expr/expr_dp_quantile/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/make_private_expr/expr_dp_quantile/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated `make_expr_dp_quantile` and `DPQuantileShim`; candidate-derived public fill, score/noise/index expression assembly and privacy delegation. The already audited discrete-score, noisy-max, index-candidates and median-alias implementations are dependencies, not re-audited.
- **Invariants:** The fill value is obtained only from public candidates. The score uses imputed private input with the original public alpha and candidate set; noisy-max selects minimum score with the public scale; a final deterministic index lookup returns one of the original candidates. No raw quantile shim may execute, and only the certified private-construction path may release the result.
- **Assumptions:** Polars literal candidate extraction, scalar median, `fill_null`, `fill_nan`, and schema inference behave according to the pinned Polars version; the downstream scorer/noisy-max/index components satisfy their contracts. A source-only graph inspection and independent reference model cannot certify those native behaviors or the resulting privacy bound.
- **Reviewed upstream SHA:** `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. [Source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_dp_quantile/mod.rs), [private dispatch](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/mod.rs), [stable score](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_discrete_quantile_score/mod.rs), [noisy max](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_noisy_max/mod.rs), [candidate indexing](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_index_candidates/mod.rs), [native Polars test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/test.rs). Coordinating [audit task #95](https://github.com/opendp/opendp-audit/issues/95).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::make_private_expr::expr_dp_quantile::DPQuantileShim::call_udf` | privacy/raw-shim-execution-guard | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Shim boundary](#shim-boundary) |
| `measurements::make_private_expr::expr_dp_quantile::DPQuantileShim::get_field` | correctness/raw-shim-schema-compatibility | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Shim boundary](#shim-boundary) |
| `measurements::make_private_expr::expr_dp_quantile::make_expr_dp_quantile` | correctness/public-candidate-imputation | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Public candidate imputation](#public-candidate-imputation) |
| `measurements::make_private_expr::expr_dp_quantile::make_expr_dp_quantile` | correctness/score-noise-index-assembly | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Private selection graph](#private-selection-graph) |
| `measurements::make_private_expr::expr_dp_quantile::make_expr_dp_quantile` | privacy/candidate-independence | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Public candidate imputation](#public-candidate-imputation) |
| `measurements::make_private_expr::expr_dp_quantile::make_expr_dp_quantile` | privacy/end-to-end-composition | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Privacy and test limits](#privacy-and-test-limits) |

## Analysis

### Shim boundary

`DPQuantileShim::call_udf` and the FFI `dp_quantile` function both raise `InvalidOperation` with an instruction to use `make_private_lazyframe`. The shim cannot directly execute a private quantile. Its `get_field` expects exactly **one** field and clones that field. The logical shim matched by the private-expression dispatcher, however, carries four expressions (`input, alpha, candidates, scale`). Whether the Polars schema planner passes one or four fields at this boundary, and whether raw `collect_schema` is supported, was **not** determined by compiled execution. Accordingly full raw-shim schema compatibility remains Partial and no schema bug is asserted.

`PrivateExpr` in `make_private_expr/mod.rs` matches `DPQuantileShim` with four arguments and routes it to this constructor, which again matches the same arity. Incorrect node kind/arity is rejected during construction; it cannot shortcut the private-dispatch path.

### Public candidate imputation

The constructor first calls `make_stable` on the original input to recover its column dtype. It extracts a **public literal** `Series` from the candidate expression (`literal_value_of::<Series>`), obtains `Series::median()` as an `f64`, and fails at construction if no median is available. The median may be **between** public candidates, especially for an even number of candidates; it is not itself a private estimate.

The constructor rewrites the data input as `input.fill_null(lit(midpoint))`, and, if the original data dtype is float, also `fill_nan(lit(midpoint))`. The resulting preprocessed input is then passed to the **stable** discrete-score plugin, which separately checks candidate ordering, candidate nulls, floating NaN eligibility, alpha range and dtype conversion. This glue path does not claim the original domain describes imputed values without checking the rewritten expression. Note that the public `f64` midpoint can promote input integer widths, potentially losing integer precision; native dtype/rank behavior was not tested here and should not be treated as proven invariant.

The existing singleton-NaN candidate-validator discrepancy is covered by [upstream open PR #3243](https://github.com/opendp/opendp/pull/3243) at the pinned revision. This constructor's public-median check is **not** a substitute for the scorer's complete candidate validator; no duplicate issue was opened for that known defect.

### Private selection graph

The source builds the following pipeline using `apply_plugin`:

1. `DiscreteQuantileScoreShim(preprocessed_input, alpha, original_candidates)`, scoring each public candidate.
2. `NoisyMaxShim(score_array, lit(true), scale)`, selecting a **minimum** score after private noise.
3. `IndexCandidatesShim(private_index, original_candidates)`, deterministically mapping a valid private index to an original candidate.

It finally calls `make_private(input_domain, input_metric, output_measure, global_scale)` on the **entire** expression. The dispatcher recursively recognizes final candidate-indexing and then noisy-max; index-to-candidate mapping is a postprocessor with no separate private-data query. The noisy-max measurement receives the score transformation and its sensitivity and calibrates its own privacy map; this constructor does **not** create a second noisy query or charge a second budget. The exact source-level expression order and argument forwarding are Audited.

### Privacy and test limits

The [independent reference model](https://github.com/opendp/opendp-audit/blob/main/tools/tests/test_polars_dp_quantile_glue_model.py) runs six Python standard-library tests, including exhaustive short-vector insert/replace score sensitivity for `alpha=1/2`; permutation invariance; public midpoint and null/NaN imputation; candidate index selection; and malformed public candidate controls. The reference model neither invokes OpenDP/Polars nor adds noise or proves a DP guarantee. It validates **mathematical glue preconditions**, not Polars runtime or the behavior of a randomized release.

The inspected pinned [native Rust `test_dp_quantile`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/test.rs) tests a Float64 median with explicit candidates, but was not run in this review. No new independent defect or privacy-budget undercount was established by this bounded source trace. Full end-to-end privacy calibration and candidate-output membership remain Partial until native execution checks the combined plugin chain, numeric casts and returned schema.

## Next checks

- Run version-matched OpenDP/Polars integration tests for non-null and nullable Integer/Float inputs, particularly `i64/u64` values greater than `2^53` whose cast to the public `f64` median type may lose precision; assert the released value belongs to the **original public candidate set**.
- Check raw `DPQuantileShim` schema inference via `collect_schema`, and normal rewritten `make_private_lazyframe` schema/collection, without presuming these paths accept identical argument field counts.
- Revisit the public candidate validator after upstream [PR #3243](https://github.com/opendp/opendp/pull/3243) is merged and retest the singleton-NaN boundary.
