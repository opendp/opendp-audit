---
schema_version: 1
upstream_commit: 7acfb2cdcee7d39fc26a6ade7edac15249c52f4b
updated: 2026-11-23
status: Partial
---

# MBI Sequential non-finite weight validation and composition boundary

## Contract and threat model

`Sequential` allocates a caller-provided total privacy budget to child MBI algorithms using public relative weights. The intended precondition is that each weight is a finite positive real number; otherwise a budget search may receive a `NaN` or infinite per-child allocation.

The reviewed privacy property is narrower: **does the invalid public weight induce a false finite privacy claim or reach private data before Rust's adaptive composer checks it?** This is not an audit of arbitrary custom algorithm implementations, and it does not assume a native `mbi` run.

## Pinned source

- [`Sequential.__post_init__` lines 44–65](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_sequential/__init__.py#L44-L65): checks `any(w <= 0 for w in self.weights)`; no `isfinite` check.
- [`Sequential.make_marginals` lines 103–116](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_sequential/__init__.py#L103-L116): creates a NumPy weight vector, searches a scalar multiplier with `make_adaptive_composition(d_mids=weights*scale)`, then reuses these allocations to construct the actual compositor.
- [`Count.__post_init__` lines 57–76](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_utilities/__init__.py#L57-L76): sibling MBI weight validates `isfinite(self.weight)`.
- [`make_adaptive_composition`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/combinators/sequential_composition/adaptive/mod.rs): iterates over allocated distances and verifies `d_mid.total_ge(zero)` before constructing a measurement; also reserves each accepted query's budget before invoking the measurement on private data.
- [`ProductOrd` for floats](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/traits/operations/mod.rs#L341-L351): partial comparison returns an error when either side is NaN.
- [`CompositionMeasure` pure-DP/zCDP](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/combinators/sequential_composition/mod.rs#L59-L77): composes per-child allocations with a sum.

## Evidence

Python's comparison `float('nan') <= 0` is `False`; `float('inf') <= 0` is also `False`. Consequently `Sequential(weights=[nan])` and `Sequential(weights=[inf])` pass the current guard (assuming a valid child algorithm). This contradicts the semantics of positive **finite** budget allocations and the explicit `Count.weight` constraint.

An isolated Python source-equivalent harness was run using the unchanged `Sequential.__post_init__` guard and a dummy `Algorithm` parent. Observations:

| Weight | Constructor guard | `np.array([weight])*0.1` |
| --- | --- | --- |
| `1.0` | Accepted | `[0.1]` |
| `float('nan')` | Accepted | `[nan]` |
| `float('inf')` | Accepted | `[inf]` |
| `0.0` | Rejected | Not evaluated |
| `-1.0` | Rejected | Not evaluated |

This is **not** an import of the actual `opendp` package, native adaptive composition, or end-to-end MBI execution. The original upstream test `test_sequential_init` covers mismatched counts and zero but not NaN/infinity.

## Privacy accounting

1. `Sequential.make_marginals` performs a public parameter search that attempts to construct a compositional measurement for the proposed `d_mids`, before invoking a child measurement.
2. If a NaN allocation reaches Rust, `make_adaptive_composition`'s nonnegative-distance guard calls `total_ge(zero)`; `f64::partial_cmp` returns `None` for NaN, and the `ProductOrd` implementation turns that into `Err`. The malformed allocation does **not** pass as an unrestricted valid privacy budget.
3. A positive-infinite allocation can be nonnegative, but its composed total is infinite and therefore cannot satisfy a **finite** overall budget via the ordinary `check` comparison. It produces unusable parameter-search behavior rather than a falsely finite privacy guarantee.
4. Any FFI conversion error might occur still earlier. No concrete data-dependent exception, unaccounted invocation, or private release on invalid weights was demonstrated.

The issue is therefore **correctness / parameter validation**, not a confirmed privacy loss. This boundary check is **Partial** because native MBI/FFI code was not executed and no claim is made about all potential non-finite numeric cases.

## Disposition

The defect is tracked in [audit #119](https://github.com/opendp/opendp-audit/issues/119). Targeted searches of open/closed upstream issues, audit issues, and upstream PRs found no equivalent report or pending fix on current `main`. [Audit task #118](https://github.com/opendp/opendp-audit/issues/118) coordinates the bounded review.

Corrective action: validate each weight as a finite positive real at `Sequential.__post_init__`, consistent with `Count` (e.g. normalize to `float`, then `math.isfinite(w) and w>0`). Add direct tests covering NaN and positive/negative infinity as well as valid finite weights. Native OpenDP/MBI budget-search integration remains the decisive downstream regression.
