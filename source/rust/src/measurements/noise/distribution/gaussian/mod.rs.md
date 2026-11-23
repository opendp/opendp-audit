---
schema_version: 1
source: rust/src/measurements/noise/distribution/gaussian/mod.rs
updated: 2026-11-22
---

# `rust/src/measurements/noise/distribution/gaussian/mod.rs`

## Scope and assumptions

Reviewed the **non-deprecated** `make_gaussian` delegation and `NoisePrivacyMap<L2Distance<RBig>, ZeroConcentratedDivergence> for ZExpFamily<2>`, as used by **scalar integer** inputs. Floating-point input discretization and threshold mechanisms are separate scopes.

- **Invariant:** When the integral scalar input has a valid `AbsoluteDistance<QI>` metric and finite Gaussian scale, the successful output has the original integer type. The zCDP map for a valid positive rational scale `σ` and nonnegative sensitivity `d` is a conservative upward representation of `d²/(2σ²)`. It returns zero if `d=0` and infinity if `d>0` and `σ=0`; negative sensitivities and negative scales must fail.
- **Assumptions:** `sample_discrete_gaussian` meets its specified law and independent sampling/error contract, `RBig` exact rational arithmetic is sound, `f64::inf_cast` rounds conservatively, conversions and `SaturatingCast` obey documented contracts. The finite distribution model is not a Rust execution.
- **Pinned upstream:** `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`, [implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/gaussian/mod.rs), [proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/gaussian/NoisePrivacyMap_for_ZExpFamily2.tex), [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/gaussian/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::noise::distribution::gaussian::make_gaussian` | correctness/integer-scalar-delegation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file pipeline](../../../../../../../investigations/gaussian-integer-scalar-privacy.md) |
| `measurements::noise::distribution::gaussian::NoisePrivacyMap<ZExpFamily<2>>::noise_privacy_map` | privacy/zcdp-bound | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Analytic bound and finite checks](../../../../../../../investigations/gaussian-integer-scalar-privacy.md) |
| `measurements::noise::distribution::gaussian::NoisePrivacyMap<ZExpFamily<2>>::noise_privacy_map` | correctness/zero-negative-boundaries | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Boundary analysis](#boundary-analysis) |

## Analysis

### Integer-scalar delegation

`make_gaussian` delegates to `DiscreteGaussian { scale, k }.make_noise`. For integer atom types, `Nature::new_distribution` rejects nonzero `k` and chooses `IntExpFamily<2>`; scalar `IntExpFamily` delegates via `make_vec` to the vector implementation and then extracts element zero. The input domain of that intermediate vector is **sized to one**. The integer vector path converts exact atoms into `IBig`, obtains exact rational sensitivity through `RBig::try_from`, adds independent discrete Gaussian noise, and saturating-casts back to the scalar type. See the [cross-file investigation](../../../../../../../investigations/gaussian-integer-scalar-privacy.md) for precise prerequisites and limitations.

### Boundary analysis

The `NoisePrivacyMap` implementation rejects a negative rational `scale` at map construction. It rejects a negative `d_in` at map evaluation. It handles `d_in=0` before scale-zero handling and returns `0.0`; if `d_in>0` and `scale=0`, it returns `+∞`. Otherwise it evaluates `f64::inf_cast((d_in/scale)^2 / 2)`; this is the standard conservative zCDP upper bound for the independent discrete Gaussian, assuming the source's `f64::inf_cast` contract.

These branches agree with the upstream `test_make_gaussian_map` and `test_make_noise_zexpfamily2_zero_scale` regression assertions (inspected, not run). The zero-sensitivity branch does not imply that a zero-noise release is safe at a positive sensitivity.

### Independent evidence

A [reproducible standard-library Python reference test](../../../../../../../tools/tests/test_gaussian_scalar_privacy_model.py) passed **300 finite-support discrete-Gaussian Rényi comparisons**, plus scalar-map boundaries and deterministic integer-saturation checks. The tests numerically approximate infinite-support distributions on `[-80, 80]`, not the compiled OpenDP sampler. They support the modeled bound but do **not** establish its implementation or all Rényi orders. No new defect was identified in the stated scope.

## Next checks

- Run the native upstream Rust Gaussian tests and verify actual sampler distributions, error paths, and conservative `f64::inf_cast` behavior.
- Audit the `FloatExpFamily` discretization and rounding-sensitivity adjustment separately.
- Review unusual metric-distance types, extremal scales, and vector behavior; the present assessment covers scalar integer inputs only.
