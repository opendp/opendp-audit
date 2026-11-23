---
schema_version: 1
source: rust/src/measurements/noise/nature/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/noise/nature/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated `Nature` numeric-carrier dispatch and `new_distribution` granularity defaults/rejections across `IBig`, primitive integers, and `f32`/`f64`. The scope is the top-level distribution-type mapping and later validation; not arbitrary-precision sampler correctness, IEEE conversion proof, or extreme-parameter resource bounds.
- **Invariant:** The Laplace and Gaussian mechanism distribution family is selected by constant norm `P=1` and `P=2` while the carrier `Nature` changes only its representation. For nonfloating carriers, `k` is exactly zero; for float carriers, omitted `k` selects the minimum representable lattice granularity. Bad `scale` and `k` must not yield a measurement carrying a false privacy promise.
- **Assumptions:** `MakeNoise` implementations for each `RV<P>` are used through typed distribution constructors; as dictated by their trait contracts, they must reject invalid parameters. Results below are based on pinned source inspection, not compiled native tests or an exhaustive classification of accepted floats.
- **Sources:** [nature dispatcher](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/noise/nature/mod.rs), [float utilities](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/noise/nature/float/utilities/mod.rs), [float mechanism](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/noise/nature/float/mod.rs), [integer mechanism](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/noise/nature/integer/mod.rs), [Laplace](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/noise/distribution/laplace/mod.rs), [Gaussian](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/noise/distribution/gaussian/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `Nature for IBig::new_distribution` | correctness/integer-granularity-constraint | Audited | `a010591f55b1713c926f8e355091471634480307` | [Carrier-specific dispatch](#analysis) |
| `Nature for primitive integers::new_distribution` | correctness/integer-granularity-constraint | Audited | `a010591f55b1713c926f8e355091471634480307` | [Carrier-specific dispatch](#analysis) |
| `Nature for f32/f64::new_distribution` | correctness/float-default-granularity | Audited | `a010591f55b1713c926f8e355091471634480307` | [Carrier-specific dispatch](#analysis) |
| `Nature::new_distribution` | privacy/invalid-scale-delegated-validation | Partial | `a010591f55b1713c926f8e355091471634480307` | [Effective validation](#effective-validation) |

## Analysis

For `IBig`, `Nature::RV<P>` is `ZExpFamily<P>` and `new_distribution` checks `k.unwrap_or(0) == 0`, then tries an exact rational conversion from the `f64` scale. It consequently rejects nonzero `k` and nonfinite scale, though negative finite scale is not rejected until the specialized privacy-map constructor. For primitive integral `T` (`i8,i16,i32,i64,i128,isize,u8,u16,u32,u64,u128,usize`), `RV<P>` is `IntExpFamily<P>`, and an identical nonzero-`k` guard applies. Integers pass `scale` to `integerize_scale(self.scale,0)` when creating the underlying `ZExpFamily<P>`.

For `f32` and `f64`, `Nature::RV<P>` is `FloatExpFamily<P>`, and the granularity defaults to `get_min_k::<T>`. The helper returns the smallest subnormal spacing exponent, **-149** for `f32` and **-1074** for `f64`. The supplied `k` is passed as-is and later checked by `get_rounding_distance::<T,P>`: `k < get_min_k::<T>` is rejected. `integerize_scale(scale,k)` rejects nonfinite scales and `k=i32::MIN`; these validation paths prevent a measurement from silently accepting a lattice finer than that of its declared floating-point carrier.

### Effective validation

`Nature::new_distribution` does **not** promise to fully validate every scale or granularity itself. It returns a carrier-appropriate distribution, whose `MakeNoise` implementation builds a `ZExpFamily<P>` and invokes the specialized `noise_privacy_map`. Both `P=1` and `P=2` privacy maps reject negative scales; zero scale with nonzero sensitivity has infinite (not zero) reported loss. Consequently a negative scale accepted temporarily by `Nature::new_distribution` does not become a valid `Measurement` through the supported `make_noise` path.

**Executed:** Pinned-source static assertions checked `IBig` and primitive-integer nonzero-`k` guards, float default calculation and rejection path, integerization and both privacy-map negative/zero-scale guards. Together with the [companion distribution report](../distribution/mod.rs.md), **17 assertions passed**. The independent arithmetic for `get_min_k::<f32/f64>` follows the publicly defined exponent bias and mantissa bit count.

**Not executed:** OpenDP native tests, actual random samples, feature-gated FFI entrypoints, unbounded resource behavior under extreme `k`, or formal proofs. The existing [float test](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/noise/nature/float/test.rs) deliberately accepts `k=i32::MAX`; its large-integer intermediate allocation should be investigated separately as an availability concern before declaring a vulnerability. This file review does **not** establish a memory-exhaustion exploit, and does not file an issue on that basis.

## Findings

**No independently supported privacy bypass in numeric-nature dispatch** at pinned upstream `a010591f55b1713c926f8e355091471634480307`. Distinguish constructor-level parameter acceptance, ultimate measurement validity, and sampler behavior; the latter two remain partially reviewed. No new defect issue was opened. [Audit task #152](https://github.com/opendp/opendp-audit/issues/152).

## Next checks

Execute native `make_noise` and `make_noise_threshold` (which shares `Nature`) with `k=None,Some(0)` and invalid `k`, negative, zero, NaN and infinite scales for all supported carrier categories. Add instrumented size/time limits for extreme positive `k` before deciding whether availability remediation is warranted.
