---
schema_version: 1
source: rust/src/transformations/make_stable_lazyframe/truncate/matching/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_lazyframe/truncate/matching/mod.rs`

## Scope and assumptions

Review the **non-deprecated** Polars identifier-truncation parser at pinned upstream SHA `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. Focus on `match_truncations`, `match_truncation_predicate`, `match_num_groups_predicate`, and `match_per_group_predicate`, including threshold comparator normalization, recognized `int_range`/dense-rank predicates, and the need for permutation invariance under `SymmetricIdDistance`.

**Invariant:** Neighboring tables with zero unordered identifier distance must produce equivalent deterministic truncation outputs. A contribution bound must describe the grouping and ordering expressions that actually influence which records survive. Actual Polars window/rank runtime and native Rust construction are not executed; source and idealized deterministic models are evaluated.

- [Upstream matcher](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/truncate/matching/mod.rs), [native matcher tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/truncate/matching/test.rs), [identifier metric](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/polars/mod.rs).
- [Cross-file investigation](../../../../../../../investigations/polars-identifier-truncation-permutation.md) and [independent Python reference tests](../../../../../../../tools/tests/test_polars_truncation_permutation_model.py).
- Known upstream [issue #3157](https://github.com/opendp/opendp/issues/3157), open corrective [PR #3158](https://github.com/opendp/opendp/pull/3158) and [PR #3270](https://github.com/opendp/opendp/pull/3270).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `match_truncations` | correctness/recognized-filter-chain | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Filter chaining and certificates](#filter-chaining-and-certificates) |
| `match_truncation_predicate` | correctness/comparison-bound-normalization | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Threshold normalization](#threshold-normalization) |
| `match_num_groups_predicate` | privacy/rank-key-permutation-invariance | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Rank provenance](#rank-provenance); existing upstream fix PR #3270 |
| `match_per_group_predicate` | privacy/positional-truncation-permutation-invariance | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Positional truncation](#positional-truncation); existing upstream issue #3157 |

## Analysis

### Filter chaining and certificates

`match_truncations` first recognizes an optional terminal group-by containing the identifier key, then descends through a contiguous sequence of recognizable filter truncations. A boolean `And` or `AllHorizontal` yields *all* child bounds only if every child is recognized; any non-truncation child causes the entire conjunction not to match. A terminal group-by also imposes a subset check that filter-bound grouping keys are included among its non-identifier keys. The function reverses the traversed truncation order and certificate list. The [consumer](../mod.rs.md) iterates all certificate bounds independently, so the two lists need not have equal lengths (one conjunctive filter can provide two bounds). No issue was established in this list-length difference.

### Threshold normalization

For recognized comparisons, `Lt` and its reversed form `Gt` certify threshold `k`; `LtEq` and its reversed form `GtEq` certify `k+1`, computed with checked `InfAdd`. A threshold outside `u32`, or inclusive `u32::MAX` that would overflow, is rejected rather than silently producing a smaller bound. A zero-based `int_range(0,len())` keeps `k` items under `<k` and `k+1` under `<=k`. A dense rank starts at one, so `<k` retains at most `k-1` groups and the source's `k` certificate is conservative but non-tight. The [reference tests](../../../../../../../tools/tests/test_polars_truncation_permutation_model.py) checked **9,792** finite cases for both rank origins and all four comparison orientations. Open PR #3270 adjusts the one-based dense-rank bound.

### Positional truncation

`match_per_group_predicate` accepts `int_range(lit(0),len(),1,Int64)` over a window partitioned by the identifier and optionally other grouping keys. It also recognizes reversed, shuffled and sorted variants. An ordering-dependent choice of which input rows have index below `k` need not be a function of the *unordered* input multiset. For identical rows under permutation, this can change which private values survive and their downstream aggregates, despite a zero identifier distance. The independent model gives an explicit witness: one identifier and one group with values `[10,20,30]`; `int_range<1` yields 10, while reversing the same multiset yields 30. Both satisfy the numerical per-group bound of one. The example models source-accepted positional semantics but does not execute native Polars.

The failure class is **already reported** upstream in [issue #3157](https://github.com/opendp/opendp/issues/3157) and addressed by open [PR #3158](https://github.com/opendp/opendp/pull/3158). This is a permutation-invariance obligation, **not** a numerical bound-underflow finding. No duplicate audit defect issue was created.

### Rank provenance

`match_num_groups_predicate` accepts a dense rank over grouping keys. In a special hashed-struct case, it recognizes a first field hashing the second key struct and returns a bound describing only the inner key fields. At the pinned revision it does **not** check that the rank struct has exactly two fields or that the hash has exactly one input before discarding outer fields. Consequently an additional row-position field may influence the dense ranks without appearing in the returned key set. The independent model demonstrates that rank over `(hash(key),key,position)` can select different values for two input permutations with the same key, even while the bound names only `key`. The structural check and categorical-key safeguards are added by open [PR #3270](https://github.com/opendp/opendp/pull/3270). This is a source-supported risk with an independent model, not a native reproduction or an additional unreported issue.

## Findings and next checks

The reference model passed **four** tests: two explicit permutation counterexamples, 9,792 conservative threshold comparisons, and conjunction recognition checks. The source currently accepts order-sensitive truncation shapes; an accepted positional expression is incompatible with zero-distance permutation invariance unless further constraints prevent execution. Existing upstream issue #3157 and PRs #3158/#3270 are the appropriate tracked remedies. See [audit task #67](https://github.com/opendp/opendp-audit/issues/67).

Run native OpenDP/Polars integration tests for both orderings, verify constructed measurements do not release zero-distance distinguishing events, and test the branch heads of PRs #3158 and #3270 before claiming a complete fix. Overall privacy verification **Partial**.
