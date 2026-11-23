---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Gaussian threshold: L2 tightening and unstable-key delta

## Invariant and threat model

The thresholded Gaussian mechanism releases only keys whose noisy integer counts are strictly beyond a signed threshold. For integer count maps with bounded `(L0, L2, L∞)` distance, its privacy map should use a non-underestimating L2 sensitivity for stable keys and a non-underestimating probability of accidentally releasing any unstable key. A counterexample would be a pair of admissible neighboring maps whose stable-key zCDP parameter or unstable-key release probability exceeds the reported `(rho, delta)`.

This review is limited to the distance adjustment, Gaussian tail bound interface, delta composition, and obvious boundary branches. It does not establish a complete privacy proof for the sampler and FFI.

## Affected symbols and source audits

- [Gaussian threshold source audit](../source/rust/src/measurements/noise_threshold/distribution/gaussian/mod.rs.md) and [commit-pinned upstream source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/gaussian/mod.rs): distance tightening, magnitude check, and joint delta.
- [Additive discrete Gaussian privacy map](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/gaussian/mod.rs): negative-distance/scale checks and `rho >= L2^2/(2s^2)`.
- [Gaussian tail helpers](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/accuracy/tail_bounds/mod.rs): bound on `Pr[Z > m]` through a continuous Gaussian `erfc` calculation with directed rounding.
- [Threshold release closure](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/mod.rs): explicit-zero elimination, strict signed comparison, and shuffled retained pairs.
- [Upstream proof sketch](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/gaussian/NoiseThresholdPrivacyMap_for_ZExpFamily2.tex) and [existing tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/gaussian/test.rs).

## Reasoning and evidence

For any differences `d_i` between integer count maps, at most `L0` coordinates are nonzero, so `||d||_2 <= sqrt(L0) ||d||_∞`. Using an upward-rounded square root preserves this bound. Since each `|d_i|` is an integer, `||d||_∞ <= floor(L∞)` and `||d||_∞ <= floor(L2)`. The implementation uses these to tighten the input bounds before evaluating the additive Gaussian zCDP map.

For any unstable key absent from one map, its nonzero count has magnitude at most `L∞'`. With threshold magnitude `T >= L∞'` and symmetric Gaussian noise, the chance that this key is included is bounded by `Pr[Z > T - L∞']` for either signed threshold direction. The discrete Gaussian tail bound uses `P[Z > m] <= P[N(0, s²) >= m] = 0.5 * erfc(m/(sqrt(2) s))`, with the implementation attempting conservative directed rounding. For at most `L0` independently noised unstable keys, a bound `p_upper` per key gives `delta <= 1 - (1-p_upper)^L0`.

**Independently executed:** A Python 3 standard-library numerical check enumerated 20 configurations with scales `s = {0.5, 1, 2, 4}` and integer margins `m = {0, 1, 2, 3, 6}`. It approximated the discrete Gaussian tail by summing `exp(-k²/(2s²))` over `k > m` and normalizing by the symmetric lattice sum, truncating at `max(30, ceil(15s))`, then compared with `0.5 * math.erfc(m/(s*sqrt(2)))`. All 20 computed continuous tails exceeded the corresponding discrete tails; this is a **finite-sum floating-point sanity check**, not a formal bound and not execution of OpenDP Rust code.

For `s = 2`, `m = 2`, the approximate discrete one-key tail is `0.1032464043`, whereas the continuous bound is `0.1586552539`. For two independently sampled unstable keys (`L0 = 2`), the continuous-bound joint delta is approximately `0.2921390183`. At `L2' = sqrt(2)` the ideal stable-key Gaussian parameter is `rho = L2'^2/(2s²) = 0.25`. These values are cross-checks of the mathematical formulas, **not** asserted exact outputs of OpenDP's rounded implementation.

The upstream Gaussian threshold unit tests exercise negative `L2`, zero sensitivity, zero scale, strict positive/negative thresholds, float/integer domains, large scale, and an empirical tail comparison. They were inspected but **not run** during this session. Neither the `erfc` approximation claim nor all extreme-parameter rounding paths were independently verified.

## Findings

No new defect identified **within the declared scope and assumptions**. Earlier incorrect threshold inclusivity was addressed by [upstream PR #3058](https://github.com/opendp/opendp/pull/3058), merged before the reviewed revision; this report does not reopen it. No new issue or upstream PR is warranted by the evidence gathered here.

## Unresolved questions

- Execute compiled Rust tests and independent high-precision comparisons of the conservatively rounded Gaussian tail helper for extreme scales and margins.
- Check the `1 - (1-p)^L0` directed-rounded computation near `p = 0` and `p = 1` and at `L0 = u32::MAX`.
- Assess distributional independence, entropy errors, and the complete proof of approximate-zCDP composition, including float-to-integer adapters.
