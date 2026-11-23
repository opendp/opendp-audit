---
schema_version: 1
source: python/src/opendp/extras/mbi/_fixed/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/mbi/_fixed/__init__.py`

## Scope and assumptions

- **Property:** `Fixed` public query acceptance, zero-dimensional clique support, and its delegation to a bounded-count marginal under the current non-deprecated MBI API.
- **Invariant:** If the constructor accepts a one-query workload `Fixed(queries=[Count(())])`, a valid `make_marginals` chain must be executable over every admitted dataset or reject unsupported cliques before private-data invocation.
- **Assumptions:** Caller supplies a valid indexed LazyFrame with bounded integer cardinalities and a valid `FrameDistance(SymmetricDistance)` contribution bound. The MBI estimator is an ordinary pure postprocessor. This audit does not certify its optimizer or the full marginal noise privacy proof.
- **Pinned source:** [`Fixed`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/mbi/_fixed/__init__.py), [`Count` and `make_stable_marginals`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/mbi/_utilities/__init__.py); [cross-file investigation](../../../../../../../investigations/mbi-fixed-zero-clique-total-count.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `Fixed.__post_init__` | correctness/empty-clique-admission | Audited | `a010591f55b1713c926f8e355091471634480307` | [Workload acceptance](#workload-acceptance), [defect #148](https://github.com/opendp/opendp-audit/issues/148). |
| `Fixed.make_marginals` | correctness/zero-dimensional-total-count-execution | Partial | `a010591f55b1713c926f8e355091471634480307` | [Count-to-Polars delegation](#count-to-polars-delegation), [cross-file investigation](../../../../../../../investigations/mbi-fixed-zero-clique-total-count.md). |
| `Fixed.make_marginals` | privacy/composition-of-fixed-workload | Partial | `a010591f55b1713c926f8e355091471634480307` | [Composition boundary](#composition-boundary); full native DP proof not attempted. |

## Analysis

### Workload acceptance

`Fixed.__post_init__` validates that at least one query is present and that all entries are `Count`, then snapshots the queries using `Count(q.by, q.weight)`. `Count` only verifies each element in `by` is a string. It accepts the empty grouping tuple, yielding an accepted `Fixed(queries=[Count(())])` instance.

### Count-to-Polars delegation

`Fixed.make_marginals` builds `cliques=[q.by for q in algorithm.queries]`, preserving the empty tuple, then composes `make_stable_marginals(..., cliques)` with `then_noise_marginals(...)`. With `clique=()`, the resulting stable marginal calls `data.group_by(()).agg(pl.len())` on execution.

OpenDP pins Polars 1.36.1, whose core group-by requires at least one key. A later Polars fix for empty keys postdates that pin. The accepted Fixed total-count workload therefore reaches a source-supported data-independent execution error instead of computing the total. Independently, if an upgraded Polars supports the empty grouping, the current scalar pivot indexing is still invalid. See [cross-file investigation](../../../../../../../investigations/mbi-fixed-zero-clique-total-count.md) and [candidate #148](https://github.com/opendp/opendp-audit/issues/148).

### Composition boundary

The fixed algorithm calibrates a global scale via `binary_search` against the composed noisy marginals and uses that checked scale to build a measurement. Nothing in this delegated privacy-map construction changes the public zero-clique runtime failure. This audit did not verify the entire noise law, typed dictionary metric, or estimator postprocessing. **No privacy-accounting error was identified in the reviewed branches**; the defect is the acceptance/execution mismatch.

**Executed:** a standard-library model of empty-clique acceptance and a NumPy model of the later scalar pivot failure. **Not executed:** installed OpenDP, pinned Polars 1.36.1, the full MBI estimator, or native FFI invocation.

## Next checks

Run a native regression for `Count(())` at the pinned Polars version. Branch on the empty clique to compute `pl.len()` without group-by and assign a zero-dimensional count without `x[()]`. Keep other valid cliques unchanged.
