---
schema_version: 1
source: rust/src/measurements/make_private_expr/expr_dp_sum/mod.rs
updated: 2026-11-22
---

# `rust/src/measurements/make_private_expr/expr_dp_sum/mod.rs`

## Scope and assumptions

Reviewed the **non-deprecated** `make_expr_dp_sum` implementation at OpenDP `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`, focusing on typed-bound midpoint calculation and the null/NaN fill-plus-clipping pipeline. Related [`dp_mean` caller](../expr_dp_mean/mod.rs.md), [`make_expr_clip`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_clip/mod.rs), and [`make_expr_sum`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_sum/mod.rs) were inspected. No compiled OpenDP/Polars code ran; the independent reference model simulates fixed-width integer overflow and clipping.

**Invariant:** For public valid closed bounds `lower ≤ upper`, inserting a null/NaN replacement should be deterministic and the resulting value should remain within the bounds, allowing a conservative downstream sum-sensitivity bound. The constructor is fallible and should not panic on valid literal bounds. If the intended fill is the midpoint, integer arithmetic must not truncate or overflow before averaging.

- Pinned [source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_dp_sum/mod.rs), [typed literal extraction](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/mod.rs), and [cross-file investigation](../../../../../../investigations/polars-dp-mean-filler-and-denominator.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::make_private_expr::expr_dp_sum::make_expr_dp_sum` | correctness/integer-midpoint-overflow | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Source-level overflow witness](#source-level-overflow-witness) |
| `measurements::make_private_expr::expr_dp_sum::make_expr_dp_sum` | privacy/public-bounds-fill-and-clip | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Clipping and privacy boundary](#clipping-and-privacy-boundary) |

## Analysis

### Source-level overflow witness

When both `lower` and `upper` are present, the constructor obtains the prior column dtype and calls `get_filler<T>`. For numeric typed literal bounds, `literal_value_of::<T>` yields the two values and `get_midpoint<T>` evaluates `lit((lower + upper) / (T::one() + T::one()))` using **ordinary fixed-width arithmetic**, not a checked or widening operation. The `Number` trait does not change the integer `+` operator's overflow semantics.

For an `Int8` column and typed literal bounds `[100i8,120i8]`, the correct midpoint is `110`, but intermediate `100i8 + 120i8 = 220` cannot be represented by `i8`. In a Rust checked-overflow build, the source operation panics instead of returning the constructor's `Fallible` error; under wrapping semantics it yields `-36`, whose integer half is `-18`. The subsequent clip converts the fill to `100`, **not** to the intended `110`. An analogous valid `UInt32` example is `[2^31,2^31+2]`, where the wrapped midpoint is `1` and clipping returns `2^31` rather than `2^31+1`. The `Int8` and `UInt32` types are both supported by `make_expr_clip`; this is not restricted to otherwise rejected `UInt8/UInt16` inputs.

The [independent fixed-width Python test](../../../../../../tools/tests/test_polars_dp_mean_model.py) reproduced those cases and checked overflow/clipping behavior across signed 8/16/32/64-bit and unsigned 32/64-bit reference models. It is **not a native Rust reproduction**, so target-specific build and Polars-literal issues remain to be tested.

**Upstream disposition:** This is **already reported**, explicitly, in [OpenDP issue #3217](https://github.com/opendp/opendp/issues/3217) (“midpoint calculation can overflow (bug but not privacy impacting)”). Do not file a duplicate candidate-defect issue in the audit repository.

### Clipping and privacy boundary

The constructor builds `input.fill_null(filler)`; for floating-point input it also applies `.fill_nan(filler)`; then it applies `.clip(lower, upper)` **before** `.sum()`. The public `filler` calculation depends on bounds and dtype, not on private records. Under successful execution with valid closed bounds and a supported Polars clipping operation, every resulting atom is within `[lower,upper]` even if a wrapping filler is not the intended midpoint. The stable sum consequently receives bounded atoms and its separate stability map controls the sum's sensitivity.

This supports the upstream classification as a **utility/correctness** problem rather than a demonstrated privacy undercount. It does **not** prove end-to-end Polars execution is infallible, nor that every unsupported type or exceptional arithmetic path is private. A checked-overflow panic can affect public-parameter availability. The review of full executable privacy semantics is **Partial**.

## Next checks

- In native Rust, construct an `Int8` `dp_sum` with bounds `[100,120]` and a null input, test debug and optimized release modes, and assert either the intended midpoint or a fallible error rather than a panic.
- Avoid `lower + upper` overflow by using a widening calculation or `lower + (upper-lower)/2` with checked direction-aware arithmetic; preserve desired rounding for negative ranges and floating-point extremes.
- Extend native tests to `Int32`, `UInt32`, `Int64`, and `UInt64` and verify the clipped sum's output domain and privacy map.
