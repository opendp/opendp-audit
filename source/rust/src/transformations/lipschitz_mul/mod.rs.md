---
schema_version: 1
source: rust/src/transformations/lipschitz_mul/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/lipschitz_mul/mod.rs`

## Scope and assumptions

Review of non-deprecated `make_lipschitz_float_mul<TA>` for conservative scalar floating-point multiplication stability under the absolute-distance metric. The claimed bound applies when finite, correctly ordered clamp bounds `lower <= upper` and a finite multiplier `constant` yield successfully constructed transformations. We also inspected constructor behavior for reversed finite bounds. This review is anchored to upstream `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`.

**Invariant:** For input values `x,y` and a nonnegative bound `d >= |x-y|`, the released clamped-and-saturated products differ by no more than the stability-map output if the map succeeds. The release must stay within `AtomDomain::new_non_nan()`. All nonzero numerical error bounds are rounded conservatively.

**Dependencies:** [transformation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/lipschitz_mul/mod.rs#L1), [`SaturatingMul` and outward arithmetic](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/arithmetic/mod.rs#L1), [`total_clamp` and float bits](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/operations/mod.rs#L1), [domain/metric compatibility](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs#L1), [upstream test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/lipschitz_mul/test.rs#L1). See the [cross-file investigation](../../../../../investigations/lipschitz-float-mul-rounding.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `transformations::lipschitz_mul::make_lipschitz_float_mul` | privacy/stability-roundoff-multiplication | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Exact-rational reference and f32/f64 models](../../../../../investigations/lipschitz-float-mul-rounding.md); no underestimation in the modeled finite cases; native arithmetic untested. |
| `transformations::lipschitz_mul::make_lipschitz_float_mul` | correctness/inverted-bounds-construction | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Issue #32](https://github.com/opendp/opendp-audit/issues/32): reversed finite bounds pass construction and fail on each invocation; source-level counterexample. |
| `transformations::lipschitz_mul::make_lipschitz_float_mul` | correctness/non-nan-finite-output | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Runtime multiplication path](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/lipschitz_mul/mod.rs#L74); finite normal parameters saturate to finite endpoints, but native and nonfinite parameter tests were not executed. |

## Analysis

For valid ordered bounds, `input_mag = max(abs(lower), upper)` is the maximum absolute endpoint magnitude; notably, when `upper < 0` and `lower <= upper`, `abs(lower)` is necessarily the larger magnitude, so omitting `abs(upper)` does not itself underestimate the bound. The code obtains `output_mag` using outward multiplication by `abs(constant)`. The `output_ulp` expression is `2^(raw_exponent(output_mag)-EXPONENT_BIAS-MANTISSA_BITS)`, evaluated with outward `InfPowI`. The map adds `d_in*abs(constant)` to this error bound using outward arithmetic.

For normal finite products, two separately rounded nearest-float multiplications can differ from their exact real products by a total of at most one unit in the last place (ULP) of the greatest output magnitude; clamp and saturation do not increase real absolute differences. For **subnormal** `output_mag`, `raw_exponent=0` yields a formal half-minimum-subnormal power, but `InfPowI` must round it *up* (or return an error); if it succeeds, its result is at least one minimum subnormal. This matters to the bound.

An independent Python model used random bit patterns for `f32` and `f64`, NumPy `float32` for the actual single-precision products, IEEE binary64 for double-precision products, and Python `fractions.Fraction` for exact input difference/product comparisons. It tested **140,291 `f32` cases** (seed 1024; 180,000 attempted) and **14,280 `f64` cases** (seed 20261123; 18,000 attempted, including 722 where the computed upper product magnitude was subnormal). Only finite cases whose ideal upper magnitude was representable were checked. All successful reference-model inequalities held after outwardly rounding the computed ULP. An earlier model that retained the unrepresentable half-minimum-subnormal ULP produced spurious violations; those do **not** indicate an OpenDP defect. The [investigation](../../../../../investigations/lipschitz-float-mul-rounding.md) records the mathematical and execution limitations.

For reversed bounds `(lower,upper)=(2.0,1.0)` and `constant=1.0`, constructor-time computations are well-defined: `input_mag=2`, `output_mag=2`, and the error allowance is finite. `Transformation::new` checks the domain and metric spaces, not bounds captured by the closure. At invocation, `arg.total_clamp(2.0,1.0)?` returns `FailedFunction` because `min > max`. This low-severity API validation problem is now tracked in [audit issue #32](https://github.com/opendp/opendp-audit/issues/32) and is not a demonstrated privacy leak; source-level evidence only, no compiled Rust reproduction.

The existing upstream test only exercises `constant=2`, `bounds=(0,10)`, and an ordinary scalar input; it does not test reversed bounds or tiny floating-point values. The historical upstream [issue #581](https://github.com/opendp/opendp/issues/581) and [merged PR #582](https://github.com/opendp/opendp/pull/582) fixed a different clamping-operand bug.

## Next checks

- Run native f32/f64 property tests against compiled OpenDP, especially underflow, overflow error paths, and negative-only bounds.
- Add a constructor-time ordering check and native regression for reversed bounds; link to [issue #32](https://github.com/opendp/opendp-audit/issues/32).
- Check outward `InfMul` and `InfPowI` implementations independently at extreme exponents and test failure handling.
