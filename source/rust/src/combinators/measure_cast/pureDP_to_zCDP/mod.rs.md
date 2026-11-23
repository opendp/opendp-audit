---
schema_version: 1
source: rust/src/combinators/measure_cast/pureDP_to_zCDP/mod.rs
updated: 2026-11-22
---

# `rust/src/combinators/measure_cast/pureDP_to_zCDP/mod.rs`

## Scope and assumptions

Review the non-deprecated `make_pureDP_to_zCDP` conversion at upstream `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`; specifically: preserving the original measurement function and input space, conversion of an `ε`-max-divergence guarantee into `ρ=ε²/2` zCDP, and handling of positive infinity. This is not a review of the original measurement's privacy claim, all possible invalid maps, or the full arbitrary-precision arithmetic backend.

The theorem assumes finite, nonnegative pure-DP bounds for valid measurements, with the directional max-divergence guarantee holding **both ways** for adjacent inputs. Directed `InfPowI` and `InfDiv` operations must round upward or fail, not silently return a smaller numerical privacy parameter.

- Source: [pinned Rust constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/measure_cast/pureDP_to_zCDP/mod.rs), [arithmetic trait implementations](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/arithmetic/mod.rs), [existing upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/measure_cast/pureDP_to_zCDP/test.rs).
- [Cross-file investigation](../../../../../../investigations/measure-cast-privacy-boundary-model.md) and [reproducible reference model](../../../../../../tools/tests/test_measure_cast_reference_model.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `combinators::measure_cast::pureDP_to_zCDP::make_pureDP_to_zCDP` | privacy/pure-dp-to-zcdp | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Bound conversion](#bound-conversion); [finite distribution model](../../../../../../investigations/measure-cast-privacy-boundary-model.md) |
| `combinators::measure_cast::pureDP_to_zCDP::make_pureDP_to_zCDP` | correctness/infinite-bound | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Boundary analysis](#boundary-analysis) |

## Analysis

### Bound conversion

The output function and input metric/domain come from the original measurement; the map first calls the original `privacy_map.eval(d_in)`, then returns `eps.inf_powi(2)?.inf_div(&2)`. By the standard pure-DP-to-zCDP theorem (BS16, cited in upstream source), an `ε`-pure-DP mechanism is `ε²/2`-zCDP. A conservative computation of this formula is sufficient; the implementation deliberately uses upward arithmetic instead of ordinary binary64 `eps*eps/2`.

The independent [finite model](../../../../../../tools/tests/test_measure_cast_reference_model.py) enumerated 21 full-support ternary and 15 full-support binary laws and checked **3,330** ordered-pair/Rényi-order comparisons against `α ε²/2` for `α=1.5, 2, 3, 5, 10`. All passed. The model calculates the ideal real-valued bound; it does **not** exercise the compiled Rust conversion or prove the general theorem.

### Boundary analysis

A source-level `eps == +∞` branch returns `+∞` before power/division. Valid `eps=0` maps to zero; positive tiny finite `eps` requires upward arithmetic to avoid underflow-induced privacy underestimation. Rust tests cover a zero-noise Laplace measurement's `0` and `+∞` outputs, but were inspected, **not executed**. Finite overflow can raise an arithmetic error instead of silently claiming a smaller `ρ`; whether this is a usability limitation requires separate runtime testing.

**Finding:** No counterexample in the declared numerical model or source-level branch logic. Privacy status stays **Partial** pending the actual directed-arithmetic implementation and native Rust tests.

## Next checks

- Run compiled Rust tests for subnormal positive `ε`, `2^-512`, finite near-overflow `ε`, zero, and infinity.
- Confirm `InfPowI` and `InfDiv` never round below the exact `ε²/2` result for every successful finite input.
