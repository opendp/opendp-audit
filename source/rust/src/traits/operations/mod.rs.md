---
schema_version: 1
source: rust/src/traits/operations/mod.rs
updated: 2026-11-22
---

# `rust/src/traits/operations/mod.rs`

## Scope and assumptions

- **Audit scope:** The `TotalOrd::total_clamp` default method's handling of an invalid `min > max` interval, as called by the non-deprecated `make_lipschitz_float_mul` transformation. Other operations in the module are not reviewed.
- **Invariant:** When the bounds are inverted, the clamp returns an error rather than an output; on valid, comparable operands, it returns the lower bound, upper bound, or value as appropriate.
- **Source:** [Pinned `total_clamp` implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/operations/mod.rs), [call site](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/lipschitz_mul/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `TotalOrd::total_clamp` | correctness/invalid-bounds-error | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Existing constructor source coverage](../../transformations/lipschitz_mul/mod.rs.md) |

## Analysis

### `TotalOrd::total_clamp` — `correctness/invalid-bounds-error`

**Conclusion:** No error in the scoped `total_clamp` implementation. Its first branch is `if min.total_gt(&max)? { return fallible!(FailedFunction, "min cannot be greater than max") }`, before evaluating or clamping the input value. This ensures that invalid ordering is rejected at **invocation**, but the calling transformation constructor does not check the bounds early. On comparable inputs with `min <= max`, comparisons select `min` below the interval, `max` above the interval, or return the original value inside it.

**Evidence:** Source inspection of control flow and a standalone model of an inverted interval; [reproducible 22,000-case reference test](../../../../../tools/tests/test_lipschitz_mul_model.py) also exercises the valid-bounds multiplication allowance. The compiled Rust method was not executed. The [existing investigation](../../../../../investigations/lipschitz-float-mul-rounding.md) and [audit issue #32](https://github.com/opendp/opendp-audit/issues/32) concern the **caller**, not an intrinsic bug in `total_clamp`.

**Limitations:** `ProductOrd::total_cmp` implementations, nullable values, and other clamp consumers were not audited.

## Next checks

Native constructor and invocation regressions for the caller. No change to `TotalOrd::total_clamp` is indicated by this bounded review.
