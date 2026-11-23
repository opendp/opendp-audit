---
schema_version: 1
source: rust/src/traits/samplers/geometric/mod.rs
updated: 2026-11-22
---

# `rust/src/traits/samplers/geometric/mod.rs`

## Scope and assumptions

- **Audit scope:** The positive-scale trial-count construction and propagation of checked integer overflow in `sample_discrete_laplace_linear<T, P>`, plus the finite-interval two-sided censored geometric output law, conditional on an ideal Bernoulli source.
- **Invariants:** A nondegenerate interval width that fits `usize` should not be rejected solely because a transient width calculation is made in the smaller signed input type. For successful bounded draws, the output distribution should match integer discrete Laplace noise followed by clamping to `[lower, upper]`.
- **Assumptions:** `T` has checked `AlertingSub` and is one of the supported integer types; `P` is a valid float; `sample_bernoulli_float(p, ...)` and `sample_standard_bernoulli` satisfy their documented distribution laws conditional on sufficient entropy. Exact-rational tests model their ideal draws, not the actual Rust implementation.
- **Pinned source:** [Geometric sampler](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/geometric/mod.rs), [checked subtraction](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/arithmetic/mod.rs), [sampler tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/geometric/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `traits::samplers::geometric::sample_discrete_laplace_linear` | correctness/signed-interval-width | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Confirmed overflow investigation](../../../../../../investigations/bounded-geometric-signed-width-overflow.md), [audit issue #4](https://github.com/opendp/opendp-audit/issues/4) |
| `traits::samplers::geometric::sample_discrete_laplace_linear` | distribution/bounded-clamped-pmf | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [504 exact-rational model comparisons](../../../../../../investigations/bounded-geometric-signed-width-overflow.md) |
| `traits::samplers::geometric::sample_geometric_linear` | correctness/trial-count-convention | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Finite-trial distribution model](../../../../../../investigations/bounded-geometric-signed-width-overflow.md) |

## Analysis

### Confirmed signed-integer width overflow

The positive-scale, non-singleton branch contains:

```rust
let trials: Option<usize> = Some(usize::exact_int_cast(
    upper.alerting_sub(&lower)?.alerting_sub(&T::one())?,
)?);
```

For `T = i8`, `lower = -128` and `upper = 0`, the intended trial count is `0 - (-128) - 1 = 127`, which fits `i8` and `usize`. However the *first* checked `i8` subtraction attempts to represent `128` and fails with `Overflow`. Therefore every positive-scale call on that interval fails before reaching the random sampler. The same applies to the full `i8` interval `(-128, 127)` and to other valid signed intervals with width greater than the type's positive maximum but not greater than `usize::MAX`. In contrast, `(-128, -1)` and `u8` bounds `(0, 255)` have representable first subtractions.

The early scale-zero and equal-bound branches skip this calculation. This is **not** a privacy underestimation: the observed defect is an unnecessarily unusable supported interval. The [related measurement constructor audit](../../../../../../source/rust/src/measurements/noise/distribution/geometric/mod.rs.md) traces the error through the public bounded API.

The [standalone Rust checked-subtraction regression](../../../../../../tools/tests/geometric_trial_width.rs) compiled and ran in [audit CI #45098886613](https://github.com/opendp/opendp-audit/actions/runs/45098886613): **4 tests passed**, verifying the failing and working interval cases in native Rust. This harness models the arithmetic primitives without importing the OpenDP library; a native OpenDP invocation test is still outstanding.

### Distributional cross-check within small widths

The finite geometric sampler runs `trials + 1` Bernoulli attempts. On a width-`w` interval, the intended number is `w`, so the censored unilateral step count has probabilities `p (1-p)^r` for each `0 <= r < w` and tail probability `(1-p)^w` at step `w`. The outer sampler chooses a fair sign, rejects exactly one signed-zero proposal, and clamps the output.

An independent Python 3 `fractions.Fraction` probability model enumerated both signed directions, the single rejected proposal and renormalization, and the clamped PMF. For `u8` and `i8` machine bounds, 6 small intervals per type (minimum, maximum, and interior), `p` in `{1/16,1/4,1/2,3/4,15/16,1}`, and 7 representative shifts (including out-of-bounds), it compared **504** full output PMFs to the ideal `a = 1 - p` clamped discrete Laplace law. All 504 were exactly equal as rational numbers. This tests the mathematical control-flow model; it does not execute the Rust sampler, assess timing, or prove the floating-point probability calculation for all scales. That property remains **Partial**.

## Next checks

- Add a **compiled OpenDP integration test** for bounded positive-scale `i8` with bounds `(-128,0)` and `(-128,127)`, verifying construction and the existing invocation `Overflow`; the standalone `rustc` arithmetic reproducer now passes in CI but does not exercise OpenDP. Verify the integration behavior after widening arithmetic upstream.
- Ensure any fix calculates width and `width-1` safely before converting to `usize`, while preserving overflow rejection for widths genuinely larger than `usize`.
- Separately test constant-time behavior and the actual floating-point Bernoulli implementation; the 504 exact-rational PMF comparisons are not Rust or timing tests.
