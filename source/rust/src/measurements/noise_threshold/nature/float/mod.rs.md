---
schema_version: 1
source: rust/src/measurements/noise_threshold/nature/float/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/noise_threshold/nature/float/mod.rs`

## Scope and assumptions

- **Audit scope:** Strict numeric threshold behavior after composing float-to-integer quantization, `ZExpFamily` integer noise with strict comparison, and `then_deintegerize_hashmap` nearest-float postprocessing. Applies to non-deprecated `make_laplace_threshold` and `make_gaussian_threshold` with `f32`/`f64` values, not to their privacy-delta precision or end-to-end entropy behavior.
- **Invariant:** An entry returned by either public float mechanism with nonnegative public threshold `t` has a numeric output value strictly greater than `t`, as described in the public constructors.
- **Assumptions:** The integer noise distribution has a positive probability of sampling `+1` at finite positive scale; the `CastInternalRational` float implementations round to the nearest binary floating-point value; the input map contains a nonzero value and the noise sampler returns successfully.
- **Pinned source:** [Float threshold adapter](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/nature/float/mod.rs), [integer-stage threshold filter](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/mod.rs), [nearest rational-to-float cast](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/cast/mod.rs), [Laplace threshold API](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/laplace/mod.rs), [Gaussian threshold API](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/gaussian/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::noise_threshold::nature::float::MakeNoiseThreshold_for_FloatExpFamily` | correctness/postrounded-strict-threshold | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Confirmed rounding counterexample](../../../../../../../investigations/float-threshold-postrounding.md), [audit issue #44](https://github.com/opendp/opendp-audit/issues/44) |
| `measurements::noise_threshold::nature::float::then_deintegerize_hashmap` | correctness/nearest-float-roundback | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Exact rational and standalone Rust models](../../../../../../../investigations/float-threshold-postrounding.md) |
| `measurements::noise_threshold::nature::float::make_float_to_bigint_threshold` | stability/quantization-allowance | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Quantization stage traced](#analysis); full stability proof and native integration remain outside scope |

## Analysis

### Counterexample in normal numeric ranges

The adapter converts each valid non-NaN value `x` to an integer nearest `x/2^k`, and converts the public threshold `t` to `floor(t/2^k)`. It runs the **integer** threshold mechanism, which includes an entry if its noised integer count exceeds this integer threshold. Finally, `then_deintegerize_hashmap(k)` returns `CastInternalRational::from_rational` of that integer count multiplied by `2^k`. This final step rounds to the nearest `f32` or `f64` and does **not** repeat the strict threshold check.

For `f64`, let `threshold=t=1.0`, `k=-54`, `scale=2^-54`, and input map `{key: 1.0}`. All parameters are finite, `k` exceeds the minimum supported `f64` grid exponent `-1074`, and the internal noise scale is exactly `1`. The input and threshold integerize to `2^54`. If the noise sampler returns `Z=+1` (positive probability for either discrete Laplace or Gaussian at scale one), the integer stage retains `2^54+1 > 2^54`. The *exact* rational conversion target is `1+2^-54`. The next representable binary64 after `1` is `1+2^-52`; `1+2^-54` is strictly nearer `1`, so `from_rational` returns exactly `1.0`. Thus a retained entry violates the documented returned-value condition `value > threshold`. The analogous `f32` witness is `k=-26`, `scale=2^-26`, `t=1.0`. Even `k=0`, `scale=1` and `t=2^54` reproduces the issue in `f64`.

For the integerized two-sided discrete Laplace with scale `1`, the event `Z=+1` has probability `((1-e^-1)/(1+e^-1))e^-1`, approximately `0.1700034`, rather than a zero-probability mathematical endpoint.

### Verification and scope

The standard-library [Python exact-rational regression](../../../../../../../tools/tests/test_float_threshold_postrounding.py) evaluates the quantization, strict integer comparison and nearest-float projection for 522 binary-exponent witness cases, plus fixed boundary and control cases. It passed locally before publication. The [standalone Rust regression](../../../../../../../tools/tests/float_threshold_postrounding.rs) checks native `f32`/`f64` rounding of the exact accepted integer numerator, without importing the OpenDP library. The Rust test is intended for audit CI; it is **not** an OpenDP integration test.

**Disposition:** Confirmed functional output-contract defect, tracked in [audit issue #44](https://github.com/opendp/opendp-audit/issues/44). No privacy underestimation has been established. The original integer-stage filter is correct; the returned-value contract changes because float rounding follows that filter. A final strict filter over **returned** float values would be privacy-preserving postprocessing, though its utility impact and consistency across signed threshold APIs must be considered.

## Next checks

- Add a compiled **OpenDP** integration regression for a float Laplace and Gaussian threshold measurement at the above parameters, conditioning on/injecting the `Z=+1` noise outcome if an appropriate deterministic sampler seam exists.
- Assess whether strict thresholding applies to returned native floats by contract, or revise API documentation if comparison is intentionally defined only before rounding.
- Separately validate the full `make_float_to_bigint_threshold` stability map and the native finite-scale sampler behavior; neither is established by this output-contract witness.
