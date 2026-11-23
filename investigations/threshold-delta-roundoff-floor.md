---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Thresholded Laplace/Gaussian joint-delta rounding floor

## Invariant and threat model

When a thresholded release has at most `L0` unstable keys and a conservative per-key release probability `p`, the reported `delta` must not underestimate their joint release probability. In addition to this safety invariant, a useful implementation should avoid losing many orders of magnitude of tightness to floating-point cancellation where a much smaller conservative union bound remains representable.

This is a numerical **utility/accounting-tightness** investigation, not a demonstrated privacy violation. It examines the common `1 - (1-p)^L0` expression for Laplace and Gaussian threshold mechanisms, for small positive `p`. It does not establish the sampler distributions or all tail-helper rounding guarantees.

## Affected symbols and source audits

- [Gaussian privacy-map source report](../source/rust/src/measurements/noise_threshold/distribution/gaussian/mod.rs.md); [upstream Gaussian map](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/gaussian/mod.rs): evaluates a single-key Gaussian tail and the joint delta.
- [Laplace privacy-map source report](../source/rust/src/measurements/noise_threshold/distribution/laplace/mod.rs.md); [upstream Laplace map](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/laplace/mod.rs): uses the identical joint expression.
- [`InfSub`/`InfPowI` implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/arithmetic/mod.rs): `neg_inf_sub` and `neg_inf_powi` evaluate with downward rounding via `FBig::<Down>` then cast to `f64`, while `inf_sub` rounds up.
- [Gaussian tail helper](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/accuracy/tail_bounds/mod.rs): computes an upper bound via `erfc` and controlled `f32` rounding; this is distinct from the *joint* delta cancellation described below.
- [Gaussian regression tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/gaussian/test.rs) and [Laplace regression tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/laplace/test.rs) assert `delta = 1.1102230246251565e-16` for high-threshold parameters.
- [Audit candidate #3](https://github.com/opendp/opendp-audit/issues/3).

## Reasoning and evidence

Both privacy maps contain:

```rust
let delta_joint: f64 = (1.0).inf_sub(
    &(1.0)
        .neg_inf_sub(&delta_single)?
        .neg_inf_powi(IBig::from(*l0))?,
)?;
```

For `0 < p = delta_single < 2^-53`, the exact real number `1 - p` lies strictly between 1 and the immediately smaller binary64 value `1 - 2^-53`. Its downward-rounded `f64` value is therefore **`1 - 2^-53`**. When `L0 = 1`, the downward power is unchanged and the final subtraction gives **`2^-53 = 1.1102230246251565e-16`**. This upper bound remains conservative; it is simply much looser than necessary.

**Concrete Gaussian witness (predicted from the source):** Use an integer-count domain, `scale = 1`, threshold `T = 11`, and privacy-map distance `(L0, L2, L∞) = (1, 1, 1)`. The tightened sensitivity remains 1, and the instability margin is `m = T - L∞ = 10`. An independently rounded single-precision model of the Gaussian tail helper gives `p_upper ≈ 7.619854396993087e-24`. Yet the joint-delta expression yields `2^-53`, a bound approximately **14.57 million times larger**. The direct union bound `L0 * p_upper = p_upper` is conservative and below `10^-20`. Hence the current calculation can reject a `delta = 10^-20` target even though a much smaller valid upper bound is available.

**Executed independently in Python 3:**

```python
import math
p_upper = 7.619854396993087e-24
survival_down = math.nextafter(1.0, -math.inf)
assert survival_down == 0.9999999999999999
assert 1.0 - survival_down == 2**-53
assert p_upper < 1e-20 < 1.0 - survival_down
```

A separate high-precision `mpmath` plus `numpy.float32` model examined 78 combinations of scales `{0.25, 0.5, 1, 2, 4, 8}` and integer margins `{0, 1, 2, 4, 8, 10, 14, 15, 16, 20, 30, 40, 80}`. The modeled `f32`-padded tail bound exceeded the `mpmath` continuous-Gaussian survival probability in all 78 examples, including extreme tails. This model calls Python's `math.erfc`, **not** Rust's `statrs::erfc`, and cannot certify the Rust implementation.

A second independent resolution limit occurs in the Gaussian single-key helper: after `f32::inf_cast(erfc(t))`, `next_up` introduces a positive subnormal floor. For example `s = 1, m = 15` yields a modeled single-key upper bound `1.401298464324817e-45` even though the continuous tail is approximately `3.67096619931e-51`. The **much larger `2^-53` joint-delta floor** dominates whenever `L0 = 1`.

**Executed:** Python directed-rounding witness and 78-case numerical model, plus source and unit-test inspection. **Not executed:** Compiled OpenDP/Rust test or direct evaluation of `statrs::erfc`. The precise Gaussian helper output in Rust remains to be checked; the joint-delta rounding mechanism is source-supported independently of the helper's specific result provided `0 < p < 2^-53`.

## Findings

**[Candidate #3](https://github.com/opendp/opendp-audit/issues/3) — low-severity numerical privacy-accounting tightness defect**, present in both Gaussian and Laplace threshold maps at the reviewed upstream commit. No privacy bound underestimate was found. The old threshold-inclusivity issue [#2922](https://github.com/opendp/opendp/issues/2922), fixed by merged [PR #3058](https://github.com/opendp/opendp/pull/3058), is unrelated. Searches of upstream/audit issues and open/merged PRs found no equivalent fix.

A potential remedy is to additionally compute a directed-upward union bound `min(1, L0 * p)` and return the **minimum of the two conservative bounds**. This avoids cancellation at tiny `p` and does not require independence for the union branch. This is a design proposal, not a tested upstream patch.

## Unresolved questions

- Execute the Gaussian witness against compiled upstream Rust and assert that the current returned delta is `2^-53`; test the Laplace counterpart.
- Add regression inputs for `p` just below/above `2^-53`, `L0=1`, `L0=2`, and `L0=u32::MAX`.
- Verify directed-upward computation of the alternate union bound and ensure all branches preserve the privacy upper-bound invariant.
- Independently validate the `statrs::erfc` approximation and the full Gaussian/Laplace sampling and proof assumptions.
