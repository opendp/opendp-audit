---
schema_version: 1
source: rust/src/measurements/noise_threshold/nature/integer/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/noise_threshold/nature/integer/mod.rs`

## Scope and assumptions

- **Scope:** The non-deprecated integer map threshold adapters for discrete Laplace and Gaussian mechanisms, specifically `MakeNoiseThreshold for IntExpFamily<P>`, `make_int_to_bigint_threshold`, and `then_saturating_cast_hashmap`. The property is the strict threshold condition on **returned native integer values** rather than intermediate `IBig` values.
- **Invariant:** For a nonnegative public threshold `t`, every released count is strictly greater than `t`; for a negative threshold, every released count is strictly smaller than `t`. These conditions are documented on the public Laplace and Gaussian threshold constructors.
- **Assumptions:** A positive finite noise scale permits noise increments `+1` and `-1` with positive probability; the `ZExpFamily<P>` sampler obeys its documented additive-noise law. The stage ordering follows the pinned source and the integer saturated-cast implementations. The full OpenDP Rust library was not run.
- **Pinned code:** [Integer adapter](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/nature/integer/mod.rs), [core integer threshold filter](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/mod.rs), [`SaturatingCast<IBig>`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/cast/mod.rs), [Laplace threshold](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/laplace/mod.rs), [Gaussian threshold](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/gaussian/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::noise_threshold::nature::integer::MakeNoiseThreshold_for_IntExpFamily` | correctness/returned-strict-threshold | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Boundary counterexamples](../../../../../../../investigations/integer-threshold-postsaturation.md), [issue #58](https://github.com/opendp/opendp-audit/issues/58) |
| `measurements::noise_threshold::nature::integer::then_saturating_cast_hashmap` | correctness/boundary-saturation | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Source and standalone models](../../../../../../../investigations/integer-threshold-postsaturation.md) |
| `measurements::noise_threshold::nature::integer::make_int_to_bigint_threshold` | stability/integer-conversion | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Conversion source trace](#analysis); full stability proof not audited |

## Analysis

The integer adapter composes the native-to-`IBig` transformation `make_int_to_bigint_threshold`, the core noisy integer threshold mechanism, and `then_saturating_cast_hashmap`. In the core, the strict predicate compares the **noisy `IBig` value** with the `IBig` threshold in the signed direction. Only afterward does the adapter map retained counts back into the original integer type `TV`. `SaturatingCast<IBig>` maps out-of-range positive values to `TV::MAX` and out-of-range negative values to `TV::MIN`.

This breaks the returned-value invariant at both boundaries:

- **Unsigned upper boundary:** public threshold `255u8`, nonzero input `255u8`, positive finite scale (e.g. `1`), and noise outcome `Z=+1`. The core retains `256 > 255`, but `then_saturating_cast_hashmap` returns `255u8`, **equal** to the public threshold.
- **Signed lower boundary:** public threshold `-128i8`, nonzero input `-128i8`, positive finite scale, and noise outcome `Z=-1`. The core retains `-129 < -128`, but saturation returns `-128i8`, also equal to the threshold.

Both events have positive probability under either finite-scale discrete Laplace or Gaussian noise. The witnesses require no private input outside its specified native integer range, and the adapter can be constructed for both signed and unsigned `TV` satisfying the existing trait bounds. This is a **confirmed output-contract defect**, not a new privacy-accounting counterexample: the cast is deterministic postprocessing.

A [Python exact-integer model](../../../../../../../tools/tests/test_integer_threshold_postsaturation.py) checks analogous positive/negative witnesses at integer widths `8,16,32,64,128` with independent controls for in-range values and zero/noise suppression. A [standalone compiled Rust model](../../../../../../../tools/tests/integer_threshold_postsaturation.rs) reproduces native integer saturation at the endpoints without linking the OpenDP/Dashu library. The full native OpenDP threshold constructor and sampler were **not** executed.

### Relationship to float thresholds

The earlier [float threshold audit](../float/mod.rs.md) and [issue #44](https://github.com/opendp/opendp-audit/issues/44) establish the same visible output-contract mismatch for **nearest-float rounding** on a fine grid. The integer variant is in a separate conversion path, with a different numerical condition and reproduction; it is tracked by [issue #58](https://github.com/opendp/opendp-audit/issues/58). Both can be addressed with a final strict comparison in the returned type.

## Next checks

- Compile and run a **native OpenDP integration test** that exercises `make_laplace_threshold` and `make_gaussian_threshold` with threshold `u8::MAX` and `i8::MIN`, ideally controlling the underlying `+1`/`-1` noise draw.
- Decide whether the strict threshold contract applies to the returned native-type value; if so, enforce a final strict comparison after the saturating cast. Such additional deterministic filtering is privacy-preserving postprocessing.
- Verify whether the proposed fix changes utility at type boundaries and whether any extreme-scale errors or sampling failures occur; these properties were not audited here.
