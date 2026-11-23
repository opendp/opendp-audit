---
schema_version: 1
source: rust/src/measurements/make_private_expr/expr_noise/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/make_private_expr/expr_noise/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated Polars noise expression construction and distribution/map parity (`make_expr_noise` and `map_function`), per-chunk sampler dispatch (`noise_impl`), and noise plugin dtype/schema acceptance (`noise_udf` and `noise_plugin_type_udf`). Focused cross-file check of NaN-permitting expression domains versus the reference noise vector domain.
- **Invariants:** For the supported input dtype and output measure, the declared privacy map uses the same distribution, scale, and Lp metric as the actual per-chunk noise plugin. Valid input series are non-null and have an Lp metric on non-NaN values. The plugin output preserves row count, chunk length, and numeric dtype.
- **Assumptions:** Valid per-measurement input plans satisfy their `ExprDomain`; `MakeNoise` fulfills its own sampling/privacy-map contract for non-NaN vectors; chunk-level calls receive independent randomness and no data-dependent failures. We do not claim that raw public plugin calls on nullable data are certified by the constructor.
- **Pinned sources:** [Noise expression](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_noise/mod.rs), [measure-to-noise dispatch](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/mod.rs), [float noise constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/float/mod.rs), [Polars metric-space preconditions](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/expr/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::make_private_expr::expr_noise::make_expr_noise` | privacy/nan-domain-precondition | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Metric-space precondition mismatch](../../../../../../investigations/polars-noise-lp-nan-domain.md), [issue #57](https://github.com/opendp/opendp-audit/issues/57) |
| `measurements::make_private_expr::expr_noise::map_function` | privacy/distribution-map-dispatch-parity | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Source correspondence](#distribution-and-privacy-map-dispatch) |
| `measurements::make_private_expr::expr_noise::noise_impl` | correctness/chunkwise-noise-dispatch | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Chunk semantics](#chunkwise-noise-and-dtype) |
| `measurements::make_private_expr::expr_noise::noise_plugin_type_udf` | correctness/numeric-dtype-validation | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Dtype restrictions](#chunkwise-noise-and-dtype) |

## Analysis

### Distribution and privacy-map dispatch

`NoiseExprMeasure for MaxDivergence` specifies `L1Distance<f64>` and `Laplace`; `NoiseExprMeasure for ZeroConcentratedDivergence` specifies `L2Distance<f64>` and `Gaussian`. The typed privacy-map helper `map_function<MO,T>` builds a `make_noise` vector measurement using `MO::Metric`, `MO`, and the same effective public `scale` passed to the plugin. At execution, `noise_impl` selects the Laplace constructor with `L1Distance` and `MaxDivergence`, or Gaussian with `L2Distance` and `ZeroConcentratedDivergence`, again with that scale and default granularity. The supported numeric dtype list is identical in the constructor's dispatch, the runtime's dispatch, and the output type UDF: `u32`, `u64`, `i8`, `i16`, `i32`, `i64`, `f32`, `f64`.

**Scoped result:** Distribution selection, metric and measure, scale, and dtype dispatch agree **by direct pinned-source inspection** for both measures and all eight accepted dtypes. This does not independently prove the underlying discrete Laplace/Gaussian sampling laws, the stability transformation, or the privacy map's one-sided floating-point calibration.

### Chunkwise noise and dtype

The plugin downcasts the supplied Polars series into typed primitive-array chunks, converts each chunk's values into a vector, calls the selected `MakeNoise` function, and reconstructs a same-numeric-type primitive array. Conditional on the input being non-null, the vector mechanism preserving length and successful sampling, chunking does not alter shape or dtype. The source does **not** guarantee chunk-independent random sampling in this audit; the underlying sampler/RNG behavior and native Polars materialization remain untested.

Polars nullable payloads require separate attention: `noise_impl` reads `chunk.values()` without a validity bitmap, so a raw plugin call on nullable data would not preserve nulls. But `make_expr_noise` explicitly rejects `middle_domain.column.nullable`, and those raw calls are **outside its validated input-domain contract**. This is recorded as a limited API observation, not a demonstrated privacy defect.

### NaN domain precondition discrepancy

Unlike the explicit non-null check, `make_expr_noise` does not check `middle_domain.column.atom_domain::<f32/f64>()?.nan()`. The constructor generates its privacy map from a fresh `VectorDomain::new(AtomDomain::<T>::new_non_nan())`. The actual `ExprDomain` retains its possibly NaN-permitting atom-domain descriptor; its `MetricSpace for LpDistance` currently checks only nullability and numeric dtype. Therefore accepting a floating expression domain under `L1Distance` or `L2Distance` does not by itself imply that the noise-map vector's non-NaN precondition holds for all members of the expression domain.

The [domain report](../../../../../../source/rust/src/domains/polars/expr/mod.rs.md) and [cross-file investigation](../../../../../../investigations/polars-noise-lp-nan-domain.md) identify this as a **confirmed metric-space validation discrepancy**. Because the analyzed aggregation primitives can impose stricter constraints on actual computed values, no end-to-end DP counterexample or confirmed distributional undercount is claimed.

## Next checks

- Run compiled OpenDP Polars integration tests comparing the noise plugin's output for one chunk and multiple chunks, both measures, and the eight numeric dtypes.
- Add a native metric-space precondition regression, then inspect which valid stable aggregations return a declared float domain permitting NaNs versus a genuinely NaN-valued result.
- Review the `make_noise` sampler and directed floating-point privacy-map arithmetic independently; the source-level dispatch check cannot substitute for a distribution/privacy proof.
