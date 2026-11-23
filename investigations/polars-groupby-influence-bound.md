---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Polars group-by: affected groups and key materialization

## Property and reachability

The non-deprecated `make_stable_group_by` must conservatively map an input contribution certificate into a symmetric-distance bound on the **grouped output**. For a grouped aggregate, changing a keyed group can delete one old aggregate row and insert one new aggregate row; thus `g` affected groups imply output symmetric distance no greater than `2g`. Retained grouping certificates must refer to the materialized output columns, not expressions to be re-evaluated after aggregation.

Sources: [source audit](../source/rust/src/transformations/make_stable_lazyframe/group_by/mod.rs.md), [group-by implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/group_by/mod.rs), [existing native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/group_by/test.rs), and [`Bounds::get_bound`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/polars/mod.rs).

## Cross-file bound argument

Given a valid input `Bounds`, `d_in.get_bound(empty).per_group` bounds the number `r` of changed rows a privacy unit contributes (when known). `d_in.get_bound(keys).num_groups` bounds the number `g` of keyed groups influenced by a unit (when known). Each changed row affects at most one grouped key, so affected groups are at most `min(r,g)` if both are known, or at most the one remaining bound. An aggregate group's output may change from `(key,old_aggregate)` to `(key,new_aggregate)`; under row symmetric distance this contributes up to two. Therefore the implemented output bound `2 * option_min(r,g)` is conservative given the certificate premises. If both candidates are unavailable, the implementation returns `FailedMap`; it does not invent finite privacy stability.

The `Bounds::get_bound` call infers `per_group` using coarser grouping certificates and `num_groups` from covers, using fallible multiplication. We traced this dependency, but did not establish every covering inference proof. The group-by map uses `InfMul` for the final factor of two rather than an unchecked wrapping multiply.

## Domain, schema and constructor checks

The constructor rejects `apply`, nonordinary group-by options, `maintain_order`, and feature-gated HAVING predicates. It validates row-wise grouping keys and calls the shared `check_infallible` gate for aggregation expressions. After predecessor stabilization, it rejects identifier-bearing metrics before creating a group-by bound. Identifier-based contribution truncation is a different path not audited here.

The grouped output schema is inferred by Polars. Retained margins must be subsets of the original selected group keys; their `by` expressions are converted into `col(key.meta().output_name()?)` and any `invariant` is set to `None`. For example, an original key `col("A") + col("B")` materializes as grouped output column `A`, while `col("A").alias("key")` materializes as `col("key")`. Retaining the source expressions instead would re-evaluate different values on the aggregated schema. The existing upstream tests assert ordinary, computed, and aliased cases; these tests were read, not executed.

## Executed checks

The committed [standard-library reference tests](../tools/tests/test_polars_groupby_stability_model.py) calculate group-wise sums and use multiset symmetric distance for input and output rows. The finite alphabet has six possible input rows, yielding 259 ordered datasets of 0–3 rows; all **67,081** ordered dataset pairs were checked against the group-bound inequality. Every pair passed and **26,949** pairs attained the bound. A deterministic additional **10,000** randomized dataset pairs over five keys and six values also passed. Missing/one-sided/two-sided certificate values and illustrative output-key name rewriting were included. The audit repository validator and all 22 local Python tests passed.

**Execution limitation:** These are finite mathematical models of the source calculation, **not compiled OpenDP/Polars tests**. They use bounds constructed from actual differing rows; they do not verify the full `Bounds::get_bound` inference, all aggregate error semantics, or every optimization path.

## Disposition

No defect was identified in the bounded properties `privacy/group-by-partition-stability`, `correctness/grouping-invariant-erasure`, `correctness/identifier-rejection` and `correctness/output-group-key-lineage`. Privacy-relevant coverage remains **Partial** because conservative input certificate inference and supported aggregation semantics are prerequisites. Searches of audit/upstream issues and upstream PRs found no same-scope defect or fix. [Audit task #59](https://github.com/opendp/opendp-audit/issues/59) coordinates this review; no candidate-defect issue is warranted.

Next checks: native grouped aggregation with multi-partition certificate inference; computed nested keys after optimizer rewrites; independent audit of `check_infallible` and aggregation error paths.
