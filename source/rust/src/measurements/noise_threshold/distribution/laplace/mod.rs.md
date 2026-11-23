---
schema_version: 1
source: rust/src/measurements/noise_threshold/distribution/laplace/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/noise_threshold/distribution/laplace/mod.rs`

## Scope and assumptions

- **Audit scope:** `ZExpFamily<1>`'s `NoiseThresholdPrivacyMap<L01InfDistance<AbsoluteDistance<RBig>>, Approximate<MaxDivergence>>` implementation, specifically integer sensitivity tightening, zero-sensitivity/zero-scale behavior, the threshold margin, and the calculation of approximate-DP delta. Also inspected the additive Laplace privacy map, both tail-bound helpers, the thresholded release predicate, and existing tests.
- **Invariants:** (1) Negative `L1` or `L∞` distance bounds are rejected. (2) A distance tuple that permits only identical integer maps has privacy cost `(0, 0)`. (3) For positive sensitivity, an error or a conservative `(epsilon, delta)` bound is returned, with the unstable-key delta no smaller than the true probability of releasing an absent key.
- **Assumptions:** Distances describe pairs of integer-valued maps under `L01InfDistance`; noise draws are independent, correctly distributed discrete Laplace samples; the released map ignores explicit zero-valued entries and shuffles retained pairs. The individual tail-bound functions and directed floating-point arithmetic satisfy their documented upper-bound contracts. This is a scoped source audit, **not** a complete privacy proof.
- **Pinned sources:** [Laplace threshold privacy map](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/laplace/mod.rs), [Laplace privacy map](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/laplace/mod.rs), [tail bounds](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/accuracy/tail_bounds/mod.rs), [core release predicate](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/mod.rs), [formal argument](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/laplace/NoiseThresholdPrivacyMap_for_ZExpFamily1.tex), and [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/laplace/test.rs).
- **Related audit:** [Core threshold mechanism](https://github.com/opendp/opendp-audit/blob/main/source/rust/src/measurements/noise_threshold/mod.rs.md), which covers zero-valued keys and strict signed filtering but not this privacy-map analysis.

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::noise_threshold::distribution::laplace::NoiseThresholdPrivacyMap::noise_threshold_privacy_map` | correctness/sensitivity-tightening | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Distance guards and tightening](#distance-guards-and-tightening) |
| `measurements::noise_threshold::distribution::laplace::NoiseThresholdPrivacyMap::noise_threshold_privacy_map` | privacy/zero-sensitivity | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Zero-sensitivity and zero-scale branches](#zero-sensitivity-and-zero-scale-branches) |
| `measurements::noise_threshold::distribution::laplace::NoiseThresholdPrivacyMap::noise_threshold_privacy_map` | privacy/laplace-tail-accounting | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Positive-sensitivity epsilon and delta](#positive-sensitivity-epsilon-and-delta) |
| `measurements::noise_threshold::distribution::laplace::NoiseThresholdPrivacyMap::noise_threshold_privacy_map` | numerical/delta-resolution | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Joint delta precision floor](#joint-delta-precision-floor) |

## Analysis

### Distance guards and tightening

The privacy map floors each `RBig` distance bound `l1` and `li`, checks that their integer parts are nonnegative, and otherwise returns `FailedMap`. Since differences of integer-valued maps have integer `L1` and `L∞` norms, flooring a nonnegative bound does not exclude any permitted neighboring pairs.

Let `L0 = l0`, `L1 = floor(l1)`, and `L∞ = floor(li)`. The implementation computes `L1' = min(L1, L0 * L∞)`, then `L∞' = min(L∞, L1')`. Any pair of maps satisfying the original bounds satisfies both tightened bounds because `||x-x'||_1 <= ||x-x'||_0 * ||x-x'||_∞` and `||x-x'||_∞ <= ||x-x'||_1`. The operations are exact arbitrary-precision integer operations for these fields.

**Conclusion:** No missing nonnegative check or unsound tightening identified for integer-valued maps. This assessment does not cover the original distance supplied by a caller being an accurate sensitivity bound.

### Zero-sensitivity and zero-scale branches

If any of `L0`, `L1`, or `L∞` is zero, `L1'` is zero and the map returns `(0, 0)`. Under the stated metric, this allows no nonzero coordinate differences between neighboring integer maps; after explicit zeros are ignored, the release distribution is identical. The branch is taken before the zero-noise-scale check, appropriately permitting `(0, 0)` when the input distance is zero even if noise scale is zero.

For `L1' > 0` with zero scale, the map returns `(infinity, 1)`, a vacuous bound rather than falsely promising privacy. Negative scale is rejected while constructing the delegated additive-noise privacy map.

**Conclusion:** These edge-case privacy-map branches are consistent with the scoped invariant.

### Positive-sensitivity epsilon and delta

For positive `L1'` and noise scale `s > 0`, the delegated additive Laplace map computes an upper-rounded `epsilon >= L1'/s`. The map then requires the threshold magnitude `T >= L∞'` or returns an error. Thus the instability margin `m = T - L∞'` is nonnegative.

The two candidate single-key tail bounds are `conservative_discrete_laplacian_tail_to_alpha(s, m)` and `conservative_continuous_laplacian_tail_to_alpha(s, m)`. Their documented bounds are respectively no smaller than `Pr[Z > m]` for discrete Laplace and the conservative continuous relaxation. The code keeps the minimum of successfully computed candidates; taking the minimum preserves an upper bound **only under both helpers' conservative-bound contracts**. If both fail, the map returns an error rather than a fabricated delta.

For integer `m >= 0`, the exact discrete Laplace one-key tail is `p = exp(-m/s) / (exp(1/s) + 1)`. For at most `L0` independently sampled unstable keys, the probability of one or more releases is bounded by `1 - (1-p)^L0`. The implementation evaluates `1 - (1-delta_single)^L0` using the downward-rounded subtraction/power for the survival probability, followed by upward-rounded subtraction for delta, and caps the result at 1.

**Independent arithmetic sanity check (not OpenDP execution):** A separate Python `math` calculation for `s=1`, `T=3`, `L0=2`, `L1=2`, `L∞=1` yields `epsilon=2`, `p≈0.0363972634`, and `delta≈0.0714697661` from the exact formulas. This verifies only the algebra of a representative case; it does **not** test the Rust helpers or certify directed rounding.

The signed-negative threshold direction uses the same magnitude-based map and is justified by the symmetry of the Laplace noise; the core mechanism filters values below a negative threshold. Existing upstream tests include integer, float, large-scale, zero-scale, signed-threshold and empirical release cases. These tests were inspected but not run here.

**Conclusion:** No contradictory bound identified under the stated tail and sampler contracts. The property is **Partial** because the contracts, extreme-parameter directed rounding, independence of underlying samplers, and the full privacy proof were not independently established.

### Joint delta precision floor

**New numerical finding:** The expression is conservative but has a binary64 precision floor around `2^-53` for `L0 = 1` and positive `delta_single < 2^-53`. This causes a loss of privacy-accounting tightness, not an understated privacy loss. See [candidate issue #3](https://github.com/opendp/opendp-audit/issues/3) and the [cross-file roundoff investigation](https://github.com/opendp/opendp-audit/blob/main/investigations/threshold-delta-roundoff-floor.md).

The Laplace privacy map uses the same `1 - (1-p)^L0` directed-rounding chain. For `L0=1` and any positive `p` below `2^-53`, the computed delta is bounded below by `2^-53` although the direct conservative union bound `p` is much smaller. The effect is **Audited** at the source arithmetic level; the exact Laplace threshold reproducer has not been run as compiled Rust.

## Next checks

- Execute the upstream Laplace threshold and tail-bound Rust test suites at the reviewed commit; this session did not build OpenDP.
- Independently test the two conservative tail helpers and directed delta composition for large `L0`, very small positive tail mass, and extremely large `RBig` scales/thresholds.
- Review the Gaussian threshold privacy map separately, especially its `L2` tightening, integer `L∞` conversion, and tail arithmetic.
- If a counterexample is found, check open/closed upstream and audit issues and PRs before filing. No defect was established in this scoped review.
