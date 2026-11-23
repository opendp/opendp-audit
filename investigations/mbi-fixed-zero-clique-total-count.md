---
schema_version: 1
upstream_commit: a010591f55b1713c926f8e355091471634480307
updated: 2026-11-23
status: Partial
---

# Fixed MBI zero-clique total-count query: accepted but not executable

## Invariant and threat model

The public `Fixed(queries=[Count(())])` configuration denotes a zero-dimensional (total-count) contingency marginal. Once accepted by `Count` and `Fixed`, it should return a scalar count after DP noise, or be rejected during construction. A data-independent empty-grouping error at the private-data invocation boundary violates correctness and availability, but it is not itself a privacy leak.

The audit covers accepted zero-clique configuration, MBI marginal transformation and Polars group-by execution. It does not attempt a full DP proof of Fixed, an MBI optimizer quality evaluation, or native OpenDP/Polars/MBI integration.

## Cross-file source trace

- [`Count.__post_init__`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/mbi/_utilities/__init__.py) validates the names in `by` via `all`; this accepts `by=()` because the predicate is vacuously true. Its normalization leaves an empty tuple.
- [`Fixed.__post_init__`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/mbi/_fixed/__init__.py) rejects an empty list of queries but accepts a list containing `Count(())`. `Fixed.make_marginals` passes `cliques=[()]` to `make_stable_marginals`, followed by Gaussian/Laplace noise and an MBI model fitter.
- [`make_stable_marginals`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/mbi/_utilities/__init__.py) computes `shape(clique)=tuple(cardinalities[c] for c in clique)` and calls `arrayd_domain(shape=(),T='i32')`. [`arrayd_domain`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/__init__.py) permits an empty shape tuple (the dimension-validity predicate is vacuous). At invocation it executes `pl.collect_all([data.group_by(c).agg(pl.len()) for c in cliques_snapshot])`.
- Pinned OpenDP [`python/setup.cfg`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/setup.cfg) requires `polars==1.36.1`; the Rust feature dependencies are patched to Polars tag [`py-1.36.1`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/Cargo.toml) at commit `2a151c10fa76790711c2f75e6d012dd69c627ddd` dated 2025-12-09. The matching [Polars group-by source](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-core/src/frame/group_by/mod.rs) rejects zero keys with `ComputeError: at least one key is required in a group_by operation`.

**The pinned-version defect** is thus a valid public zero-clique query that creates a transformation but cannot evaluate its plan. A later Polars PR [#27141](https://github.com/pola-rs/polars/pull/27141) merged on 2026-04-02 to rewrite zero-key `group_by` plans to `SELECT`. This merge **postdates** the December 2025 tag pinned by OpenDP, so it does not fix this release.

## Independent model of the follow-on pivot failure after upgrading

Even on a newer Polars with empty-group aggregation, the current OpenDP `pivot` callback has a separate zero-dimensional mismatch:

```python
y = np.zeros(shape(clique), dtype=np.int32)  # scalar when clique == ()
y[tuple(x[clique].to_numpy().T)] = (
    x["len"].clip(upper_bound=np.iinfo(np.int32).max).cast(pl.Int32).to_numpy()
)
```

In the Polars [`py-1.36.1` `get_df_item_by_key`](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/py-polars/src/polars/_utils/getitem.py), `x[()]` routes to `_select_rows`, where the empty sequence branch returns `df.clear()`. The [`DataFrame.clear`](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/py-polars/src/polars/dataframe/frame.py) method retains the **single** `len` column but changes the row count to zero. Therefore its `to_numpy().T` has shape `(1, 0)`, and `tuple(...)` gives a **single** empty integer index array, not the empty tuple that indexes a zero-dimensional NumPy scalar.

**Executed** on NumPy: `np.zeros((),dtype=np.int32)[tuple(np.empty((0,1),dtype=np.int64).T)]` raises `IndexError: too many indices for array: array is 0-dimensional, but 1 were indexed`. This is a **future-upgrade path**; the current pinned Polars fails at its earlier empty-group guard first.

An independent, dependency-light regression [`test_mbi_fixed_empty_clique_model.py`](../tools/tests/test_mbi_fixed_empty_clique_model.py) checks Count acceptance, source-equivalent empty row selection, invalid scalar pivot and correct `y[()]` assignment. NumPy-specific checks skip if NumPy is absent. It is not an execution of native OpenDP or Polars.

## Findings and disposition

**Finding:** [Candidate correctness issue #148](https://github.com/opendp/opendp-audit/issues/148). **Verification:** Reproduced source-level control flow and NumPy indexing model; pinned Polars/OpenDP executable integration unverified. **Upstream disposition:** Unreported at `a010591f55b1713c926f8e355091471634480307`. No identical upstream issue/PR or audit issue found in targeted closed/open searches. Related [Polars issue #23397](https://github.com/pola-rs/polars/issues/23397) and [Polars PR #27141](https://github.com/pola-rs/polars/pull/27141) repair **only the dependency's** zero-group key semantics, not OpenDP's scalar `pivot` handling.

No privacy-accounting violation or data-dependent disclosure was established: the public empty clique causes the same code path independently of private row values.

## Unresolved questions and remediation

1. Run native `Fixed(queries=[Count(())])` with a one-column encoded LazyFrame and valid contribution bounds at `polars==1.36.1`; check whether failure occurs during plan lowering or collection. The source is sufficient to predict an error, not its precise OpenDP exception wrapping.
2. Special-case empty cliques: use `data.select(pl.len())` and assign `y[()] = count` (with `i32` saturation), rather than `group_by(())` and `x[()]`.
3. Test empty and nonempty datasets, public domain dimensionality, zero-dimensional count and noise correctness, and both pure-DP and zCDP marginal paths.
4. If an empty workload is unsupported by design, reject `Count(())` explicitly and document the limitation. Since MBI elsewhere treats `clique=()` as a total count, supporting it is preferable.
