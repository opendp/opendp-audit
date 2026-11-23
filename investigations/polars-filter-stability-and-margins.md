---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Partial
---

# Polars frame and aggregation filter stability

## Scope and invariant

Reviewed two **non-deprecated** filter paths on upstream OpenDP `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. [Frame filter](../source/rust/src/transformations/make_stable_lazyframe/filter/mod.rs.md) removes rows before grouping; [aggregation expression filter](../source/rust/src/transformations/make_stable_expr/expr_filter/mod.rs.md) removes values only within existing groups. They should be nonexpansive in record-multiset symmetric distance for the same deterministic, row-local predicate applied to each dataset. The invariant does **not** cover a predicate depending on aggregate statistics, runtime errors, or arbitrary expressions whose row-locality is unproved.

Pinned sources and tests:
- [Frame filter](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/filter/mod.rs) and [test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/filter/test.rs).
- [Aggregation expression filter](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_filter/mod.rs) and [test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_filter/test.rs).
- [Independent model test](../tools/tests/test_polars_filter_stability_model.py).

## Reasoning

For row value `r` and dataset multiset `X`, let `n_X(r)` be its count. For deterministic row-local predicate `p(r)`, filtered multiplicity is `n_F(X)(r) = n_X(r)·1[p(r)]`. Therefore

`|n_F(X)(r)-n_F(Y)(r)| ≤ |n_X(r)-n_Y(r)|`.

Summing over `r` yields identity-map nonexpansiveness for symmetric multiset distance; applying the inequality per public group key yields non-expansiveness in groupwise `L0`, `L1` and `L∞` summaries. This establishes the ideal mathematical mechanism conditional on row-locality. It does **not** prove every Polars predicate is total and row-local under all optimizer plans.

**Frame-level:** The source checks a boolean predicate, constructs it under `Context::RowByRow` (which excludes aggregation-only expressions such as `Expr::Len`), keeps the source metric and an identity stability map, and drops all `Margin.invariant` descriptors. This is conservative: filtering can delete the last row of a group and change all group lengths. Upper bounds for record and group counts remain valid.

**Aggregation expression:** The source requires `Context::Aggregation`, checks a boolean predicate and matching output metrics for the row-local input and predicate expressions, and maps an existing `Some(Invariant)` to `Some(Invariant::Keys)`. The enclosing aggregate still has the group key even if zero expression values pass its filter, but its length may change. Thus key invariants can remain when previously known, while length invariants cannot.

## Executed finite model

A standard-library [reference test](../tools/tests/test_polars_filter_stability_model.py) ran locally as `python -m unittest -v /mnt/data/test_polars_filter_stability_model.py`; **four tests passed**, not native Rust/Polars. Six predicates over four record values were checked:

- All ordered dataset pairs of size at most 4: `6×(1+4+16+64+256)^2=697,686` multiset-distance inequalities, no violations.
- All ordered dataset pairs of size at most 3: `6×(1+4+16+64)^2=43,350` groupwise comparisons, each checking per-key differences and `L0/L1/L∞` non-expansion, no violations.
- Frame filter witness: `[(0,a),(1,a),(2,b)]` filtered by `value==2` removes group `a` and decreases length.
- Aggregation filter witness: filtering the same input by `value>1` retains both group keys but leaves group `a` with no expression values.

Total: **741,036 ordered-pair comparisons**, plus two invariant witnesses. The model uses Python `Counter` and a simple group-key map, not the actual Polars execution engine.

## Findings and limitations

No counterexample under the specified model or source contracts. The source handles key and length margin invariants differently for the two APIs in a way consistent with their semantics. No unreported bug confirmed, so no candidate-defect issue warranted; [task #43](https://github.com/opendp/opendp-audit/issues/43) tracks this review.

Privacy coverage is **Partial** pending native Rust/Polars execution, validation that all accepted predicate expressions satisfy row-by-row semantics, nullable-predicate execution, optimizer behavior, and data-dependent exception analysis. Upstream [issue #3082](https://github.com/opendp/opendp/issues/3082) concerns expression-based truncation keys, a distinct path, and is not evidence of a filter regression.

## Next checks

Native integration tests for both operators including all-filtered groups, nullable boolean predicates, errors and optimizer rewrites; review `StableExpr` row-locality dependencies.
