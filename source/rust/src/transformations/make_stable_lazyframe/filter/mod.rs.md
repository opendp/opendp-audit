---
schema_version: 1
source: rust/src/transformations/make_stable_lazyframe/filter/mod.rs
updated: 2026-11-22
---

# `rust/src/transformations/make_stable_lazyframe/filter/mod.rs`

## Scope and assumptions

Non-deprecated `make_stable_filter`: construction of a Polars frame-level filter, its boolean/row-local predicate checks, identity stability map, and preservation of valid output-domain margins. Reviewed [upstream source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/filter/mod.rs) and [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/filter/test.rs) at `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. Full privacy assessment assumes deterministic successful row-local predicate evaluation on both neighboring datasets; the compiled Rust/Polars runtime was not executed.

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `transformations::make_stable_lazyframe::filter::make_stable_filter` | privacy/row-local-filter-stability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Bound reasoning](#bound-reasoning), [model](../../../../../../investigations/polars-filter-stability-and-margins.md) |
| `transformations::make_stable_lazyframe::filter::make_stable_filter` | correctness/key-and-length-invariant-invalidation | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Margin reasoning](#margin-reasoning) |
| `transformations::make_stable_lazyframe::filter::make_stable_filter` | correctness/boolean-predicate-validation | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Predicate guard](#predicate-guard) |

## Analysis

### Bound reasoning

The constructor stabilizes the prior plan, constructs `t_pred` under `Context::RowByRow`, and returns `DslPlan::Filter` with the middle metric and identity stability map. For deterministic row-local predicate `p`, row multiplicities after filtering satisfy `n_F(X)(r) = n_X(r)·1[p(r)]`. Thus each absolute multiplicity difference is unchanged or zero, and multiset symmetric distance is nonincreasing. The same per-key inequality bounds groupwise `L0`, `L1`, and `L∞` distances. The independent [Python reference model](../../../../../../tools/tests/test_polars_filter_stability_model.py) passed **697,686** row-pair checks and **43,350** groupwise comparisons. It does not execute compiled Polars or certify all predicate subexpressions.

### Margin reasoning

For every output margin, `m.invariant = None`: frame filtering can delete the last record in a group and alter group lengths, so neither key nor length invariants survive. Existing upper bounds such as `max_length` and `max_groups` remain upper bounds when records are removed. The upstream test asserts margin invalidation; inspected but not run.

### Predicate guard

The predicate must have boolean dtype. It is checked in a row-by-row expression domain, which excludes aggregation-only predicates such as `Expr::Len` (see [source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_len/mod.rs)). This is not a complete audit of all data-dependent Polars errors or optimizer semantics.

## Findings

No new counterexample within the stated row-local model. Full stability is **Partial** pending native execution and predicate-contract verification. [Investigation](../../../../../../investigations/polars-filter-stability-and-margins.md); [audit task #43](https://github.com/opendp/opendp-audit/issues/43).

## Next checks

Native Rust/Polars grouped and nullable-predicate integration tests; error-path and optimizer review.
