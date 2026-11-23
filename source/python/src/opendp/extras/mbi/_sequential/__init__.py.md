---
schema_version: 1
source: python/src/opendp/extras/mbi/_sequential/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/mbi/_sequential/__init__.py`

## Scope and assumptions

- **Scope:** Validation and snapshot of `Sequential.weights`, allocation computation in `Sequential.make_marginals`, and the first Rust adaptive-composition budget guard. This is a single contract property, not an audit of all nested MBI algorithms or synthesized model outputs.
- **Invariant:** Public relative weights used to allocate finite privacy budget must be finite and strictly positive. A rejected non-finite allocation must not reach a private-data invocation under a falsely finite privacy map.
- **Pinned upstream:** [Sequential source](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_sequential/__init__.py), [sibling Count guard](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_utilities/__init__.py#L57-L76), and [Rust adaptive composer](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/combinators/sequential_composition/adaptive/mod.rs).
- **Cross-file evidence:** [Investigation](https://github.com/opendp/opendp-audit/blob/main/investigations/mbi-sequential-nonfinite-weight-budget.md); [audit task #118](https://github.com/opendp/opendp-audit/issues/118); [correctness finding #119](https://github.com/opendp/opendp-audit/issues/119).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `Sequential.__post_init__` | correctness/finite-budget-weights | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Non-finite acceptance](#non-finite-acceptance); [finding #119](https://github.com/opendp/opendp-audit/issues/119) |
| `Sequential.make_marginals` | privacy/adaptive-allocation-validation | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Composer boundary](#composer-boundary); [investigation](https://github.com/opendp/opendp-audit/blob/main/investigations/mbi-sequential-nonfinite-weight-budget.md) |
| `Sequential.make_marginals` | correctness/weight-snapshot | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Snapshot and normalization](#snapshot-and-normalization) |

## Analysis

### Non-finite acceptance

[At lines 55–63](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_sequential/__init__.py#L55-L63), `Sequential.__post_init__` validates that the list length matches `algorithms` and rejects weights for which `w <= 0`. Both `float('nan')` and `float('inf')` fail that reject predicate, and so enter `self.weights` unchanged. A relative budget allocation of NaN or infinity is not a finite positive real.

This differs from the sibling MBI [`Count.__post_init__`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_utilities/__init__.py#L57-L76), which normalizes to `float` and explicitly rejects non-finite values with `isfinite`. The upstream `test_sequential_init` validates zero and length/type mismatch but omits non-finite test cases.

A locally executed source-equivalent Python harness used the constructor guard unchanged with a dummy `Algorithm` parent, accepting weights `nan` and `+inf` and rejecting `0.0` and `-1.0`. `np.array([nan, inf]) * 0.1` produced `[nan, inf]`. This was **not a full OpenDP/MBI run**.

### Snapshot and normalization

`make_marginals` calls `_check_and_snapshot_algorithm(self)`, which deep-copies its configuration and reruns `__post_init__`; this maintains the same defective finite-weight check rather than supplying new validation. It creates `weights = np.array(algorithm.weights or [1] * len(algorithms))` and uses `weights * scale` in `binary_search_param` and again as the actual `d_mids` allocation. Thus invalid weights propagate into the **public** budget search instead of being rejected at the configuration boundary.

The absence of post-construction mutation to `weights` is covered by the local `tuple` snapshot and the later deepcopy. Full stability of all nested algorithm descriptors and arbitrary caller-owned objects is not asserted by this property review.

### Composer boundary

The Rust [`make_adaptive_composition`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/combinators/sequential_composition/adaptive/mod.rs) checks `d_mid.total_ge(&zero)?` for every allocation before returning a measurement. `f64`'s [`ProductOrd::total_cmp`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/traits/operations/mod.rs#L341-L351) uses `partial_cmp` and returns an error on NaN. Consequently, a NaN allocation cannot be admitted by this guard as a valid nonnegative allocation. Infinite allocations cannot satisfy a finite total privacy budget under normal composition/check semantics.

This is a **source-backed negative privacy finding**, not a demonstrated privacy bypass. The full runtime path could reject even earlier in FFI conversion. No native OpenDP, Polars, MBI, or Rust tests were executed in this review; the result is **Partial** for end-to-end privacy behavior.

## Disposition and next checks

**Reproduced public parameter-validation defect**, filed as [audit issue #119](https://github.com/opendp/opendp-audit/issues/119), labeled `correctness`, not `privacy`. Targeted upstream issue/PR search found no equivalent report or pending correction. No underreported privacy loss or private-data-dependent exception was established.

Fix: require finite positive weights in `Sequential.__post_init__`. Add a real upstream test for `nan`, `inf`, `-inf`, zero, negative, finite positive, and large finite weight inputs. Verify that invalid weights fail before the parameter search, and that legitimate weights still yield a measurement with `measurement.check(d_in, d_out)` true.

More details and exact branch reasoning: [cross-file investigation](https://github.com/opendp/opendp-audit/blob/main/investigations/mbi-sequential-nonfinite-weight-budget.md).
