---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Identifier truncation: finite numerical contribution bounds

## Invariant and threat model

When one identifier is added to or removed from an input dataframe, a valid contribution-bound certificate must not underestimate the number of changed rows in any output group or the number of impacted groups. The current non-deprecated Polars matcher recognizes dense-rank group truncation, per-ID/group enumeration truncation, and an optional identifier-preserving group-by. This report tests **the numerical certificate arithmetic**, not the stronger invariance required by `FrameDistance<SymmetricIdDistance>`.

**Important separate privacy concern:** The matched positional row truncation can choose different records when rows within the same identifier are permuted, even at identifier distance zero. That unresolved **source-supported privacy failure class** is detailed in the [permutation investigation](polars-identifier-truncation-permutation.md), already reported upstream as [#3157](https://github.com/opendp/opendp/issues/3157) and addressed by open [PR #3158](https://github.com/opendp/opendp/pull/3158). Open [PR #3270](https://github.com/opendp/opendp/pull/3270) separately hardens the matcher. Passing cardinality checks **does not remedy** these issues.

## Affected symbols and source audits

- [Stable truncation constructor and bound converter](../source/rust/src/transformations/make_stable_lazyframe/truncate/mod.rs.md): `make_stable_truncate` and `truncate_id_bound`, with [pinned Rust](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/truncate/mod.rs).
- [Pattern matcher](../source/rust/src/transformations/make_stable_lazyframe/truncate/matching/mod.rs.md): `match_truncations`, `match_truncation_predicate`, `match_num_groups_predicate`, and `match_per_group_predicate`, with [pinned Rust](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/truncate/matching/mod.rs).
- [Grouping-certificate inference](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/polars/mod.rs): `Bounds::get_bound` derives bounds from known coarser groupings and min-cover products.
- [Native matcher tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/truncate/matching/test.rs) and [truncation tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/truncate/test.rs).

## Reasoning and evidence

### Filter recognition and certificates

The matcher accepts an optional final ordinary group-by containing the protected identifier, preceded by an uninterrupted sequence of recognized truncation filters. It creates a `num_groups=K` certificate over the ranked grouping key for a supported dense-rank condition within the identifier window; or `per_group=L` over non-identifier window keys for a supported zero-based row enumeration. A conjunction can yield multiple certificates from a single filter. Ordinary `GroupBy(ID,group)` emits at most one row per identifier/group but no independent number-of-groups limit.

For nonnegative public comparison threshold `t`, the source maps `<t` to upper certificate `t` and `<=t` to `t+1`. This is conservative for both zero-based enumeration and one-based dense rank (although the latter can be looser by one). Inclusive `u32::MAX` overflows with a fallible arithmetic error, not a wrapped zero. The [model test](../tools/tests/test_identifier_truncation_model.py) checks each comparator on thresholds 0 through 5.

### One-identifier finite reference model

Let the changed-ID count be one, the upper bound on changed IDs in each output group be one, and the original set of possible grouping values have size three. A row truncation cap `L` leads to a per-group row certificate `1*L=L`. If a final group-by emits at most one row for each `(ID,group)` pair, the combined certificate is `min(L,1)`. A dense-rank cap `K` limits the number of output groups to at most `min(1*K,3)`. These represent the relevant `truncate_id_bound` products and independently valid minimums, under this narrow setup.

The independent [Python unittest](../tools/tests/test_identifier_truncation_model.py) enumerates all 210 multisets of up to four rows for one identifier from a six-value alphabet (three groups and two payloads), mixes each with three unchanged-ID baselines, and checks five distinct-group caps `K=0..4`, four per-group row caps `L=0..3`, and both raw-row and final group-by outputs.

**25,200 paired checks passed locally.** Every check verifies:
- The output contribution of the unchanged ID is identical in both datasets.
- The number of retained rows from the changed ID in any group does not exceed the computed per-group certificate.
- The number of impacted groups does not exceed the computed group-count certificate.

The model deterministically selects the lowest ranked keys and the earliest rows in each group; it does **not** model random shuffling, hash grouping, or runtime Polars execution. Its passing result applies to cardinality for one changed identifier only. It cannot certify all arbitrary `Bounds` graphs or permutation invariance.

### Historical key-materialization privacy regression

Computed grouping keys must be referenced in the output schema by their **materialized output name**, not reevaluated against post-aggregation columns. The current source does this after a final group-by. Historical upstream [issue #3082](https://github.com/opendp/opendp/issues/3082) was fixed by merged [PR #3087](https://github.com/opendp/opendp/pull/3087); the earlier column-rewrite invalidation error [#2949](https://github.com/opendp/opendp/issues/2949) was fixed by merged [PR #3056](https://github.com/opendp/opendp/pull/3056).

The model's third test uses 20 rows from one ID with original key `A+B` all distinct. It simulates grouping by that key, which writes the value into output column `A` while preserving a `B` aggregate. Regrouping output by **materialized `A`** gives at most one contribution per group; stale reevaluation of `A+B` merges all 20 into one group. This demonstrates why the already-merged relabeling fix is needed and is **not a new defect**.

### Evidence and limitations

**Executed:** Three independent standard-library Python tests passed locally, including the 25,200 neighboring-ID checks, comparator checks, and computed-key regression. Inspected source-pinned implementations and Rust tests.

**Not executed:** Compiled OpenDP, Polars query planner, null/hash-specific grouping, multiple changed IDs, arbitrary key expressions, random permutations, arbitrary input bounds, or any DP mechanism. **These finite numerical checks are strictly weaker than full metric stability:** the previously documented order-dependence risk remains present at the pinned upstream revision.

## Findings

No new unreported bug was found within the numerical bound model. Source-level privacy risks from order-sensitive truncation are already tracked by upstream [#3157](https://github.com/opendp/opendp/issues/3157), [PR #3158](https://github.com/opendp/opendp/pull/3158) and [PR #3270](https://github.com/opendp/opendp/pull/3270); the historical computed-key undercount is fixed by [#3087](https://github.com/opendp/opendp/pull/3087). No duplicate bug issue was created.

## Unresolved questions

Execute native Rust/Polars on the exact pin, verify corrected permutation-invariant truncation on the PR branches, and extend model coverage to multiple changed IDs and inferred mixed-key certificate graphs. Current privacy result remains **Partial**.
