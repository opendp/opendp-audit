---
schema_version: 1
source: rust/src/measurements/noise/nature/float/mod.rs
updated: 2026-11-22
---

# `rust/src/measurements/noise/nature/float/mod.rs`

## Scope and assumptions

- **Scope:** The non-deprecated Gaussian `FloatExpFamily<2>` pipeline, particularly `make_float_to_bigint`, its L2 stability map, and `then_deintegerize_vec`. The same conversion also supports `P=1`, but this review establishes claims for `P=2` only. Discrete-Gaussian distributional correctness, numerical entropy errors, and threshold mechanisms are out of scope.
- **Invariant:** On equal-length finite `f32` or `f64` vectors of known size `n`, quantization at grid `h=2^k` must obey `||q_k(x)-q_k(y)||_2 <= (||x-y||_2 + sqrt(n)(h-g))/h`, where `g=2^k_min` is the minimum input lattice spacing; `k >= k_min`. When `k=k_min` the allowance is zero, even for an unsized domain. The transformed integer vector retains its input length.
- **Assumptions:** Only non-NaN finite inputs, valid metric distances, and successful allocation, exact rational conversion, and atom cloning; upstream rounding functions and `InfSqrt`/ `InfCast` satisfy their specified contracts. Native Rust was not executed.
- **Reviewed revision:** `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`, [floating-point path](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/float/mod.rs), [rounding helpers](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/float/utilities/mod.rs), [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/float/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::noise::nature::float::make_float_to_bigint` | privacy/l2-rounding-stability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file investigation](../../../../../../../investigations/gaussian-float-rounding-sensitivity.md) and [executed model](../../../../../../../tools/tests/test_float_gaussian_rounding_model.py) |
| `measurements::noise::nature::float::FloatExpFamily<2>::make_noise` | privacy/discrete-gaussian-composition | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Pipeline analysis](#pipeline-analysis) |
| `measurements::noise::nature::float::then_deintegerize_vec` | correctness/deterministic-output-conversion | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Pipeline analysis](#pipeline-analysis) |

## Analysis

### Pipeline analysis

The float mechanism builds `ZExpFamily<2>` with exact-rational scale `scale*2^(-k)`, builds `make_float_to_bigint`, invokes the discrete-Gaussian measurement on its `IBig` output, and applies `then_deintegerize_vec(k)`. Converting a grid index back via `TO::from_rational(index*2^k)` is deterministic postprocessing and therefore cannot increase privacy divergence, irrespective of final float rounding or overflow to an infinity.

The transformation rejects NaN-permitting domains. On the stated **finite-input** subset it converts each input float to a rational without loss, then computes the nearest index on the `2^k` grid with ties toward **positive infinity**. It preserves vector length. The stability map converts `d_in` exactly to a nonnegative rational, adds `get_rounding_distance<T,2>(k, size)`, and multiplies by `2^(-k)`. Negative or nonfinite `d_in` values fail instead of silently producing an optimistic bound.

If `k=k_min`, the conversion is exact for all finite `T` values and the rounding allowance is zero. Otherwise `get_rounding_distance` requires `size=Some(n)`, since an unbounded number of coordinates could each incur an additional error; an unsized input domain is rejected. For finite inputs, each coordinate's possible rounding-induced separation increase is bounded by `2^k-2^k_min`, giving the vector allowance `sqrt(n)*(2^k-2^k_min)` by the L2 triangle inequality. `f64::inf_cast(n)?.inf_sqrt()?` is intended to round this multiplier upward. The full privacy claim relies on the independently audited discrete Gaussian sampler and the directed-rounding contracts.

**Executed independent evidence:** The [Python small-lattice model](../../../../../../../tools/tests/test_float_gaussian_rounding_model.py) passed **2,461,004** input-pair L2-bound comparisons for dimensions 1 through 3 across grid multipliers 1, 2, 4, and 8; an additional 729 dyadic formula comparisons and six signed tie cases passed. The model is not compiled OpenDP, so cross-file privacy status remains **Partial**.

The source and upstream tests also contain a minor documentation inconsistency: the `get_rounding_distance` comment describes ties as rounding down, while `find_nearest_multiple_of_2k` and its Rust tests use ties toward positive infinity. The conservative magnitude bound applies under either tie convention; this mismatch is not a demonstrated privacy defect.

## Next checks

- Execute native Rust float Gaussian tests for `f32` and `f64`, including subnormals, non-finite values excluded from the domain, extreme `k`, and multiple vector sizes.
- Independently verify `InfSqrt`, `InfCast`, `CastInternalRational`, and the discrete-Gaussian sampler contracts in production configurations.
- Correct the rounding helper's documentation to say ties toward positive infinity, or clarify that the bound is tie-rule independent.
