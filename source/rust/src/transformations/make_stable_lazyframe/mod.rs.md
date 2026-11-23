---
schema_version: 1
source: rust/src/transformations/make_stable_lazyframe/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_lazyframe/mod.rs`

## Scope and assumptions

- **Scope:** Only the HStack-used helpers `is_identity`, `unaffected`, `retain_margins`, and `retain_bounds`. General lazyframe dispatch is outside this property.
- **Invariants:** Preserve a certificate only when the HStack writes no potentially changed columns, or it has explicit known dependencies disjoint from all written columns. A multiple-output selector invalidates a certificate on any change. Recognize identity only for `Expr::Column` and aliases of the same output column.
- **Assumptions:** Polars reports grouping expression roots and multiple-output selectors accurately. Arbitrary user-defined expression semantics are not independently proven.
- **Source:** [Pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/mod.rs), [HStack caller](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/h_stack/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `is_identity` | correctness/column-lineage | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Expression identity analysis](../../../../../investigations/polars-hstack-lineage.md) |
| `unaffected` | privacy/grouping-certificate-lineage | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Dependency and selector analysis](../../../../../investigations/polars-hstack-lineage.md) |
| `retain_margins` | privacy/grouping-certificate-lineage | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Certificate-retention analysis](../../../../../investigations/polars-hstack-lineage.md) |
| `retain_bounds` | privacy/grouping-certificate-lineage | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Certificate-retention analysis](../../../../../investigations/polars-hstack-lineage.md) |

## Analysis

`is_identity` peels aliases and accepts a column only if its source name equals the output name. `unaffected` retains all certificates when no columns change, rejects any multiple-output selector when columns do change, and otherwise retains only explicit grouping expressions whose `root_names()` do not intersect changed columns. `retain_margins` and `retain_bounds` apply this same predicate to each certificate, so domain and stability-map pruning are aligned.

No counterexample was found within these declared set/lineage rules. The [source-model regression](../../../../../tools/tests/test_hstack_lineage_model.py) checked 1,280 exhaustive combinations and 20,000 deterministic randomized cases. The expression metamodel and actual optimizer output have **not** been executed; reliance on accurate Polars dependency metadata is the reason for partial privacy statuses. `is_identity` itself is fully examined for the declared `Expr::Column`/`Expr::Alias` forms only.

## Next checks

Exercise nested aliases and selectors through actual Polars optimizer plans, and verify retention against independently measured output groupings. No defect identified in the reviewed helper branches.
