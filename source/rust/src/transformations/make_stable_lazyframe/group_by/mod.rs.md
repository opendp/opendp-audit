---
schema_version: 1
source: rust/src/transformations/make_stable_lazyframe/group_by/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_lazyframe/group_by/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated `make_stable_group_by` on unbounded row-contribution metrics, including its group-by option checks, contribution stability map, and grouping-certificate preservation; plus the narrowly scoped `materialize_grouping_keys` helper. The large `check_infallible` whitelist is not independently audited **except** for `ArrayFunction::Get(bool)` and its direct error-propagation contract. The downstream private aggregation mechanism is not independently audited here.
- **Invariant:** Output symmetric-distance row bounds must conservatively account for affected aggregate groups. Grouping certificates retained after aggregation must refer to materialized output columns with key/length invariants dropped. Identifier-bearing metrics must not silently enter this sample-and-aggregate path.
- **Assumptions:** Input metric `Bounds` are valid; `Bounds::get_bound` infers conservative limits; aggregation expressions are total on the declared domain **except the identified `ArrayFunction::Get(false)` path, which violates that assumption**; Polars grouping-output-name metadata is accurate; and each key expression's stability constructor fulfills its contract. A changed grouped output row contributes at most one deletion and one insertion to symmetric distance.
- **Pinned source:** [group-by implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/group_by/mod.rs), [native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/group_by/test.rs), [input `Bounds::get_bound`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/polars/mod.rs), [investigation](../../../../../../investigations/polars-groupby-influence-bound.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_stable_group_by` | privacy/group-by-partition-stability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Bound derivation and finite model](../../../../../../investigations/polars-groupby-influence-bound.md) |
| `make_stable_group_by` | correctness/grouping-invariant-erasure | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Key certificates](../../../../../../investigations/polars-groupby-influence-bound.md) |
| `make_stable_group_by` | correctness/identifier-rejection | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Source control-flow trace](../../../../../../investigations/polars-groupby-influence-bound.md) |
| `materialize_grouping_keys` | correctness/output-group-key-lineage | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Materialized keys](../../../../../../investigations/polars-groupby-influence-bound.md) |
| `check_infallible_function` | correctness/array-get-oob-validation | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Pinned Polars Get(false) mismatch](../../../../../../investigations/polars-array-get-oob-whitelist.md); [issue #71](https://github.com/opendp/opendp-audit/issues/71) |
| `check_infallible` | privacy/data-dependent-aggregation-error | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Error-channel analysis and integration limitations](../../../../../../investigations/polars-array-get-oob-whitelist.md) |

## Analysis

### `make_stable_group_by` — `privacy/group-by-partition-stability`

**No defect identified within the source-level property.** The map computes `contributed_rows = d_in.get_bound(empty).per_group` and `contributed_groups = d_in.get_bound(original_keys).num_groups`. It fails if both are unknown; otherwise it emits `Bounds([Bound::by(empty).with_per_group(2 * min(known bounds))])`, with fallible upward-checked multiplication. A changed group may replace one output aggregate row, contributing at most two to symmetric distance. An affected group must contain a changed row, and input group contribution bounds independently cap how many groups are affected.

**Executed model:** A [Python standard-library regression](../../../../../../tools/tests/test_polars_groupby_stability_model.py) checks **67,081 exhaustive ordered pairs** of datasets of 0–3 rows (two keys, three values), plus **10,000 randomized pairs** with additional keys/values. The model computes multiset symmetric distance of the grouped `(key,sum)` rows. All cases satisfied `d_out <= 2 * min(changed_rows, distinct_changed_keys)`; 26,949 exhaustive pairs attained equality. Tests also check absent bounds and min-of-bounds behavior. This is not compiled OpenDP or Polars.

**Why Partial:** The model does not validate arbitrary aggregation expressions, all optimizer paths, `Bounds::get_bound`'s finite covering inference, or the full data-dependent-error gate `check_infallible`. Correctness of those prerequisites was assumed, not established.

### `make_stable_group_by` — `correctness/grouping-invariant-erasure`

Only prior margin key sets that are subsets of the original group keys are retained. Their source expressions become materialized output column expressions using `materialize_grouping_keys` and **`invariant = None`** is set unconditionally. The output schema is simulated from the actual group-by plan. Existing Rust tests cover computed, aliased, and ordinary keys; they were inspected but not executed natively.

### `make_stable_group_by` — `correctness/identifier-rejection`

The constructor rejects unsupported `apply`/options/`maintain_order`, and feature-gated HAVING predicates. It checks group keys' row-wise stability and uses `check_infallible` for aggregations. After predecessor stabilization, it rejects `middle_metric.0.identifier().is_some()` before constructing a grouped stability map. Unbounded contributions from a protected identifier require the separate truncation path.

### `materialize_grouping_keys` — `correctness/output-group-key-lineage`

Each validated key is rewritten as `col(key.meta().output_name()?)`; output-name lookup errors propagate. Thus a source key `A+B` is represented by its materialized output column `A`, not by evaluating `A+B` again on the grouped result; aliased keys become columns of the alias name. Native Rust tests illustrate these cases, but none was run here.

### `check_infallible_function` — `correctness/array-get-oob-validation`

**Finding:** The `ArrayFunction::Get(_)` arm accepts `Get(false)` and recurses into its inputs without considering the Boolean `null_on_oob` flag, even though the immediately neighboring `ListFunction::Get(null_on_oob)` rejects `false`. The exact pinned Polars 0.52.0 / `py-1.36.1` backend marks `IRArrayFunction::Get(false)` fallible and its native tests require `ComputeError` for out-of-bounds index series. A private index column can therefore trigger a data-dependent evaluation error in an aggregate expression admitted by this whitelist.

**Verification:** OpenDP and pinned Polars source trace, same-version checked-in Polars regression tests, and a local Python [source model](../../../../../../tools/tests/test_array_get_oob_whitelist_model.py) with 20,672 boundary/random checks; OpenDP Rust/Polars were **not executed**. [Investigation](../../../../../../investigations/polars-array-get-oob-whitelist.md), [candidate privacy-impacting issue #71](https://github.com/opendp/opendp-audit/issues/71). `Audited` is limited to the `Get(bool)` branch's admission contract, not the whole whitelist.

### `check_infallible` — `privacy/data-dependent-aggregation-error`

**Assessment: Partial, with a candidate side channel.** `make_stable_group_by` and `truncate_domain` call `check_infallible` on aggregate expressions, making this branch reachable; a failure dependent on a protected index may expose success/error status. We have not compiled and evaluated an end-to-end private LazyFrame, so privacy impact cannot be promoted to `Reproduced`. This finding challenges the aggregation-totality assumption of the earlier influence-bound review; the bound calculation itself remains unchanged.

## Next checks

Test native Rust/Polars grouped aggregation with multi-partition bound inference, computed key expressions, optimizer rewrites, and remaining `check_infallible` whitelist cases. The `ArrayFunction::Get(false)` case has a specific [candidate issue #71](https://github.com/opendp/opendp-audit/issues/71) and requires native end-to-end regression. No candidate defect was found within this scope; [audit task #59](https://github.com/opendp/opendp-audit/issues/59) tracks the review.
