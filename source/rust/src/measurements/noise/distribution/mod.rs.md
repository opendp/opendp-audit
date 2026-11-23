---
schema_version: 1
source: rust/src/measurements/noise/distribution/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/noise/distribution/mod.rs`

## Scope and assumptions

- **Audit scope:** Non-deprecated generic `make_noise`, its `NoiseMeasure` dispatch implementation for `MaxDivergence` and `ZeroConcentratedDivergence`, and the scalar/vector `NoiseDomain` trait implementations. Review only the distribution-selection and parameter-forwarding boundary; do not re-prove sampler probability laws or native FFI bindings.
- **Invariants:** Requested pure DP must dispatch to Laplace/P=1 and zCDP to Gaussian/P=2; the passed `input_domain`, `input_metric`, `scale`, and `k` must reach a mechanism whose privacy map validates parameters before construction. Unsupported carrier/metric combinations should be excluded by trait bounds, not silently accepted.
- **Assumptions:** Current supported `NoiseMeasure` implementations for `MaxDivergence` and `ZeroConcentratedDivergence` are unit-like, and their corresponding `NoisePrivacyMap` implementations are correct when invoked with valid parameters. This source-level review does not establish sampler correctness, FFI safety, or numerical conservatism of rounded releases.
- **Pinned sources:** [generic router](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/noise/distribution/mod.rs), [Laplace](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/noise/distribution/laplace/mod.rs), [Gaussian](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/noise/distribution/gaussian/mod.rs), [nature dispatch](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/noise/nature/mod.rs), [bigint mechanism](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/noise/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_noise` | privacy/selected-measure-distribution | Audited | `a010591f55b1713c926f8e355091471634480307` | [Type-directed distribution routing](#analysis) |
| `make_noise` | privacy/parameter-validation-propagation | Partial | `a010591f55b1713c926f8e355091471634480307` | [Downstream validation trace](#downstream-validation-trace); native execution/sampler not exercised |
| `NoiseMeasure for MaxDivergence::new_distribution` | privacy/laplace-selection | Audited | `a010591f55b1713c926f8e355091471634480307` | [Type-directed distribution routing](#analysis) |
| `NoiseMeasure for ZeroConcentratedDivergence::new_distribution` | privacy/gaussian-selection | Audited | `a010591f55b1713c926f8e355091471634480307` | [Type-directed distribution routing](#analysis) |
| `NoiseDomain for AtomDomain<T>` | correctness/scalar-noise-carrier | Audited | `a010591f55b1713c926f8e355091471634480307` | [Carrier admissibility](#carrier-admissibility) |
| `NoiseDomain for VectorDomain<AtomDomain<T>>` | correctness/vector-noise-carrier | Audited | `a010591f55b1713c926f8e355091471634480307` | [Carrier admissibility](#carrier-admissibility) |

## Analysis

The generic `make_noise` calls `output_measure.new_distribution(scale, k).make_noise((input_domain, input_metric))`, retaining the caller's domain and metric. It does not bypass or modify a privacy map. For `MaxDivergence`, `NoiseMeasure::Distribution` is `DiscreteLaplace`; for `ZeroConcentratedDivergence`, it is `DiscreteGaussian`. Those constructors select `DI::Atom::new_distribution::<1>` and `::<2>` respectively, so the choice of distribution family follows the typed privacy measure rather than the value of a user-provided tag.

### Downstream validation trace

`Nature` dispatch then selects rational-scaled `ZExpFamily<P>` for arbitrary-precision integers, `IntExpFamily<P>` for native integers, and `FloatExpFamily<P>` for floats; full details are in [the companion nature audit](../nature/mod.rs.md).

The downstream `MakeNoise` implementations convert to `ZExpFamily<P>` and invoke `noise_privacy_map` **before** calling `Measurement::new`. Both `ZExpFamily<1>`/Laplace and `ZExpFamily<2>`/Gaussian privacy-map constructors reject negative rational scales. For positive input sensitivity and a scale of zero, each returns an infinite privacy-loss bound rather than silently promising zero privacy loss; for zero input sensitivity each returns zero. The regular Laplace and Gaussian maps compute (respectively) `d / scale` and `(d / scale)^2 / 2` in big rational arithmetic before conservative conversion to `f64`. No parameter-validation bypass was found at this dispatch boundary.

**Limitation:** A valid privacy map for a custom externally implemented `NoiseMeasure` is the implementor's contract; the router does not prove it. Native sampler correctness, low-level floating-point integerization, and downstream noise failures are outside the scoped review. In particular, support for extreme `k` values is delegated to `Nature` and its rounding helper; this review does not establish availability or bounded memory usage for very large public `k`.

### Carrier admissibility

`NoiseDomain` is implemented on `AtomDomain<T>` and `VectorDomain<AtomDomain<T>>` for `T: CheckAtom`. The generic constructor additionally requires `MO::Distribution: MakeNoise<DI,MI,MO>` and `(DI, MI): MetricSpace`, so the actual supported metric and noise nature are constrained by the relevant concrete implementation. There is no generic dynamic fallback that silently treats unsupported carrier shapes as private.

**Executed checks:** Seventeen source-text assertions on pinned GitHub source checked distribution dispatch, parameter forwarding, negative/zero scale guards, granularity branches, and bigint privacy-map construction order; all passed. **Not executed:** A compiled OpenDP Rust or FFI measurement; the upstream sampler distributions and their proofs were inspected at entrypoints, not mechanically verified. [Audit task #152](https://github.com/opendp/opendp-audit/issues/152) contains scope and validation status.

## Findings

**No independent defect established** in the generic noise router or its two supported privacy-measure bindings. The local routing contracts are audited, but overall end-to-end privacy accounting and native sampler behavior remain **Partial**.

## Next checks

Run compiled integration tests on the unified `make_noise` entrypoint with scalar/vector `f32`, `f64`, native integers, positive and negative scales, and `k` values around supported granularity limits. Specifically check extreme public `k` values for reasonable resource limits before treating them as safe to accept from untrusted callers. See [nature dispatch report](../nature/mod.rs.md).
