---
schema_version: 1
source: python/src/opendp/extras/mbi/_table/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/mbi/_table/__init__.py`

## Scope and assumptions

- **Scope:** `_make_oneway_marginals` for publicly enumerated categorical keys, specifically the `group_by_agg` left join, the Rust private group-by/public-key sanitizer, and the `postprocess` conversion to integer marginals. Reviewed [upstream `main` at 7acfb2cdcee7d39fc26a6ade7edac15249c52f4b](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_table/__init__.py).
- **Invariant:** For a public category missing from private data, the released key remains present and receives DP-noised count output rather than a data-dependent null, missing row, or exception. In particular, `np.fromiter` must consume a privatized integer even if the original group is absent.
- **Assumptions:** Keysets are genuinely public; Polars compiles the supported `JoinType::Left` plan as matched; the Rust noise plugin and `OnceFrame` implement their claimed randomized semantics. This is a source-level review, not an executed native integration test.
- **Related:** [Cross-file investigation](../../../../../../../investigations/mbi-oneway-public-key-imputation.md), [prior Rust group-by audit](../../../../../../../source/rust/src/measurements/make_private_lazyframe/group_by/mod.rs.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `_make_oneway_marginals` | privacy/absent-public-groups | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Analysis](#analysis), [cross-file trace](../../../../../../../investigations/mbi-oneway-public-key-imputation.md) |
| `_make_oneway_marginals.group_by_agg` | privacy/public-key-join-routing | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Analysis](#analysis) |
| `_make_oneway_marginals._make.postprocess` | correctness/noisy-marginal-materialization | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Analysis](#analysis) |

## Analysis

With `name in keys`, `group_by_agg` constructs a public `LazyFrame([keyset])` and left-joins the private grouped `dp_len(signed=True)` output, using coalesced public key columns and `nulls_equal=True`. In unrewritten Polars, an absent private group would produce a null count, and `postprocess`'s `np.fromiter((lookup[k] for k in keys[name]), dtype=np.int64)` could fail. That failure **does not establish a current OpenDP bug**: the DP constructor rewrites this plan.

The Rust [`match_group_by` matcher](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/measurements/make_private_lazyframe/group_by/matching.rs#L43-L172) specifically recognizes public-key Left/Right joins, requires column-only coalesced equality keys and validates the join. In [`make_private_group_by`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/measurements/make_private_lazyframe/group_by/mod.rs#L133-L249), this path sets `is_join`, creates `fill_null` expressions for each private noisy aggregate, deduplicates the public keys, performs the join and appends a post-join `HStack` evaluating those fillers. A missing category consequently receives the aggregate's randomized fill expression instead of a null; the public key set is released without charging unknown-key delta, consistently with the public-key assumption.

The [upstream Rust `test_explicit_keys`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/measurements/make_private_lazyframe/group_by/test.rs) builds 5,000 public candidates with one private key, checks deduplication, and statistically assesses imputed aggregate draws. **The test source was inspected but not run in this audit.** No local Polars, OpenDP, or MBI installation was available, and no compiled native test was executed.

## Findings and next checks

No additional defect identified in the scoped missing-public-category path. This is an independently documented Python-to-Rust boundary, not a claim that all MBI mechanisms or all group-by operators are safe. Status remains **Partial** pending a native regression over two neighboring tables (missing/present public categories), including `np.fromiter` materialization, and an end-to-end check under both supported privacy measures. The separate [upstream issue #3285](https://github.com/opendp/opendp/issues/3285) concerns **nullable ordinal marginal inputs**, not this public-key imputation invariant.
