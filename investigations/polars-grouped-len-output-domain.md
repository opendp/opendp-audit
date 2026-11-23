---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Polars grouped `len()`: output-domain cardinality mismatch

## Property and threat model

For a stable transformation `T: (D,M) -> (D',M')`, the output carrier must belong to `D'` for every input in `D`. An output-domain guarantee can be used by subsequent transformations and measurement proofs; making the output domain **too restrictive** is not a harmless loss of precision if valid outputs lie outside it.

The non-deprecated Polars `make_expr_len` constructor builds an aggregation expression over the *same grouping keys* as the input, but sets `max_groups=Some(1)` unconditionally. When grouped by a nonempty key list with multiple possible key values, its output has one row **per distinct group**, violating the declared output-domain group limit. This is a **confirmed source-level correctness bug**; possible privacy implications remain unquantified.

Source evidence:
- [`make_expr_len` source audit](../source/rust/src/transformations/make_stable_expr/expr_len/mod.rs.md), [pinned constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_len/mod.rs) and [existing upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_len/test.rs).
- [`make_expr_count` contrast](../source/rust/src/transformations/make_stable_expr/expr_count/mod.rs.md), [pinned constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_count/mod.rs).
- [`ExprDomain::member`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/expr/mod.rs), [`Margin::member`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/frame/mod.rs), and [`Invariant::Lengths` definition](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/frame/mod.rs).
- [Independent reference test](../tools/tests/test_polars_grouped_len_domain_model.py), actually executed locally (5 passing tests).
- [Audit defect issue #78](https://github.com/opendp/opendp-audit/issues/78) with an upstream-ready Rust regression sketch.

## Proof of the source-level contradiction

Use the valid input frame with rows `(by="a",x=1)` and `(by="b",x=2)`. A `LazyFrameDomain` with `by`/ `x` numeric or string atom domains and no `max_groups` restriction admits these rows. Its aggregation context grouped by `col("by")` carries that grouping expression in `Margin.by`.

The `make_expr_len` output domain has:

```rust
Margin {
    by: old_margin.by,                 // {col("by")}
    max_length: Some(1),              // one expression value per group: valid
    max_groups: Some(1),              // only one group total: invalid
    invariant: old_margin.invariant,
}
```

The transformation's `Function::from_expr(len())` generates `ExprPlan` with a length expression. By the [domain membership implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/expr/mod.rs), grouped membership constructs `frame = plan.group_by([col("by")]).agg([len()])`, yielding two output rows, one per original grouping key. It then checks `margin.member(frame.lazy())`. This [membership predicate](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/frame/mod.rs) computes the number of distinct `by` groups in that output (two) and compares it with `max_groups` (one). The result is false, although the input was admitted and the expression succeeded.

This contradicts the stable-transformation output-domain postcondition. It is not merely a loose or non-tight sensitivity bound, and the output margin is not just a scalar-cardinality descriptor: the copied nonempty `by` expresses an actual group-by on the result.

**Boundary that works:** With no `by` keys (ordinary `select([len()])`), the output has exactly one aggregate result even for empty input; `max_groups=Some(1)` is compatible with that case. With one distinct grouping key, the grouped output also fits. The bug manifests with **at least two distinct group keys** permitted by the input domain.

**Contrasting implementation:** `make_expr_count` emits the same `max_length:Some(1)`, but preserves `max_groups: margin.max_groups` instead of narrowing it to one. This makes its grouped output cardinality descriptor conservative.

## Executed reference-model verification

The [standalone standard-library model](../tools/tests/test_polars_grouped_len_domain_model.py) was executed locally as `python -m unittest -v /mnt/data/test_polars_grouped_len_domain_model.py`, with **5 passing tests**:

- A two-group frame is admitted by the input margin; the `make_expr_len` output margin rejects it while `make_expr_count`'s inherited output margin accepts it.
- Exhaustive **1,365** input tuples of length 0–5 over four group keys: every output with two or more distinct groups violates the hardcoded one-group limit; zero/one-group cases fit. The sibling count margin admits them when the allowed input limit is four.
- Ungrouped `select([len()])` yields one aggregate result and is compatible with a one-group margin.
- A hypothetical repair preserving the input `max_groups` admits a three-group frame while retaining `max_length=1`.
- **268,324** pair/statistic comparisons across 259 small grouped datasets and four count functions (`len`, non-null `count`, `null_count`, `n_unique`) confirm conservatism of the idealized `min(l1, l0·linf)` and `min(l1, sqrt(l0)·linf)` bounds. This supports the count stability formulas separately from the domain bug.

These reference tests do not execute compiled OpenDP or Polars; they assume conventional semantics for grouping and counts, and reproduce the exact source-declared margin parameters. The Rust constructor, `ExprDomain::member`, actual query-planner behavior, edge types and directed arithmetic still need native tests.

## Deduplication and disposition

Searched upstream and audit issues and upstream pull requests for `make_expr_len`, grouped `len`, and `max_groups`/output-domain behavior. No existing issue or open corrective PR specifically covered this mismatch. [Upstream #3152](https://github.com/opendp/opendp/issues/3152) concerns **pairwise privacy accounting with a user-specified input** `max_groups` bound. It is distinct from this constructor's **unconditionally narrowed output** `max_groups`. Filed [audit issue #78](https://github.com/opendp/opendp-audit/issues/78), labeled correctness/privacy because the invalid domain certificate can affect proof assumptions, without asserting a demonstrated budget violation.

**Next checks:** Run the Rust regression in issue #78, preserving multiple grouping keys. Repair grouped `max_groups` retention (possibly special-case ungrouped `select`). Then verify output-domain membership, downstream expression composition and actual privacy maps against the repaired bounds.

**Privacy status:** **Partial**. Source-level domain contract violation established; end-to-end DP exploitability unverified. No upstream code modified.
