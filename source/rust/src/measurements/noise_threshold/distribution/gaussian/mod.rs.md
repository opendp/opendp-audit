---
schema_version: 1
source: rust/src/measurements/noise_threshold/distribution/gaussian/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/noise_threshold/distribution/gaussian/mod.rs`

## Scope and assumptions

- **Scope:** The `NoiseThresholdPrivacyMap` implementation for `ZExpFamily<2>` (approximate zCDP), including nonnegative distance guards, L2/L∞ tightening, zero-scale and zero-distance cases, and the unstable-key delta calculation.
- **Invariants:** A privacy map must reject invalid negative sensitivity, not underestimate the distance or the event probability of releasing keys absent in a neighbor, and not claim positive privacy loss when the only admissible pairs are equal.
- **Assumptions:** The input map has integer-valued counts, `L02InfDistance` measures these counts with missing keys treated as zero, Gaussian samples are independent and follow the specified law, and directional arithmetic / Gaussian-tail helpers honor their contracts. A complete proof of these dependencies is out of scope.
- **Pinned sources:** [Gaussian threshold privacy map](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/gaussian/mod.rs), [additive Gaussian privacy map](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/gaussian/mod.rs), [tail bound](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/accuracy/tail_bounds/mod.rs), and [Gaussian threshold tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/gaussian/test.rs).
- **Cross-file analysis:** [Gaussian threshold delta investigation](https://github.com/opendp/opendp-audit/blob/main/investigations/gaussian-threshold-tail-accounting.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::noise_threshold::distribution::gaussian::NoiseThresholdPrivacyMap::noise_threshold_privacy_map` | correctness/gaussian-sensitivity-tightening | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Sensitivity tightening](#sensitivity-tightening) |
| `measurements::noise_threshold::distribution::gaussian::NoiseThresholdPrivacyMap::noise_threshold_privacy_map` | privacy/gaussian-zero-distance | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Zero distance and zero noise scale](#zero-distance-and-zero-noise-scale) |
| `measurements::noise_threshold::distribution::gaussian::NoiseThresholdPrivacyMap::noise_threshold_privacy_map` | privacy/gaussian-tail-composition | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Tail and delta accounting](#tail-and-delta-accounting) |

## Analysis

### Sensitivity tightening

The code floors the nonnegative `L∞` bound to an integer and rejects negative values. Since count differences are integral, this loses no admissible neighboring pairs. It next computes
`L2' = min(L2, floor(L∞) * upward_sqrt(L0))`, where `upward_sqrt` is `f64::inf_sqrt`, and then `L∞' = min(floor(L∞), floor(L2'))`. Since at most `L0` coordinates differ and `||d||_∞ <= floor(L∞)`, these updates do not underestimate an actual feasible norm. `u32 -> f64` conversion for `L0` is exact and the square root is rounded upward. Negative `L2'` is rejected by the delegated Gaussian noise privacy map, which is called before the zero-distance return. The `L2` tightening is performed on an exact rational value and an upper-rounded float converted into a rational.

**Conclusion:** No unsound tightening or missing negative-distance guard identified for integer-valued counts.

### Zero distance and zero noise scale

If `L0 = 0`, or `L∞ < 1`, the tightened `L2'` is zero for valid nonnegative bounds. The map then returns `(rho, delta) = (0, 0)` after delegated noise validation. This is justified because integer-map neighbors under those constraints cannot differ. If `L2' > 0` and the distribution has zero scale, the map returns `(infinity, 1)` rather than claiming a finite privacy bound. Negative scales are rejected during `noise_privacy_map` construction.

**Conclusion:** No defect found in these branches under the stated distance model. Upstream contains tests for `(0,0,0)`, negative `L2`, and zero scale.

### Tail and delta accounting

After evaluating `rho >= L2'^2 / (2 s^2)`, the map requires `threshold magnitude >= L∞'`, otherwise it returns an error. For margin `m = T - L∞' >= 0`, it obtains an upper bound `p_upper` on `Pr[Z > m]` from `conservative_discrete_gaussian_tail_to_alpha`. Given at most `L0` unstable keys and independent noise draws, the joint bound is `delta <= 1 - (1 - p_upper)^L0` with directed floating-point rounding away from underestimation and a final cap at 1.

The Gaussian tail helper applies the continuous Gaussian tail bound at the integer threshold, using downward-rounded `t/(s sqrt(2))` and an upward adjustment to the single-precision `erfc` result. This review checked the call graph, parameter signs, and the intended rounding directions, but **did not independently prove the library's `erfc` error bound**. See the [cross-file investigation](https://github.com/opendp/opendp-audit/blob/main/investigations/gaussian-threshold-tail-accounting.md) for an independent finite-sum numerical sanity check covering 20 cases.

**Conclusion:** No counterexample identified in the bounded analysis. The status remains **Partial** pending a compiled Rust test run, verified elementary tail helper bounds at extreme inputs, and review of the underlying random sampler.

## Next checks

- Run the upstream Gaussian threshold, tail-bound and directed arithmetic tests on commit `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`.
- Test extreme rational scales and threshold margins, large `L0`, and underflow/overflow in `erfc` and the joint delta expression.
- Verify Gaussian sampler distribution / independence and end-to-end approximate-zCDP proof obligations; no blanket privacy certification follows from this review.
