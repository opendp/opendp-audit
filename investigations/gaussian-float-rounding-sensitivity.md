---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Partial
---

# Floating-point Gaussian: dyadic rounding and L2 sensitivity

## Invariant and threat model

The non-deprecated `make_gaussian` floating-point implementation transforms finite `T`-valued inputs to arbitrary-precision integer coordinates, adds discrete Gaussian noise and deterministically converts the result back. For finite float vectors `x, y` of the same known dimension `n`, let `g=2^k_min` denote the minimum representable input spacing and `h=2^k` the chosen noise granularity (`k>=k_min`). The transformation must satisfy

`||Q_h(x)-Q_h(y)||_2 <= ||x-y||_2 + sqrt(n)(h-g)`,

where `Q_h` rounds to the nearest multiple of `h` with ties to positive infinity. After division by `h`, the right-hand side is the `make_float_to_bigint` stability-map upper bound. A failure would cause understated Gaussian sensitivity and potentially understated zCDP.

The claim excludes nonfinite input atoms, entropy failures, source-level `Clone` side effects and exceptional resource exhaustion. It assumes the directed-rounding helper contracts are sound. We executed a mathematically independent small-grid model, **not** compiled OpenDP.

## Affected symbols and source audits

- [Floating-point pipeline source audit](../source/rust/src/measurements/noise/nature/float/mod.rs.md), including `FloatExpFamily<2>::make_noise` and `make_float_to_bigint`; [pinned upstream](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/float/mod.rs).
- [Rounding and scale utilities source audit](../source/rust/src/measurements/noise/nature/float/utilities/mod.rs.md), including `find_nearest_multiple_of_2k`, `get_rounding_distance`, `get_min_k`, and `integerize_scale`; [pinned upstream](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/float/utilities/mod.rs).
- [Discrete Gaussian privacy-map record](../source/rust/src/measurements/noise/distribution/gaussian/mod.rs.md) and [pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/gaussian/mod.rs).
- [Independent Python model](../tools/tests/test_float_gaussian_rounding_model.py). The Rust module's [existing tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/float/utilities/test.rs) were inspected but not executed.

## Reasoning and evidence

### Exact dyadic rounding

For finite `f32` and `f64`, every representable value is an integer multiple of `g=2^k_min`. The code converts the input into an exact `RBig`, then maps each coordinate to the nearest index on the `h` grid using `floor(x/h + 1/2)`. This resolves signed half-grid ties toward positive infinity, contrary to the “ties rounding down” wording in one helper comment and proof. That difference does not affect the magnitude argument below.

For any two coordinates `a, b` on the input lattice, the greatest possible separation expansion under this deterministic nearest-grid rule is bounded by `h-g` when `h>g`, and zero when `h=g`. This follows by considering the closest possible pair straddling a rounding decision: the input lattice prevents them from being closer than `g` while their rounded values are `h` apart. More generally, coordinatewise rounding errors have opposite signs with total absolute difference at most `h-g`. By the L2 triangle inequality, the vector expansion is at most `sqrt(n)(h-g)`. Dividing by `h` gives the integer-coordinate sensitivity map.

The implementation computes `sqrt(n)` with `f64::inf_cast(n)?.inf_sqrt()?`, then represents the result as an exact rational. Both directed helpers specify an upper (never lower) approximation, or error. If `h=g`, the allowance vanishes and no known vector size is needed. Otherwise the constructor rejects missing `size`. An unsized vector with arbitrary length cannot use a finite universal `sqrt(n)` adjustment.

The integer noise distribution uses exact rational scale `σ/h` and receives the upper-bounded integer sensitivity. The discrete-Gaussian zCDP bound is then `(d_integer/scale_integer)^2/2`, and final float conversion is deterministic postprocessing. This establishes a source-level conditional argument; the runtime sampler and the cast contracts are not independently proved by the finite model.

### Independent finite tests executed 2026-11-22

A [standard-library Python test](../tools/tests/test_float_gaussian_rounding_model.py) ran successfully. Its input coordinates lie on a miniature dyadic lattice `g`, represented by integer grid indices. For grid widths `h=t*g`, `t in {1,2,4,8}`, it enumerates **all ordered input vector pairs**:
- dimension 1, coordinates -8..8 (17² pairs per grid);
- dimension 2, coordinates -8..8 (17⁴ pairs per grid);
- dimension 3, coordinates -4..4 (9⁶ pairs per grid).

Total comparisons: **4(17²+17⁴+9⁶)=2,461,004**. Every comparison satisfied `||Q_h(x)-Q_h(y)||_2 <= ||x-y||_2 + sqrt(n)(h-g)` to a numerical tolerance of `1e-12`. The test also checked **729** dyadic rounding-formula cases and six signed half-grid tie cases. No counterexample was found.

The first exploratory reference test used Python `int` truncation for negative values; that test itself was corrected to `math.floor` before the reported passing results. This was not a Rust finding. The tests are analytical small-grid models, not actual Rust calls, random sampling or a full `f32/f64` exhaustive check.

### Documentation consistency

The implementation and upstream Rust tests implement ties toward **positive infinity**. The `get_rounding_distance` source comment and its proof state “ties rounding down.” This is a documentation inconsistency that should be corrected. The conservative bound covers both tie choices, so it is not evidence of a privacy undercount.

### Directed integer-to-float and square-root dependencies (2026-11-22)

Source audits: [`InfCast<usize> for f64`](../source/rust/src/traits/cast/mod.rs.md) and [`InfSqrt for f64`](../source/rust/src/traits/arithmetic/mod.rs.md). The former dispatches through `FBig<Up>::from(IBig::from(size))`, not nearest-native integer casting. The latter computes `sqrt` under `FBig<Up>` and casts outward to `f64`, which should preserve a conservative upper bound. The float Gaussian utility combines them via `f64::inf_cast(size)?.inf_sqrt()?`, then converts the returned binary64 exactly into `RBig`.

The new [independent 64-bit reference model](../tools/tests/test_directed_gaussian_rounding_model.py) ran **9,484** adversarial and seeded integer sizes and tested whether an upward binary64 cast and upward sqrt remained above the exact real `sqrt(size)`. This included `2^53+1`, `2^63-1`, `2^64-1`, power-of-two boundaries and square boundaries. All passed exact `fractions.Fraction` inequalities. **This does not execute or independently verify dashu `FBig<Up>`; the dependency's real Rust implementation remains Partial.**

The previously reported tie-direction documentation mismatch is tracked by [audit issue #21](https://github.com/opendp/opendp-audit/issues/21). It does not affect the privacy bound.

## Findings

No violation of the L2 rounding-sensitivity inequality was found within the audited source-level assumptions and executed small-grid cases. A non-security documentation discrepancy exists for tie direction and is tracked in [audit issue #21](https://github.com/opendp/opendp-audit/issues/21). The full Gaussian cross-file privacy property remains **Partial** because the directed arithmetic, sampler and float conversion behavior were not natively executed or independently proved here. **Upstream disposition: unreported; no matching corrective PR found.**

## Unresolved questions

- Verify production `InfCast`, `InfSqrt` and rational/float conversions at extreme vector sizes and noise grids.
- Run the pinned upstream Rust tests on actual `f32` and `f64` inputs, including subnormals and large `k`, with explicit metric-distance property cases.
- Verify actual discrete-Gaussian sampling and entropy-error semantics; review unbounded runtime/memory behavior at extreme `k` separately.
