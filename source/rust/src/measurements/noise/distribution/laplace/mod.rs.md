---
schema_version: 1
source: rust/src/measurements/noise/distribution/laplace/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/noise/distribution/laplace/mod.rs`

## Scope and assumptions

- **Audit scope:** The active, non-deprecated Laplace constructor's delegation and the pure-DP privacy map's sign, zero, and rational-to-`f64` boundary behavior. Only the exact-rational `ZExpFamily<1>` privacy map is examined in detail; the sampler's distribution, independence, FFI, and floating-point discretization proofs are separate properties.
- **Invariants:** Invalid negative rational scale is rejected at construction, invalid negative sensitivity is rejected at map evaluation, zero sensitivity maps to `ε=0` regardless of scale, positive sensitivity at zero scale maps to `ε=∞`, and positive-scale loss is conservatively no smaller than the exact rational `d/scale`. The constructor must delegate to the appropriate noise family for the input atom type.
- **Assumptions:** `RBig` division is exact; `InfCast<RBig> for f64` implements directed upward conversion; and the additive discrete-Laplace sampler implements the claimed distribution with data-independent errors. Those dependencies are inspected, not formally proved here.
- **Pinned upstream revision:** `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. [Laplace source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/laplace/mod.rs), [privacy map proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/laplace/NoisePrivacyMap_for_ZExpFamily1.tex), [noise core](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/mod.rs), [nature dispatch](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/mod.rs), [upward casting](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/cast/mod.rs), [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/laplace/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::noise::distribution::laplace::make_laplace` | correctness/distribution-delegation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Constructor delegation](#constructor-delegation) |
| `measurements::noise::distribution::laplace::DiscreteLaplace::make_noise` | correctness/distribution-delegation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Constructor delegation](#constructor-delegation) |
| `measurements::noise::distribution::laplace::NoisePrivacyMap<ZExpFamily<1>>::noise_privacy_map` | correctness/parameter-boundaries | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Boundary analysis](#boundary-analysis) |
| `measurements::noise::distribution::laplace::NoisePrivacyMap<ZExpFamily<1>>::noise_privacy_map` | privacy/pure-dp-loss | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Rational privacy accounting](#rational-privacy-accounting) |

## Analysis

### Constructor delegation

`make_laplace` constructs `DiscreteLaplace { scale, k }` and calls its `MakeNoise::make_noise` implementation. That implementation calls `DI::Atom::new_distribution(scale, k)`, then delegates to the returned distribution's noise mechanism. `Nature` dispatches finite/integer types to `IntExpFamily<1>`, floating-point types to `FloatExpFamily<1>`, and `IBig` directly to `ZExpFamily<1>`. Integer and big-integer inputs reject nonzero `k`; float inputs choose their minimum representable granularity when `k` is omitted. The integer path uses exact `IBig` conversion, samples an additive discrete-Laplace random variable, and postprocesses via saturation. The floating-point path first applies sensitivity-aware discretization, whose separate stability proof was not re-audited here.

For these constructor symbols, `Partial` indicates that source routing was inspected but full sampler and downstream composition behavior was not established. Negative `f64` scale is eventually rejected when the rational privacy map is constructed; nonfinite scale fails rational conversion in `Nature`/`integerize_scale`.

### Boundary analysis

In `NoisePrivacyMap<L1Distance<RBig>, MaxDivergence> for ZExpFamily<1>`, map construction first rejects `scale < 0`. The returned map rejects `d_in < 0`, then checks `d_in == 0` *before* zero scale. Thus `d_in=0, scale=0` produces `0.0`, and positive `d_in` at `scale=0` produces `f64::INFINITY`. The remaining positive-scale branch evaluates `f64::inf_cast(d_in / scale)`. Because the division is exact rational arithmetic and the cast is upward-directed, its result is conservative, conditional on the source's `InfCast` contract. No negative-scale, negative-distance, or zero-division path was found that mistakenly returns a finite positive privacy certificate.

The upstream test file includes native-type roundtrips, map rejection of negative/nonfinite sensitivities, signed zero, and exact zero-scale privacy-map assertions. Those tests were inspected, **not run** in this audit.

### Rational privacy accounting

The exact model for a positive rational scale and distance is `ε = d_in/scale`. The [independent reference tests](../../../../../../../tools/tests/test_laplace_privacy_map_model.py) passed four standard-library Python `unittest` cases: sign and zero boundaries; exact and upward-rounded results (including `1/3` and `5/3`); a subnormal-to-largest-finite ratio; an overflowing rational ratio; and **300 deterministic finite rational pairs** checked for upward enclosure and minimality of the enclosing binary64 value. This checks a mathematical oracle **rather than the OpenDP Rust sampler or casting implementation**. Its finite-ratio checks compare the candidate against exact `Fraction` arithmetic, and check that the preceding representable float lies below the true ratio. The model also checks the correct zero-scale infinity behavior.

This evidence supports the source-level accounting but does **not** independently establish the real discrete-Laplace law, entire vector L1 privacy proof, OS entropy behavior, or the compiled Rust directed cast. Thus `privacy/pure-dp-loss` remains `Partial` rather than a full mechanism certification.

**Disposition:** No new defect identified within this scope. Upstream [draft PR #2881](https://github.com/opendp/opendp/pull/2881) proposes additional `MultiDP` accounting for discrete Laplace, but is open and unmerged; it is not evidence of a defect in this reviewed `MaxDivergence` map. [Audit task #39](https://github.com/opendp/opendp-audit/issues/39) tracks completion of this bounded review.

## Next checks

- Run compiled upstream `test_make_laplace_map`, `test_make_noise_zexpfamily1_zero_scale`, and the native noise tests in a build with relevant features.
- Independently validate `InfCast<RBig>` for actual finite overflow and subnormal underflow and the discrete-Laplace tail/sampling law.
- Verify the vector-privacy bound and floating-point discretization in separate scoped reviews; do not infer end-to-end correctness from the isolated rational oracle.
