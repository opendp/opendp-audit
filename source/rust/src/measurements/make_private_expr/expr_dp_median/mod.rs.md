---
schema_version: 1
source: rust/src/measurements/make_private_expr/expr_dp_median/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/make_private_expr/expr_dp_median/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated `DPMedianShim` and `make_expr_dp_median` on the Polars private-expression path, pinned to OpenDP `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`.
- **Invariant:** A DP median request must be exactly the DP quantile request with the public scalar `alpha=0.5f64`, preserving the input expression, candidate series, scale argument, global scale, output measure and metric. It must not bypass DP scoring, selection or privacy-map composition.
- **Assumptions:** `match_shim` identifies only the matching plugin and pads missing public arguments with literal nulls; `apply_plugin` constructs a replacement shim without executing the old shim; `PrivateExpr` recursively converts the new quantile expression. The prior private-quantile constructor and downstream privacy proofs are treated as dependencies, not re-established here.
- **Sources:** [Median implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_dp_median/mod.rs), [private-expression dispatch](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/mod.rs), [quantile delegation target](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_dp_quantile/mod.rs) and [shim helpers](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_expr_dp_median` | correctness/median-to-quantile-delegation | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Delegation and arguments](#delegation-and-arguments), [finite model](../../../../../../tools/tests/test_dp_median_delegation_model.py) |
| `make_expr_dp_median` | privacy/recursive-measurement-composition | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Privacy boundary](#privacy-boundary), [investigation](../../../../../../investigations/polars-median-quantile-score-delegation.md) |
| `DPMedianShim` | correctness/shim-output-type-and-arity | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Schema and invocation](#schema-and-invocation) |

## Analysis

### Delegation and arguments

`match_shim::<DPMedianShim, _>` produces the three positions `[input,candidates,scale]` or fails. The constructor calls `apply_plugin(vec![input,lit(0.5f64),candidates,scale],expr,DPQuantileShim)` and then delegates to `input.make_private(input_domain,input_metric,output_measure,global_scale)`. No intermediate randomization or release happens in this wrapper. The original candidate expression and scale argument are passed through unchanged. The scalar 0.5 is public and exact as binary64; downstream `score_candidates_constants` can represent it exactly as 1/2 in ordinary cases.

### Privacy boundary

Private-expression dispatch checks `DPMedianShim` before `DPQuantileShim` and recursively routes the rewritten expression through `make_expr_dp_quantile`. That constructor fills nulls/NaNs with a public candidate-series median, creates a discrete-quantile score plugin, privately selects the minimizing score index and finally maps it to the public candidate series. The wrapper itself does not assign or weaken a privacy map; the privacy guarantee depends on the downstream quantile score, noise and postprocessing contracts. End-to-end native OpenDP execution was not performed.

### Schema and invocation

The shim's `get_field` expects one data field and returns a clone of it; `function_options()` declares an aggregation. Calling the shim as a Polars UDF without the OpenDP private rewrite raises the data-independent `InvalidOperation` error, not a private-data-dependent computation. `match_shim` rejects more than three inputs; omitted trailing arguments become public null literals and are subject to downstream validation. Exact Polars field-resolution and FFI serialization semantics have **not** been verified against compiled OpenDP.

## Findings and next checks

The median wrapper's four-argument quantile delegation is **Audited** at the source level. The [independent finite model](../../../../../../tools/tests/test_dp_median_delegation_model.py) verifies the alpha-1/2 score relation and small-distance bounds; it is not native OpenDP runtime evidence. Existing quantile candidate validation and proof issues are tracked separately: [audit #9](https://github.com/opendp/opendp-audit/issues/9) and [pending upstream PR #3243](https://github.com/opendp/opendp/pull/3243).

**No new defect identified in the wrapper.** Next: compile both shim forms with actual Polars, verify FFI serialization and the output field for nullable integer/float inputs, and test private median releases under finite privacy budgets.
