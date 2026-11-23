---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# IBig scalar noise via singleton-vector transformation

## Question and invariant

The non-deprecated scalar arbitrary-precision `ZExpFamily<P>` implementation calls `make_vec`, then the existing vector noise mechanism, then `then_index_or_default(0)`. This review tests whether scalar `AbsoluteDistance<RBig>` is preserved under the intermediate `LpDistance<P,RBig>` for `P=1,2`, whether the privacy map is inherited unchanged, and whether a missing vector index or sampling failure can silently produce a default scalar output.

The audit assumes the vector noise mechanism's sampler and privacy map are valid. The reduction is not itself a proof of discrete Laplace or Gaussian laws.

## Cross-file evidence

- [Scalar BigInt source audit](../source/rust/src/measurements/noise/nature/bigint/mod.rs.md); [pinned upstream scalar adapter](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/bigint/mod.rs).
- [`make_vec` and `then_index_or_default`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/scalar_to_vector/mod.rs) and [its existing audit](../source/rust/src/transformations/scalar_to_vector/mod.rs.md).
- [Vector `ZExpFamily<P>` implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/mod.rs), which maps each input `IBig` through a fallible sampler without changing the successful vector length.
- [`make_chain_mt` and `make_chain_pm`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/mod.rs), which compose with an identity stability map and retain the measurement privacy map after deterministic postprocessing.
- [Upstream scalar native test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/bigint/test.rs) and [independent source-equivalent reference test](../tools/tests/test_bigint_scalar_singleton_noise_model.py).

## Distance preservation

The scalar-to-vector map is `T(x)=[x]`. For `P=1,2`, and scalar integers `x,y`, the resulting vector `Lp` distance is `(|x-y|^P)^{1/P}=|x-y|`, exactly the scalar absolute distance. The `make_vec` stability map is the identity. Consequently, when the existing vector mechanism's privacy map is `M(d)`, the scalar composed measurement has map `M(identity(d))=M(d)`, with no extra multiplicative constant.

This is a semantic equality for each supported `P`, not a claim that invalid `P=0` admits a valid norm. The separate [invalid-exponent issue #37](https://github.com/opendp/opendp-audit/issues/37) remains tracked independently.

For reference, the vector `ZExpFamily<1>` map for positive scale `s` takes nonnegative distance `d` to `d/s`, and `ZExpFamily<2>` maps it to `d²/(2s²)`, with `M(0)=0` and `M(d>0,s=0)=+∞`. These formulas are evaluated at the unchanged `d` after the singleton transform; floating conversion and extremal bound behavior are concerns of the underlying noise-map code, not this adapter.

## Successful cardinality and errors

The initial transformation produces a one-element vector and a size-one output domain. The vector noise function calls `distribution.sample` exactly once for that element, then collects its fallible result into `Vec<IBig>`. If the call succeeds, `Vec` length remains one and `then_index_or_default(0)` returns the sampled element. If it fails, the vector measurement returns an error, and composition short-circuits before the index postprocessor; it never substitutes the default zero for a failed sample.

The index function's fallback is observable when used *independently* on an empty vector, but the scalar adapter cannot create that empty vector on its successful path. A general source-equivalent model of an empty vector would therefore be out of scope for a scalar input to this constructor.

## Independent executable checks

[The Python reference test](../tools/tests/test_bigint_scalar_singleton_noise_model.py) covers the following bounded arithmetic properties:

- 200 shifted finite rational noise laws across `P=1,2` and four support radii. For each, projection of the singleton vector's released output law is exactly the scalar shifted law.
- 578 singleton `Lp` powered-distance identities across integer pairs.
- 50 analytical privacy-map parameter cases for rational scales and distances, including zero sensitivity and zero scale.
- Controls for negative-distance rejection, zero-scale identity, and simulated sampler-error propagation.

The modeled rational noise weights are `2^{-|z|^P}` on *finite* support. They are a testing convenience and **not sampled from, nor asserted equal to**, OpenDP's unbounded discrete Laplace/Gaussian mechanisms. Thus the model demonstrates composition mechanics, not the underlying noise law or native error behavior.

## Findings and limitations

**No new defect established:** The scalar adapter preserves the one-element output and the existing vector noise privacy map for its supported `P` values, under the underlying vector mechanism's contracts. The fallback-default concern is ruled out by source-level cardinality reasoning, not empirical sampling.

**Remaining Partial:** Native OpenDP Rust integration, arbitrary-precision extreme scales, random entropy errors, and complete noise-map/distribution proofs. No candidate-defect issue was warranted for this bounded review. [Task #85](https://github.com/opendp/opendp-audit/issues/85) tracks the coordination outcome.

## Recommended follow-up

Run upstream `test_make_noise_atomdomain_ibig` and a native scalar/vector equivalence regression with deterministic shared noise increments. Verify the same behavior for `P=1` and `P=2` and ensure future vector sampler changes preserve successful vector length.
