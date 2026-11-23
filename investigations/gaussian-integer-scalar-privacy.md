---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Partial
---

# Integer scalar Gaussian: zCDP accounting across conversion and postprocessing

## Invariant and threat model

For a valid integer scalar input `x`, positive finite standard deviation `σ`, and metric sensitivity bound `d`, `make_gaussian` should return a scalar of the same integer type and claim a conservatively rounded `ρ=d²/(2σ²)` zCDP bound. For `d=0` it reports zero privacy loss; for `σ=0, d>0` it reports infinite loss. Negative distances, negative scales, and nonfinite scales must be rejected rather than silently converted into privacy-optimistic values.

This audit is limited to `AtomDomain<T>` for built-in integer types with `AbsoluteDistance<QI>`; the float-domain discretization and noisy threshold algorithms are excluded. Claims are conditional on the exact discrete-Gaussian sampler and conservative rational-to-`f64` casting; no Rust binary was executed.

## Affected symbols and source audits

- [Gaussian distribution and privacy-map source audit](../source/rust/src/measurements/noise/distribution/gaussian/mod.rs.md), [pinned code](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/gaussian/mod.rs), and [zCDP proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/gaussian/NoisePrivacyMap_for_ZExpFamily2.tex).
- [Integer noise path source audit](../source/rust/src/measurements/noise/nature/integer/mod.rs.md), [pinned code](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/integer/mod.rs), and [Nature type dispatch](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/mod.rs).
- [Singleton vector transformation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/scalar_to_vector/mod.rs), [saturating cast implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/cast/mod.rs), and [Gaussian sampling entry point](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/mod.rs).
- [Independent reference test](../tools/tests/test_gaussian_scalar_privacy_model.py).

## Reasoning and evidence

### Scalar-to-vector delegation

The integer `Nature` dispatch accepts `k=None` or `Some(0)`, rejects nonzero `k`, and constructs `IntExpFamily<2>`. The scalar implementation maps the input to a fixed-length-one vector (`make_vec`, identity stability map) and calls the integer vector implementation. `make_int_to_bigint` applies `IBig::from` to each `T` atom and converts `d_in` via `RBig::try_from`, with an error on nonfinite/unrepresentable distances. The integer noise scale is `RBig::from(scale)` (via `integerize_scale(scale, 0)`), hence finite `f64` values are represented exactly as rationals rather than rounded downward.

The discrete-Gaussian vector mechanism adds one independently sampled `Z` to each exact integer. `then_saturating_cast` maps the result back to the requested fixed-width integer type, and `then_index_or_default(0)` extracts the lone element. Because valid execution preserves vector length one, the fallback default branch is not reached. Both final operations are deterministic postprocessing; no privacy cost is added. Unlike `FloatExpFamily`, this integer path introduces no discretization sensitivity adjustment.

### Privacy bound and boundary conditions

The source zCDP map rejects negative rational noise scale at construction, and rejects negative rational sensitivity on evaluation. For `d=0` it returns zero before checking for zero scale; for `d>0, σ=0` it returns infinity; otherwise it computes `f64::inf_cast((d/σ)^2/2)`. The `inf_cast` contract must yield an upper bound to preserve privacy even if the exact rational is between representable floating-point values.

The [pinned proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/gaussian/NoisePrivacyMap_for_ZExpFamily2.tex) references the CKS20 discrete Gaussian zCDP theorem, which bounds Rényi divergence at every order `α>1` by `α ||x-x'||²_2/(2σ²)`, conditioned on independent exact discrete Gaussian samples. In the scalar singleton case, the L2 norm equals the absolute difference, and saturation can only reduce divergence by postprocessing. For a bounded scalar integer domain, output saturation may improve utility near extrema while preserving this upper bound.

### Executed finite reference model

The independent [Python unittest](../tools/tests/test_gaussian_scalar_privacy_model.py) was run locally. It models a discrete Gaussian centered at an integer mean `μ` with ideal weights `exp(-(z-μ)²/(2σ²))`, normalized on integer support `[-80,80]` using numerically stable log-sum-exp. Across `σ in {0.5, 1, 2, 3}`, all ordered `(μ,ν)` in `{-2,-1,0,1,2}²`, and Rényi orders `α in {2,3,5}`, it checked **300** inequalities `D_α(P_μ||P_ν) <= α(μ-ν)²/(2σ²)+1e-9`; all passed. It additionally tested reference zero/negative sensitivity and scale cases and 81 pairwise saturation checks.

The finite support approximation discards extremely small tails and uses IEEE floating-point arithmetic; it is **not an exact distribution proof** or a sample from OpenDP. The analytic model tests the mathematical mechanism only. Neither the full Rust tests nor entropy-handling paths were executed here.

## Findings

No new privacy-map violation was observed within the tested integer-scalar Gaussian scope. The source control flow and model align with the claimed zCDP bound, conditional on the sampler and conservative conversion contracts. The full cross-file property remains **Partial** until these dependencies receive native execution and rigorous review. No audit-task issue or candidate defect was created.

## Unresolved questions

- Run upstream Rust tests on a pinned checkout; verify discrete Gaussian sampler correctness, entropy errors, and `f64::inf_cast` conservatism across extreme rational magnitudes.
- Review `FloatExpFamily` rounding-distance accounting independently; the present results do not extend to floats.
- Verify behavior under unusual sensitivity `QI` types, extreme scales, and allocation failures; ensure no source changes invalidate the pinned assumptions.
