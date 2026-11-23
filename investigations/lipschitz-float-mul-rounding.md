---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Floating-point multiplier stability and subnormal ULP accounting

## Invariant and threat model

The non-deprecated `make_lipschitz_float_mul` computes `f(x)=saturating_mul(clamp(x,lower,upper),constant)` and advertises `stability_map(d) >= |f(x)-f(y)|` whenever `d >= |x-y|`. Incorrect rounding-error accounting could underestimate sensitivity for closely spaced floating-point inputs and invalidate downstream DP calibration. This is a bounded arithmetic review, not an audit of the full downstream measurement or native floating-point backend.

## Affected symbols and source audits

- [Primary source report](../source/rust/src/transformations/lipschitz_mul/mod.rs.md); [pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/lipschitz_mul/mod.rs#L1).
- [`SaturatingMul` and `InfPowI`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/arithmetic/mod.rs#L1); [`FloatBits::raw_exponent` and `total_clamp`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/operations/mod.rs#L1).
- [`Transformation::new`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs#L1); [upstream test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/lipschitz_mul/test.rs#L1).

## Reasoning and evidence

For correctly ordered finite bounds, `M=max(|lower|, upper)` upper-bounds `|clamp(x)|`. If `w` is a conservative upper floating-point bound on `M*|c|`, each nearest-float multiplication incurs error at most half a ULP at the greatest magnitude, and the difference between two rounded outputs incurs at most one ULP total. Clamping and saturation are nonexpansive under absolute distance. The code evaluates the map as `InfAdd(InfMul(|c|,d), output_ulp)`, so ideal real-arithmetic bound comparison is justified only under the outward-rounding contracts of these traits.

### Subnormal-specific check

For IEEE `f32`, with a zero raw exponent and a 23-bit mantissa, the integer power expression in the code has exponent `0-127-23=-150`: `2^-150` is **not** representable as a positive `f32`. It must be rounded **up** to the minimum subnormal `2^-149` if `InfPowI` succeeds, providing a full ULP for subnormal outputs. Analogously, for `f64`, the expression is `2^-1075` and the least positive representable `f64` is `2^-1074`. A model that assumes exact storage of the half-minimum-subnormal value is unsound and yields false-positive inequality violations.

### Independent executed numerical models

The tests below used locally executed **Python**, not OpenDP Rust:

1. `f32`: `random.Random(1024)` generated 180,000 candidate combinations of random 32-bit-pattern `lower`, `upper`, and `constant`. Finite candidates were ordered and those with unrepresentable ideal maximum product magnitude excluded. Input points were endpoints or random points in their clamp interval, rounded to `numpy.float32`. Actual outputs were nearest-`f32` saturated products. An exact rational bound `|x-y||c|+ULP` was checked, with `ULP` rounded upward at the subnormal boundary. **140,291 comparisons passed; no modeled bound violation.**
2. `f64`: `random.Random(20261123)` generated 18,000 candidate combinations of random 64-bit-pattern parameters. On representable finite candidates, the model used endpoint inputs, Python nearest-`f64` multiplication with saturation, and exact `fractions.Fraction` arithmetic for the ideal formula. **14,280 comparisons passed; no modeled bound violation.** Of these, 722 had a subnormal upward maximum-product magnitude.

These independently executed comparisons use actual IEEE-style arithmetic, but not OpenDP's directed arithmetic implementation; cases excluded due to nonfinite/unrepresentable magnitudes are **not** evidence that OpenDP itself returned errors. They cannot establish universally valid stability or certify all `d` inputs.

### Separate constructor-bound-order finding

The constructor never directly checks `lower <= upper`. For `constant=1.0`, `bounds=(2.0,1.0)`, its magnitude and ULP calculations are finite, so the construction proceeds, while `total_clamp(2.0,1.0)` produces a deterministic `FailedFunction` at every invocation. [`Transformation::new`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs#L1) checks the metric spaces but not captured parameters. This is a low-severity early-validation defect, recorded in [audit issue #32](https://github.com/opendp/opendp-audit/issues/32) by another parallel audit agent. No duplicate issue was opened by this review.

## Findings

**Privacy/stability property: Partial.** No underestimation was found in 154,571 independently modeled finite f32/f64 input pairs, but the native `InfPowI`/`InfMul` execution paths, exceptional parameter handling, and general proof obligations remain unverified. **Constructor validation:** source-level reversed-bounds defect, separately tracked in [issue #32](https://github.com/opendp/opendp-audit/issues/32). No new privacy violation established.

## Unresolved questions

- Check native `InfPowI` upward rounding for zero/subnormal exponent paths and finite `InfMul` error handling.
- Run native randomized property tests and an inverted-bounds constructor regression.
- Verify full-precision casting and domain membership for signed zero and nonfinite public parameters.
