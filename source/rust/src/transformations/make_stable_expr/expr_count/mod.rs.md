---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_count/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_count/mod.rs`

## Scope and assumptions

Reviewed the **non-deprecated** `make_expr_count` and `counting_query_stability_map` implementations at pinned upstream `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. The scope is the grouping/output-domain metadata, optional-length invariant, and conservative L1/L2 sensitivity of `Count`, `Len`, `NullCount`, and `NUnique` strategies. Full Polars execution and numerical `InfSqrt` implementation remain separate dependencies; no native Rust/Polars code ran.

- [Upstream constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_count/mod.rs), [native Rust tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_count/test.rs).
- [Sibling `Expr::Len` source report](../expr_len/mod.rs.md), [cross-file investigation](../../../../../../investigations/polars-grouped-len-output-domain.md), and [reproducible reference tests](../../../../../../tools/tests/test_polars_grouped_len_domain_model.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_expr_count` | correctness/grouped-output-margin-preservation | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Output margin](#output-margin) |
| `make_expr_count` | privacy/length-invariant-zero-sensitivity | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Counting strategies](#counting-strategies) |
| `counting_query_stability_map` | privacy/groupwise-l1-l2-stability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Sensitivity model](#sensitivity-model) |

## Analysis

### Output margin

The constructor builds the output `ExprDomain` with `max_length: Some(1)` and **`max_groups: margin.max_groups`**, copying `margin.by` and `margin.invariant`. Each input group contributes one aggregate output value, while the *number* of groups remains determined by the input grouping. This is consistent with the postcondition expected by [`ExprDomain::member`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/expr/mod.rs) and [`Margin::member`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/frame/mod.rs) for the scoped integer count strategies.

This is the correct contrast to the separate [`make_expr_len` defect](../expr_len/mod.rs.md), where `max_groups: Some(1)` is hardcoded even if the group-by has multiple distinct keys (audit [issue #78](https://github.com/opendp/opendp-audit/issues/78)). The independent reference tests verify that a two-group count fits the preserved margin but fails the `make_expr_len` margin.

### Counting strategies

`make_expr_count` recognizes `AggExpr::Count` (with or without nulls), `NullCount`, and `NUnique`; it stabilizes the input expression and demands an aggregation context. To determine if a `Count` can use a fixed-group-length invariant, it checks that the input is a valid row-by-row expression and is non-nullable. `Count` with `include_nulls` has `Strategy::Len` and can use the invariant if the expression is row-local. `NullCount` and `NUnique` cannot use this zero-sensitivity shortcut, because the values contributing to the statistic can change even while total group lengths remain fixed.

The source sets `will_count_all` only for those qualifying cases, and forwards `Some(Invariant::Lengths)` to the stability map **only** then. When count_all is known and group lengths are invariant, the zero map is sound. The model evaluates the counting functions but does not reproduce Polars input-expression validation or every typed/null behavior; this property remains **Partial**.

### Sensitivity model

For an arbitrary (not fixed-length) counting statistic, changing `d_g` rows in group `g` can change the result by at most `d_g`. For `l0` affected groups, `l1 = Σ_g d_g`, and `linf = max_g d_g`, the output L1 norm is bounded by `min(l1, l0·linf)`, and the L2 norm by `min(l1, sqrt(l0)·linf)`. The source uses `inf_sqrt` and `inf_mul` for conservative arithmetic, with unsupported norms rejected. The independent standard-library model exhaustively checked **268,324** dataset-pair/statistic cases over four count strategies on 259 small grouped datasets and both norm bounds; no counterexamples.

These are idealized finite results. The compiled directed rounding implementation, Polars optimizer and native execution are **not verified**, so the full privacy property is **Partial**.

## Findings and next checks

No new defect identified in the bounded count-strategy sensitivity formulas or grouped margin preservation; the sibling standalone `make_expr_len` remains incorrect as tracked in [audit issue #78](https://github.com/opendp/opendp-audit/issues/78). Native Rust property tests should cover both paths with multiple grouping keys, fixed-length and nullable inputs, and unusual expression trees.
