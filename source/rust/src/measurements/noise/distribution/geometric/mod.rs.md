---
schema_version: 1
source: rust/src/measurements/noise/distribution/geometric/mod.rs
updated: 2026-11-22
---

# `rust/src/measurements/noise/distribution/geometric/mod.rs`

## Scope and assumptions

- **Audit scope:** Positive-scale, bounded `make_geometric` construction for scalar and vector signed-integer inputs and propagation of the `sample_discrete_laplace_linear` interval-width overflow through invocation. Unbounded sampling and privacy-map derivations are not re-audited here.
- **Invariant:** For a public integer support interval that can be iterated in `usize` steps, successful construction should not silently yield a measurement whose invocation always fails for any valid input solely due to overflow in the narrower input type.
- **Assumptions:** Ordinary Rust checked-subtraction and `?` propagation; a positive finite scale such as `1.0`; a valid non-null integer domain; `usize` can represent the desired interval width.
- **Pinned upstream:** [Bounded measurement constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/geometric/mod.rs), [sampler](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/geometric/mod.rs), [upstream native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/geometric/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::noise::distribution::geometric::make_geometric` | availability/bounded-dispatch | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Signed-width investigation](../../../../../../../investigations/bounded-geometric-signed-width-overflow.md) |
| `measurements::noise::distribution::geometric::ConstantTimeGeometric::make_noise` | availability/invocation-overflow | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Confirmed failure path and issue #4](https://github.com/opendp/opendp-audit/issues/4) |
| `measurements::noise::distribution::geometric::ConstantTimeGeometric::make_noise` | privacy/directed-p-calibration | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Source review](#analysis), extreme-scale native checks not run |

## Analysis

A non-`None` `bounds` argument dispatches to `ConstantTimeGeometric { scale, bounds }.make_noise`. The vector implementation checks only that `lower <= upper` and that scale is convertible to a rational and has a usable conservative geometric success probability. It then builds `Measurement::new` with a fallible closure calling `sample_discrete_laplace_linear::<T, f64>` on every element. The constructor does not evaluate `upper - lower` or its trial count; that computation happens inside the sampler on **invocation**.

For `T = i8`, `bounds = (-128, 0)` and `scale = 1.0`, the distribution/privacy-map setup has no interval-width arithmetic blocking construction. But the sampler immediately attempts `0_i8.alerting_sub(&(-128_i8))`, which fails since `128` exceeds `i8::MAX`. As a result, vector invocation with any nonempty input fails, and scalar invocation fails as well because the scalar path wraps the input in a singleton vector and invokes the same vector mechanism. For an **empty vector**, the element-wise map is empty and no sampler runs; its invocation can succeed. This qualification matters when describing the error as deterministic: the error is unconditional for nonempty input vectors (or scalars), not for all domain values.

For `scale == 0` or `lower == upper` the sampler bypasses this path; those cases do not reproduce the overflow. With positive scale and smaller signed intervals whose width fits `T` (for example `i8` `(-128,-1)`), the intermediate subtraction does not fail.

**Disposition:** Confirmed functional availability defect, tracked by [audit issue #4](https://github.com/opendp/opendp-audit/issues/4). It is **not** a demonstrated DP privacy-accounting violation. Source-level control flow and exact integer arithmetic establish the failure; native Rust execution was unavailable in this audit.

The bounded constructor computes a conservative success probability `p = 1 - exp(-1/scale)` with directed rounding, and passes a rational `ZExpFamily<1>` scale to its privacy map. The probability-to-privacy calibration is not exhaustively verified here and remains `Partial`.

## Next checks

- Execute a native Rust regression for scalar and nonempty vector `i8` bounded to `(-128,0)` at scale `1.0`; expect successful construction and current invocation overflow.
- Fix the sampler's trial count arithmetic in a wider integer type, then verify the fixed-size interval law and zero/degenerate-scale paths.
- Audit extreme-scale directed probability rounding and privacy maps independently; this report establishes a functional overflow, not a privacy failure.
