---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Partial
---

# Scalar-to-vector metric cast admits an undefined Lp exponent

## Invariant and threat model

A transformation certified under an `LpDistance<P,Q>` output metric should only be constructible where the metric has the mathematical meaning used by its stability proof. An unsupported `P` can invalidate the proof assumptions, especially when a composed measurement relies on the map. This is a **metric contract and proof-precondition gap**, not a demonstrated release or differential-privacy exploit.

## Affected symbols and source audits

- [`make_vec` and `then_index_or_default` source audit](../source/rust/src/transformations/scalar_to_vector/mod.rs.md) and [upstream Rust implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/scalar_to_vector/mod.rs).
- [Upstream `make_vec` proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/scalar_to_vector/make_vec.tex).
- [`LpDistance<P,Q>` and vector metric-space check](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/mod.rs), plus the existing [metrics source report](https://github.com/opendp/opendp-audit/blob/main/source/rust/src/metrics/mod.rs.md).
- [Finite standalone mathematical checks](../tools/tests/test_scalar_to_vector_lp_model.py) and [audit candidate issue #37](https://github.com/opendp/opendp-audit/issues/37).

## Reproduction and evidence

1. The Rust `make_vec<T, const P: usize, Q>` generic parameter `P` has type `usize`, but no `P > 0` constraint. The function creates `LpDistance::default()` with unchanged `StabilityMap::new(Clone::clone)`.
2. `LpDistance<P,Q>` implements `Metric` for any `P: usize`. Its `MetricSpace` implementation for `VectorDomain<AtomDomain<T>>` rejects NaN-permitting domains but does **not** inspect `P`. Consequently, visible construction checks admit `P=0` for `AtomDomain::<f64>::new_non_nan()`, despite the mathematical specification's nonzero-denominator requirement.
3. The `make_vec.tex` proof writes the singleton distance as `(sum |x_i-x'_i|^p)^(1/p) = |x-x'|`. The step is valid for `p>0` but not for `p=0` because the exponent `1/p` is undefined. The public metric documentation also uses ordinary `Lp` notation without giving `P=0` alternate semantics.
4. **Conditional L0 interpretation:** If `LpDistance<0,f64>` were defined as `L0` support size, choose `x=0.0`, `x'=0.5`, and `d_in=0.5`. A singleton difference has L0 size 1, while `make_vec` maps `d_in` to 0.5. This violates the stated 1-stability condition. The upstream source does **not** commit to this L0 interpretation, so this is an explanatory countermodel rather than a proved OpenDP privacy bug.
5. **Executed:** Four Python standard-library tests. Across 25 ordered rational pairs for each of `P=1,2,3,4,8`, the singleton norm equaled the absolute scalar distance (within numerical tolerance). A model explicitly rejects zero as a valid exponent of the ordinary norm, and the L0 conditional counterexample computes `1 > 0.5`. The remaining test checks the `then_index_or_default(0)` postprocessing branch. **Not executed:** Native OpenDP Rust construction, measurement chaining, FFI, or any compiled library.

## Finding and disposition

**Candidate, source-supported metric-contract gap** for `P=0`. Valid positive exponents behave as expected for the finite model. **Unreported upstream** after searches for `LpDistance<0>`, `make_vec` and zero exponent semantics; historical upstream [issue #773](https://github.com/opendp/opendp/issues/773) is a broader metric-refactoring task, not a specific fix. The audit tracking record is [#37](https://github.com/opendp/opendp-audit/issues/37). Severity and practical privacy impact remain uncertain until a concrete compiled constructor path or supported mechanism is identified; no privacy guarantee failure is claimed.

## Unresolved questions

- Does any production or user-exposed `make_noise`/Polars path actually instantiate `LpDistance<0,Q>`? Determine supported const-generic `P` values and whether trait implementations constrain them transitively.
- Compile and run the `P=0` constructor witness; determine whether the correct contract is to reject it universally or assign a documented, proven alternative distance interpretation.
- Establish generic `Q`/`T` metric preconditions for non-real numerical types rather than extrapolating from the rational scalar model.
