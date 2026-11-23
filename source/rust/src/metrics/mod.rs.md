---
schema_version: 1
source: rust/src/metrics/mod.rs
updated: 2026-11-22
---

# `rust/src/metrics/mod.rs`

## Scope and assumptions

- **Audit scope:** The cross-length adjacency semantics of `LInfDistance<Q>` as used by `make_noisy_top_k`, contrasted with the explicit cross-length contract of `LpDistance<P,Q>` and the vector-domain metric-space compatibility check.
- **Invariant:** If successful outputs reveal input length and two different-length inputs are finite-distance neighbors, then finite pure-DP and zCDP bounds cannot both hold for the pair. Conversely, if different-length vectors have infinite distance, the length disclosure is not a privacy-map counterexample.
- **Assumptions:** The ordinary coordinate-wise definition of vector differences is evaluated only for vectors of equal dimension unless otherwise specified by the metric. This is a mathematical convention, **not** an implementation guarantee or a confirmed OpenDP contract.
- **Source links:** [Upstream metrics](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/mod.rs), [vector domain](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/mod.rs), [Polars fixed-width array metric check](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/expr/mod.rs), [noisy top-k investigation](../../../../investigations/noisy-top-k-privacy-calibration.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `metrics::LInfDistance<Q>` | privacy/cross-length-adjacency | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-metric comparison](#analysis) |
| `metrics::LpDistance<P,Q>` | privacy/cross-length-adjacency | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Explicit infinite-distance rule](#analysis) |
| `MetricSpace for (VectorDomain<AtomDomain<T>>, LInfDistance<T>)` | domain/size-compatibility | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Compatibility check](#analysis) |

## Analysis

### Explicit and implicit cross-length rules

The pinned `LpDistance<P,Q>` proof definition explicitly states that if vectors `u` and `v` have different lengths, their distance is infinity. The `LInfDistance<Q>` proof definition separately gives the coordinate-wise difference formula, `max_i |x_i - x'_i|` (or infinity when the monotonic sign condition fails), **without** the corresponding clause for different-length vectors. The explicit `LpDistance` clause is relevant precedent for how OpenDP treats dimensional mismatch, but is **not** mechanically inherited by the distinct `LInfDistance` type.

For `LInfDistance` and `VectorDomain<AtomDomain<T>>`, the `MetricSpace::check_space` implementation rejects NaN-permitting element domains and otherwise returns success; it does not require `VectorDomain.size = Some(n)`. The unsized vector domain permits variable lengths. Therefore construction-time metric-space compatibility by itself does not assert that different lengths are finite-distance neighbors. It only checks whether the supplied domain and metric form a valid combination under the library's claimed mathematical semantics.

A second distinct consumer, the Polars `ExprDomain` implementation of `LInfDistance`, requires an array-typed numeric column, which has a fixed width specified by its dtype. This is evidence of use on fixed-dimensional arrays, **not** a guarantee for unsized Rust vectors.

### Conditional privacy implication for top-k

In `noisy_top_k`, every successful output has length `min(k, input.len())`. Thus, at public `k = 2`, inputs of lengths 1 and 2 yield outputs of lengths 1 and 2 respectively, with disjoint support. If those inputs were finite-distance neighbors, no finite pure-DP or zCDP map could be valid for that pair. If they have infinite metric distance, the output-length behavior is compatible with the privacy claim and no defect follows. The independent Python 3 source-semantics model checked all 320 combinations of `n=0..7`, `k=0..9`, and both boolean selection flags; cardinalities matched the formula. It did **not** execute Rust.

**Conclusion:** The retrieved proof definition is insufficient to decide cross-length closeness for `LInfDistance`. The strongest defensible reading is an open **contract/documentation question**, with a plausible fixed-dimension interpretation supported by `LpDistance` precedent and the fixed-width Polars use case. This is **not** a confirmed privacy defect; do not open a bug issue based solely on variable-length output.

## Next checks

- Locate an explicit upstream proof or definition for `LInfDistance` on unequal-length vectors, or clarify the proof documentation to state their distance is infinite/undefined as appropriate.
- If unequal-length vectors are intended to be finite-distance neighbors, re-evaluate `make_noisy_top_k` and `make_noisy_max` with concrete support-disjointness and error-path examples.
- Run native Rust tests if a runnable upstream checkout and toolchain are available; this audit used pinned source, documentation, and a Python model only.
