---
schema_version: 1
upstream_commit: 7acfb2cdcee7d39fc26a6ade7edac15249c52f4b
updated: 2026-11-23
status: Partial
---

# MBI one-way marginals: public keyset imputation across Python and Rust

## Invariant and threat model

For public categories `K` and private data `D`, a keyed one-way marginal must release counts over all `K` without disclosing which keys were absent from `D` through missing rows, null counts, or a data-dependent exception. Adjacent private datasets may differ by one occurrence of a public key. The joined values must be privatized before Python postprocessing treats them as integers. Keysets are public and fixed, and the data and distance certificates satisfy the input domain.

## Affected symbols and source audits

- [Python `_make_oneway_marginals` source report](../source/python/src/opendp/extras/mbi/_table/__init__.py.md) and [upstream code](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_table/__init__.py#L523-L677).
- [Rust `match_group_by`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/measurements/make_private_lazyframe/group_by/matching.rs#L43-L172), [Rust `make_private_group_by`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/measurements/make_private_lazyframe/group_by/mod.rs#L133-L249), and the [existing Rust audit report](../source/rust/src/measurements/make_private_lazyframe/group_by/mod.rs.md).

## Reasoning and evidence

1. Python's `group_by_agg` constructs an explicit left join from public categories to private `group_by(name).agg(dp_len(signed=True))`. Without DP-aware rewriting, absent groups would have a null count and subsequent `np.fromiter(..., dtype=np.int64)` would fail in a data-dependent way.
2. This query does **not** reach Python unchanged. `make_private_lazyframe` invokes `match_group_by`, which recognizes an authorized public-key join and stores a `KeySanitizer::Join`.
3. `make_private_group_by` obtains a `fill` expression from each private aggregate, requires it to exist for every aggregate, and rewrites the joined plan to apply `col(name).fill_null(fill_expression)` after deduplicating the public keys. A missing category therefore gets a randomized imputed aggregate rather than a null.
4. The Rust [`test_explicit_keys`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/measurements/make_private_lazyframe/group_by/test.rs) covers the exact public-key imputation route, including many absent groups and duplicate public keys. This audit **inspected** that test but did **not** run it. The local environment lacks Polars, OpenDP and MBI, so there is no new execution-level counterexample or empirical confirmation.

The source-visible rewrite invalidates the initial exception-leak hypothesis. The correct conclusion is a negative finding in this bounded property, conditional on actual Polars execution respecting the rewritten plan.

## Findings

No new defect established in public-key absent-category imputation. Do not confuse this with [upstream issue #3285](https://github.com/opendp/opendp/issues/3285) (nullable ordinal array indexing), which is a different issue and has a pending [PR #3288](https://github.com/opendp/opendp/pull/3288).

## Unresolved questions

Run native Rust explicit-key tests on the pinned revision and a Python/MBI end-to-end pair of neighboring datasets, and confirm no `None` enters the keyed `np.fromiter` path. This audit did not establish an independent proof of the noise fill distribution or its privacy accounting.
