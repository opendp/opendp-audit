---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_len/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_len/mod.rs`

## Scope and assumptions

Reviewed the **non-deprecated** `make_expr_len` Polars expression transformation at pinned OpenDP SHA `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. The review checks `Expr::Len` dispatch, grouped output-domain membership and the delegated `counting_query_stability_map`. The output-domain postcondition requires every valid input plan to produce an `ExprPlan` admitted by the claimed `ExprDomain`. We assume standard grouped Polars `len()` semantics (one result per distinct grouping key); this review did not run the native Rust/Polars constructor or its integration tests.

- Pinned [implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_len/mod.rs), [native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_len/test.rs).
- [`ExprDomain::member`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/expr/mod.rs) and [`Margin::member`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/frame/mod.rs); [sibling count constructor](../expr_count/mod.rs.md).
- [Cross-file investigation](../../../../../../investigations/polars-grouped-len-output-domain.md) and [executed independent reference model](../../../../../../tools/tests/test_polars_grouped_len_domain_model.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_expr_len` | correctness/grouped-output-domain-membership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Two-group counterexample](#grouped-output-domain-counterexample); [audit issue #78](https://github.com/opendp/opendp-audit/issues/78) |
| `make_expr_len` | privacy/grouped-output-domain-postcondition | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Contract impact](#contract-impact) |
| `make_expr_len` | privacy/count-stability-map | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Sensitivity analysis](#sensitivity-analysis) |

## Analysis

### Grouped output-domain counterexample

The constructor extracts `old_margin = input_domain.context.aggregation("len")?`, then constructs an output margin with `by: old_margin.by`, `max_length: Some(1)`, **`max_groups: Some(1)`**, and the unchanged invariant.

For a valid input frame with two rows `(by="a", x=1)` and `(by="b", x=2)`, an aggregation context `by=[col("by")]` imposes no one-group restriction. `group_by("by").agg(len())` returns two distinct grouping keys, each with one length value. By its source definition, `ExprDomain::member` executes this grouping and then checks the resulting frame against the output `Margin::member`. That member function counts distinct `by` groups and checks `num_groups ≤ max_groups`. Here it rejects `2 ≤ 1`. Consequently a successful grouped `len()` transformation declares an output domain that does not contain its own intended output.

This is a source-level **output-domain postcondition violation**, independent of any particular differential privacy noise calibration. [Audit issue #78](https://github.com/opendp/opendp-audit/issues/78) records the exact witness and a proposed upstream Rust regression test. Its sibling `make_expr_count` instead carries `max_groups: margin.max_groups` through to the output; it does not have this particular mismatch.

The `Some(1)` output-group count *is* appropriate when `margin.by` is empty and `select([len()])` yields a single aggregate result. The error is applying that restriction unconditionally to grouped aggregation.

### Contract impact

A valid stable transformation's output must satisfy its output domain because later privacy proofs may rely on that domain. An incorrectly narrow descriptor violates this foundational correctness contract and can invalidate downstream reasoning if consumed. No concrete privacy-budget undercount, data-dependent failure, or distinguishing randomized release was demonstrated. Therefore the **privacy impact is unconfirmed** even though a domain-postcondition mismatch is source-confirmed. Native integration testing and downstream composition review remain necessary.

### Sensitivity analysis

The transformation delegates its map to `expr_count::counting_query_stability_map(margin.invariant)`. For `Invariant::Lengths`, the grouped length vector is fixed across neighboring datasets and a zero distance bound is correct under the invariant's definition. Without this invariant, `min(l1, l0^(1/p)·linf)` is a conservative bound for grouped length differences for `p=1,2`; these properties were checked in the [independent finite model](../../../../../../tools/tests/test_polars_grouped_len_domain_model.py). The model does not execute Rust `InfSqrt` or numerical edge cases. The sensitivity bound itself is **not** the identified defect.

## Findings and next checks

**New source-confirmed correctness defect:** grouped `len()` incorrectly declares at most one output group, for inputs with two or more valid grouping keys. Existing issue/PR searches found no exact upstream fix; [audit issue #78](https://github.com/opendp/opendp-audit/issues/78) is the tracked candidate. Do not confuse this with upstream [#3152](https://github.com/opendp/opendp/issues/3152), which concerns pairwise bounds derived from an *input* margin.

A likely repair is to preserve `old_margin.max_groups` for grouped expressions, as in `make_expr_count`, and use `Some(1)` only for ungrouped `select([len()])` where applicable. Execute the Rust regression from #78 and verify the downstream noise/metric composition before asserting complete privacy soundness.
