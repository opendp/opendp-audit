---
schema_version: 1
source: rust/src/measurements/make_private_lazyframe/group_by/matching.rs
updated: 2026-11-23
---

# `rust/src/measurements/make_private_lazyframe/group_by/matching.rs`

## Scope and assumptions

- **Scope:** The non-deprecated `match_group_by` public-key `Join` admission branch, including `match_grouping_columns` and its dependency on `valid_public_key_join_options`. Trace both left and right orientations, complete materialized grouping-key coverage, public frame schema collisions, and join options. This is **not** a review of threshold filtering, `find_len_expr`, or private aggregation/noise maps.
- **Invariant:** An explicit public key set must enumerate all materialized private group keys, must not expose private-side uncoalesced keys or shadow private aggregate output names, and must not permit order/slice or predicate behaviors that defeat the public-key sanitizer. Duplicate public key tuples must not multiply private noisy results.
- **Assumptions:** Input `DslPlan::GroupBy` and public-key `Join` are genuine Polars expressions with consistent `compute_schema()` and `expr_output_name()` metadata; `valid_public_key_join_options` is authoritative for pinned Polars `JoinOptions`; the later constructed `Distinct` deduplicates public key tuples; the underlying measurements charge all released aggregate expressions.
- **Pinned source:** [`matching.rs`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/group_by/matching.rs), [private group-by output rewrite](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/group_by/mod.rs), [`valid_public_key_join_options`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/options.rs), [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/group_by/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `match_group_by` | privacy/public-key-join-sanitization | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Source-level join safeguards](#source-level-join-safeguards); [reference model](../../../../../../tools/tests/test_public_key_join_sanitization_model.py) |
| `match_group_by` | correctness/group-key-coverage | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Complete materialized group key comparison](#materialized-group-key-coverage) |
| `match_grouping_columns` | correctness/column-only-key-normalization | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Name normalization](#materialized-group-key-coverage) |

## Analysis

### Source-level join safeguards

For public-key joins, `match_group_by` accepts only a `DslPlan::Join` with no extra predicates, required key coalescing, no slice, and `valid_public_key_join_options`. The latter explicitly admits only left/right, `ManyToMany`, disabled maintain-order, approved coalescing and suffix semantics; parallel settings are unconstrained. The matcher orients the public key plan to the **left** for `JoinType::Left` and **right** for `JoinType::Right`, with complementary `input_on` and `keys_on`.

Both sides of every join-key pair must be direct `Expr::Column` expressions. This prevents Polars from disabling coalescence when a key uses a computed expression. The public schema must contain the public join names, and its entire set of columns must be disjoint from the **private aggregate output names**, blocking both ordinary and join-key collisions. The later measurement constructor wraps the public key relation in `DslPlan::Distinct` using `subset = Some(join keys)`, `keep_strategy = Any`, before joining, so repeated public keys cannot multiply a noisy aggregate's output rows. The original private-key sanitizer's join orientation and null-imputation rules are independent of these checks and were not audited here.

### Materialized group key coverage

For a matched `GroupBy`, `match_group_by` computes the set of *materialized output* grouping key names using `expr_output_name`, expanding `Selector::ByName` and rejecting unsupported selectors; it requires this set to **equal** the set of private-side join key columns. Thus omitting any private grouping key is rejected even if the remaining public keys happen to match private data. It permits public-side column names that differ from private group key names (the column pair mappings still coalesce), and permits extra nonconflicting public metadata columns.

`match_grouping_columns` maps direct columns (and named selector expressions when called separately) to a `BTreeSet<PlSmallStr>`. At this call site, the explicit preliminary `Expr::Column` guard rejects selectors in the join `on` expressions, so selectors are only relevant to the materialized group-by key comparison. Set equality intentionally ignores ordering. The matcher does **not** independently require a bijection of join key pairs: for example, repeated join columns can collapse under set conversion. Whether such unconventional duplicate join-pair plans lead to invalid coalescing or are normalized/rejected by Polars was not exercised; no privacy claim is made for those cases.

### Executed evidence and limitations

**Source model:** [`test_public_key_join_sanitization_model.py`](../../../../../../tools/tests/test_public_key_join_sanitization_model.py) exhaustively compares group-key sets, joined-key sets, public schema and aggregate name masks over three names (**4,096** combinations), checks the strict option/column guards, and runs **20,000** seeded random key/schema/collision cases. It models only the set equality, length equality and disjointness checks; it does not execute native OpenDP or Polars joins. The native upstream tests were inspected, not executed: `test_explicit_key_join_rejects_partial_keys`, `test_explicit_key_join_deduplicates_public_keys`, `test_explicit_key_join_rejects_collisions`, and `test_explicit_key_join_rejects_unsafe_options` cover both join orientations and representative rejection conditions.

The guards are consistent with earlier upstream [merged PR #3097](https://github.com/opendp/opendp/pull/3097) (**merged 2026-11-04**). No duplicate bug report was created. The property remains **Partial** for end-to-end privacy because the checker depends on Polars name and schema metadata, actual join behavior and key deduplication, none of which were independently verified in this bounded pass. The key-set matching and column-only source-control-flow properties are `Audited` narrowly.

**Conclusion:** No new confirmed defect found in the declared source-level properties. The published source review does not prove arbitrary Polars public-key joins safe.

## Next checks

Native tests of computed materialized grouping keys, duplicate `on` pairings, public key columns with different names, null join-key behavior, and actual `Distinct`/imputation behavior on private empty/nonempty groups. Review the key-sanitizer postprocessing separately from this admission audit.
