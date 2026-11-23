---
schema_version: 1
source: rust/src/measurements/noise/nature/bigint/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/noise/nature/bigint/mod.rs`

## Scope and assumptions

- **Scope:** The non-deprecated, arbitrary-precision scalar noise adapter `MakeNoise<AtomDomain<IBig>, AbsoluteDistance<RBig>, MO> for ZExpFamily<P>`. Check exact singleton-vector conversion, privacy-map handoff, successful scalar output cardinality and error propagation. Relevant instantiated distributions are `P=1` (discrete Laplace) and `P=2` (discrete Gaussian), with supported measures.
- **Invariant:** For any valid scalar input `x`, the adapter implements the scalar projection of its vector noise mechanism on `[x]`. Its privacy map is the vector mechanism's map evaluated at the unchanged scalar distance, and successful invocation always returns the vector's unique output rather than the postprocessor's default value.
- **Assumptions:** The underlying vector `ZExpFamily<P>` mechanism is valid and samples once per input element; the `Sample` implementations propagate failures; the `Measurement >> Function` chain preserves the prior privacy map; `P` is in the supported noise-map family. Independent distributional/entropy proofs are outside scope.
- **Pinned upstream:** [Scalar IBig adapter](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/bigint/mod.rs), [`make_vec` and `then_index_or_default`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/scalar_to_vector/mod.rs), [vector noise implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/mod.rs), [composition implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/mod.rs), [native upstream scalar test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/bigint/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::noise::nature::bigint::MakeNoise_AtomDomain_for_ZExpFamily::make_noise` | correctness/scalar-vector-equivalence | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file source proof](../../../../../../../investigations/bigint-scalar-singleton-noise.md) |
| `measurements::noise::nature::bigint::MakeNoise_AtomDomain_for_ZExpFamily::make_noise` | privacy/singleton-lp-map-preservation | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Metric and map reasoning](../../../../../../../investigations/bigint-scalar-singleton-noise.md) |
| `measurements::noise::nature::bigint::MakeNoise_AtomDomain_for_ZExpFamily::make_noise` | correctness/empty-default-unreachable | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cardinality and error trace](#index-zero-and-error-path) |
| `measurements::noise::nature::bigint::MakeNoise_AtomDomain_for_ZExpFamily::make_noise` | privacy/distributional-soundness | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | Depends on the underlying vector `ZExpFamily` sampler and proof, not retested in native Rust |

## Analysis

### Singleton metric and privacy composition

The adapter first invokes `make_vec` on the scalar input space, yielding a transformation from `AtomDomain<IBig>, AbsoluteDistance<RBig>` to `VectorDomain<AtomDomain<IBig>>::with_size(1), LpDistance<P,RBig>`. Its function is `x ↦ vec![x.clone()]`, and its stability map is `Clone::clone`, i.e. identity on the distance.

For any `P∈{1,2}` and scalar integers `x,y`, the vector norm of their singleton images is `(|x-y|^P)^(1/P)=|x-y|`. There is no extra sensitivity factor or rounding in this reduction; `RBig` represents the metric distance. The adapter calls the vector `MakeNoise` on the transformation output space. `make_chain_mt` composes the vector noise privacy map with the identity stability map. Subsequent `then_index_or_default(0)` postprocessing retains that same map via `make_chain_pm`.

The [independent exact model](../../../../../../../tools/tests/test_bigint_scalar_singleton_noise_model.py) exhaustively checks 578 singleton `L1`/`L2` powered-distance identities and 50 rational map-parameter cases (zero sensitivity, zero/positive scale). These validate the mathematical reduction **only**, not the Rust implementation of infinity casting or every underlying sampler.

### Index zero and error path

The `make_vec` transformation always emits exactly **one** element. The vector `ZExpFamily<P>` implementation maps `distribution.sample(x_i)` over each vector element and collects into `Fallible<Vec<IBig>>`. On success it therefore returns a vector of exactly one noisy `IBig` element. The final `then_index_or_default(0)` obtains that element through `vec.get(0).cloned()`; the fallback `IBig::default()` is not reached for any successful call through this adapter.

If sampling fails, the collecting iterator returns `Err`; the composed measurement propagates the error before the postprocessor executes. The wrapper does not transform a failed sample into a public zero.

The [independent reference test](../../../../../../../tools/tests/test_bigint_scalar_singleton_noise_model.py) checks output equivalence for 200 shifted finite rational noise models, including the degenerate zero case; it also checks zero-noise identity and simulated sampler errors. Those finite distributions are deliberately truncated model laws, **not** the actual OpenDP discrete Laplace/Gaussian random samplers. The proof of fixed output length is by inspecting the actual Rust iterator and its fallible collection, not from the model alone.

### Native test and proof limitations

The upstream [scalar `ZExpFamily<2>` test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/bigint/test.rs) checks a sampled output, map at zero and unit sensitivity, and negative-distance rejection. It was inspected, **not executed** during this audit. The scalar adapter's `#[proven]` source proof is a compositional argument that depends on the scalar-to-vector, vector mechanism and postprocessing proof obligations. That dependence is retained rather than replaced by an empirical model.

The known invalid `LpDistance<0>` validation issue [#37](https://github.com/opendp/opendp-audit/issues/37) pertains to a broader `LpDistance` space. This particular instantiated scalar `ZExpFamily` route requires a supported `NoisePrivacyMap` trait implementation, here `P=1` or `P=2`, and does not independently expose that invalid-exponent case.

## Findings

**Bounded negative result:** For the supported `P=1,2` scalar `IBig` noise routes, the one-element conversion preserves distance and the vector privacy map; successful vectors always have an index zero. No confirmed new defect in this adapter was found.

**Residual Partial coverage:** Native sampler distributions, extreme `RBig` scales/distances, Rust error handling under exhausted entropy, and complete differential-privacy proofs remain dependent on other components. The new reference checks are not compiled OpenDP integration tests.

## Next checks

- Run the existing scalar `IBig` Rust test and add paired scalar/vector samples using a controlled common noise outcome to test execution equivalence, including a failing sampler.
- Revisit arbitrary-precision score handling and numeric conversion only if their corresponding underlying noise implementations change; neither is introduced by this adapter.
