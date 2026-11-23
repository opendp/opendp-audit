---
schema_version: 1
source: python/src/opendp/extras/mbi/_utilities/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/mbi/_utilities/__init__.py`

## Scope and assumptions

- **Audit scope:** `Count.__post_init__` validation, `make_stable_marginals` handling of the zero-dimensional clique `()`, and its `pivot` conversion from grouped Polars counts to `np.ndarray`. The general L0/L1/L2 sensitivity proof, typed-dictionary metric, full noise samplers and mirror-descent optimizer remain outside the scope.
- **Invariant:** Every accepted clique is either rejected before private-data access or can be materialized as a correctly shaped, in-domain count array for an arbitrary valid input dataset; `()` denotes one cell holding the total count.
- **Assumptions:** The clique columns are already encoded as bounded integer indices, the input frame carries at least one column, and Polars' documented 1.36.1 group-by and DataFrame getitem semantics match its pinned source. No installed Polars/OpenDP execution was available.
- **Pinned source:** [`_utilities`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/mbi/_utilities/__init__.py), [`arrayd_domain`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/__init__.py), [Polars pinned 1.36.1 group-by guard](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-core/src/frame/group_by/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `Count.__post_init__` | correctness/empty-clique-validation | Audited | `a010591f55b1713c926f8e355091471634480307` | [Zero-clique acceptance](#zero-clique-acceptance), [cross-file investigation](../../../../../../../investigations/mbi-fixed-zero-clique-total-count.md). |
| `make_stable_marginals` | correctness/zero-dimensional-pivot | Audited | `a010591f55b1713c926f8e355091471634480307` | [Empty-key source path](#empty-key-source-path), [issue #148](https://github.com/opendp/opendp-audit/issues/148). |
| `make_stable_marginals` | privacy/total-count-sensitivity | Partial | `a010591f55b1713c926f8e355091471634480307` | [Stability-map construction](#stability-map-construction); full native and numeric coverage outstanding. |
| `make_noise_marginals` | correctness/fixed-workload-arity | Partial | `a010591f55b1713c926f8e355091471634480307` | [Delegation](#delegation); nonempty fixed workload is not reduced by zip when internally generated weights align. |

## Analysis

### Zero-clique acceptance

`Count.__post_init__` accepts `by=()` because the all-string predicate is vacuously true and normalizes it to `tuple()`; the default query weight is valid. The `Fixed` algorithm's publicly accepted workload can therefore contain a total-count query. `make_stable_marginals` itself also snapshots any sequence of zero-dimensional cliques without rejecting it.

### Empty-key source path

`shape(())=()`, so `arrayd_domain(shape=(),T='i32')` is accepted. On invocation, the stable marginal constructs `data.group_by(()).agg(pl.len())`; Polars 1.36.1 rejects group-by with zero grouping keys in its compiled execution path. [Polars PR #27141](https://github.com/pola-rs/polars/pull/27141) added the missing rewrite in April 2026, after the pinned 1.36.1 tag dated December 2025.

The `pivot` implementation also does `y[tuple(x[clique].to_numpy().T)]`. In Polars' pinned getitem semantics, `x[()]` selects zero rows but retains columns; for a scalar output with one `len` column, the resulting NumPy indexing tuple has one empty integer array, which a zero-dimensional `y` rejects. This independent follow-on issue would persist after upgrading Polars unless `pivot` is separately fixed.

**Executed:** standard-library source-equivalent empty-`Sequence` indexing and NumPy scalar indexing `IndexError` witness; [portable model](../../../../../../../tools/tests/test_mbi_fixed_empty_clique_model.py). **Not executed:** native Polars 1.36.1 or OpenDP and MBI integration. See [full cross-file analysis](../../../../../../../investigations/mbi-fixed-zero-clique-total-count.md).

### Stability-map construction

The map computes a contribution-distance tuple `(l0, min(total,l0*linf), linf)` from public `Bounds`, including the empty clique. For a one-cell total count, the numeric L1 sum bound is consistent with the `total` parameter under the stated representation assumptions. This was a narrow formula inspection, **not** a proof of every groupwise bound or clipping-saturation operation. The failure found is data-independent and occurs before DP noise is added, so there is no substantiated privacy-accounting defect for this property.

### Delegation

`make_noise_marginals` maps `zip(cliques,weights)` to noise measurements and composes them. `Fixed.make_marginals` derives one weight per `Count`, so list lengths match. Whether arbitrary direct callers may provide mismatched weight lengths is outside this zero-clique audit. No new issue is filed for arity.

## Next checks

Special-case `()` at the marginal transformation level, computing a zero-dimensional total with `data.select(pl.len())` and `y[()] = count`, and verify zero and positive private counts. Run native tests for both privacy measures and for named nonempty cliques.
