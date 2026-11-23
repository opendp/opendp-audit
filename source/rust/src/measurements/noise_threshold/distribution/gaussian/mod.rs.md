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

| `measurements::noise_threshold::distribution::gaussian::NoiseThresholdPrivacyMap::noise_threshold_privacy_map` | numerical/delta-resolution | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Joint delta precision floor](#joint-delta-precision-floor) |

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

**Conclusion:** No evidence of an **understated privacy bound** in the bounded analysis. A separate numerical **overestimation** defect in the joint delta expression is documented below. The overall privacy property remains **Partial** pending a compiled Rust test run, verified elementary tail helper bounds at extreme inputs, and review of the sampler.

### Joint delta precision floor

**New numerical finding:** The expression is conservative but has a binary64 precision floor around `2^-53` for `L0 = 1` and positive `delta_single < 2^-53`. This causes a loss of privacy-accounting tightness, not an understated privacy loss. See [candidate issue #3](https://github.com/opendp/opendp-audit/issues/3) and the [cross-file roundoff investigation](https://github.com/opendp/opendp-audit/blob/main/investigations/threshold-delta-roundoff-floor.md).

For example with Gaussian `scale=1`, `threshold=11`, and distance `(L0,L2,L∞)=(1,1,1)`, the single-key tail upper bound is approximately `7.62e-24`. Directed subtraction rounds `1 - p` down to the `f64` immediately below 1, yielding a joint bound of `2^-53 ≈ 1.1102230246251565e-16`. A conservative union bound would instead be `p` for `L0=1`. This is **Audited** as a numerical cancellation effect from the pinned source and independently executed Python arithmetic, not a compiled Rust regression.

## Next checks

- Run the upstream Gaussian threshold, tail-bound and directed arithmetic tests on commit `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`.
- Test extreme rational scales and threshold margins, large `L0`, and underflow/overflow in `erfc` and the joint delta expression.
- Verify Gaussian sampler distribution / independence and end-to-end approximate-zCDP proof obligations; no blanket privacy certification follows from this review.
