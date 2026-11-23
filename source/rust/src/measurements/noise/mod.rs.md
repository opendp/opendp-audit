---
schema_version: 1
source: rust/src/measurements/noise/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/noise/mod.rs`

## Scope and assumptions

- **Scope:** The non-deprecated `ZExpFamily<1>` distribution's public Rustdoc, its implementation of `Sample`, and the generic `MakeNoise` vector wrapper. The `ZExpFamily<2>` Gaussian distribution and the generic measure's complete privacy proof are excluded.
- **Invariants:** The public Laplace distribution must have a nonnegative PMF with total mass one; `Sample for ZExpFamily<1>` must add shifted, zero-centered discrete Laplace noise; construction must enforce a valid distribution before making privacy claims.
- **Assumptions:** Rational scale is nonnegative for a valid `ZExpFamily<1>`, CKS20 sampler has the distribution claimed by its specification, repeated entropy draws are independent, and arbitrary-precision additions are exact. The full independence/entropy and privacy proofs were not re-executed.
- **Pinned sources:** [Noise distribution, Sample and MakeNoise](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/mod.rs), [Laplace privacy-map implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/laplace/mod.rs), [CKS20 sampler](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/cks20/mod.rs) and [MakeNoise proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/MakeNoise_IBig_for_RV.tex).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `ZExpFamily<1>` | documentation/discrete-laplace-pmf | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Duplicated negative PMF](#duplicated-negative-pmf) and [issue #48](https://github.com/opendp/opendp-audit/issues/48) |
| `<ZExpFamily<1> as Sample>::sample` | correctness/shifted-discrete-laplace | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Shifted sampler trace](#shifted-sampler-trace) and [investigation](../../../../../investigations/cks20-discrete-laplace-normalization.md) |
| `<RV as MakeNoise<VectorDomain<AtomDomain<IBig>>>>::make_noise` | privacy/vector-noise-construction | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Measurement construction](#measurement-construction) and [source proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/MakeNoise_IBig_for_RV.tex) |

## Analysis

### Duplicated negative PMF

The `ZExpFamily<P>` public proof-definition comment for `P=1` duplicates the negative discrete-Laplace factor `(exp(-1/scale)-1)/(exp(-1/scale)+1)`, which is strictly negative at every positive scale. The same erroneous factor appears in [`cks20::sample_discrete_laplace` Rustdoc](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/cks20/mod.rs); the corrected LaTeX proof and statistical test oracle instead use `(1-q)/(1+q)` for `q=exp(-1/scale)`. This is a **second documentation location of the same defect**, tracked in consolidated [audit issue #48](https://github.com/opendp/opendp-audit/issues/48). It does not constitute a separate error in the sampler's acceptance mechanism.

### Shifted sampler trace

For `ZExpFamily<1>`, `Sample::sample` returns `Ok(shift + sample_discrete_laplace(self.scale.clone())?)` using arbitrary-precision `IBig` addition. Therefore the center shift is applied *after* sampling the zero-centered discrete distribution. The [CKS20 independent reference model](../../../../../tools/tests/test_cks20_laplace_law_model.py) checks the normalized zero-centered law for positive scales but does not run this native addition path or native randomness. The output-law assessment remains **Partial**.

### Measurement construction

For a vector of big integers, the generic `MakeNoise` implementation requests `self.noise_privacy_map` before constructing the measurement; its closure samples every element through `distribution.sample(x_i)`. The adjacent `NoisePrivacyMap<L1Distance<RBig>, MaxDivergence> for ZExpFamily<1>` checks `scale < 0` and rejects negative scales, so a successful *Laplace measurement construction* has the requisite nonnegative-scale premise. It returns zero privacy cost for zero input distance, infinite privacy cost for nonzero distance at zero scale, and an upper-rounded `d_in / scale` otherwise. The precise privacy-law proof and independence of native entropy draws were not independently verified here. The `ZExpFamily` struct is public and directly calling `Sample::sample` with an invalid negative scale is outside the valid-distribution trait precondition.

**Evidence boundary:** Commit-pinned source and proof inspection, plus the four existing independent distribution-model tests (previously passed in CI). No new native Rust runtime test was executed for this source audit.

## Next checks

Correct the negative Rustdoc coefficient in *both* `noise/mod.rs` and `cks20/mod.rs`. Run native Rust tests for `Sample` shift semantics and vector noise distribution, and test entropy-failure behavior separately. No further issue was opened because [#48](https://github.com/opendp/opendp-audit/issues/48) already covers the shared documentation defect.
