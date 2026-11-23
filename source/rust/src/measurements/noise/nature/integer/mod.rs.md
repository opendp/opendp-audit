---
schema_version: 1
source: rust/src/measurements/noise/nature/integer/mod.rs
updated: 2026-11-22
---

# `rust/src/measurements/noise/nature/integer/mod.rs`

## Scope and assumptions

This review follows **integer scalar** Gaussian releases through `IntExpFamily<2>`. It examines exact input conversion, the singleton scalar-to-vector delegation, and the final deterministic saturation. It does not cover all possible integer input types or floating-point input paths in compiled Rust.

- **Invariant:** For valid scalar integer inputs, conversion to `IBig` is exact, a singleton vector retains length one through successful noise addition and type conversion, and the scalar output returns a value of the original integer type. The scalar privacy loss is bounded by the delegated discrete Gaussian `L2Distance<RBig>` mechanism.
- **Dependencies:** [Integer implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/integer/mod.rs), [singleton vector helper](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/scalar_to_vector/mod.rs), [Gaussian privacy map](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/gaussian/mod.rs), [saturation cast](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/cast/mod.rs). Reviewed upstream SHA: `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`.

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::noise::nature::integer::make_int_to_bigint` | correctness/exact-integer-conversion | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Conversion analysis](#conversion-analysis) |
| `measurements::noise::nature::integer::IntExpFamily<2>::make_noise_scalar` | privacy/singleton-delegation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file investigation](../../../../../../../investigations/gaussian-integer-scalar-privacy.md) |
| `measurements::noise::nature::integer::then_saturating_cast` | correctness/saturating-output | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Saturation analysis](#saturation-analysis) |

## Analysis

### Conversion analysis

`make_int_to_bigint` maps each integer `T` to `IBig::from(T)` without numerical truncation; its domain is `VectorDomain<AtomDomain<IBig>>` with the original length descriptor. The stability map uses `RBig::try_from(d_in)` rather than a floating-point conversion. Thus finite representable distances of the input `QI` type are represented exactly as rationals, or conversion fails (for example, nonfinite floating-point distances). No sensitivity-reducing cast was found.

For a scalar, `make_vec` produces a one-element vector with a cloned atom, `LpDistance<2, QI>`, and identity stability map. Its output has fixed length one. The vector Gaussian chain preserves vector length by sampling once per element, so `then_index_or_default(0)` returns the actual first atom on every successful valid invocation rather than taking its default branch. These statements depend on the constructors' domain/mapping contracts; no Rust execution was performed.

### Saturation analysis

The output `then_saturating_cast` calls `T::saturating_cast` on each noisy `IBig` value. Its integer implementation preserves in-range values and clamps out-of-range values to `T::MIN` or `T::MAX`; it has no branching on unperturbed input. Hence it is deterministic postprocessing and cannot increase privacy divergence. The independent model verified 81 pairwise nonexpansiveness checks for an i8-like signed range; it does not execute the Rust cast. The upstream `test_then_saturating_cast` covers out-of-range behavior (inspected, not run).

**Conclusion:** No defect identified in the examined exact conversion or deterministic saturation logic. A [cross-file investigation](../../../../../../../investigations/gaussian-integer-scalar-privacy.md) documents the full Gaussian pipeline and untested assumptions.

## Next checks

- Execute compiled Rust scalar integer tests for signed and unsigned types, including extrema and zero scale.
- Revisit potential allocation, entropy, or exceptional type-conversion failures separately.
- Audit floating-point integerization and its rounding-distance stability bound as an independent property.
