---
schema_version: 1
source: rust/src/combinators/measure_cast/approximate/mod.rs
updated: 2026-11-22
---

# `rust/src/combinators/measure_cast/approximate/mod.rs`

## Scope and assumptions

Review the non-deprecated `make_approximate` adapter at upstream `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`, restricted to the privacy-distance conversion `d -> (d, 0)` and preservation of the measurement function, input domain, and metric. The source measurement must already meet its stated privacy measure. Source: [pinned constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/measure_cast/approximate/mod.rs), [Approximate measure definition](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measures/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `combinators::measure_cast::approximate::make_approximate` | privacy/zero-slack-lifting | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Algebraic argument](#algebraic-argument) |

## Analysis

### Algebraic argument

The implementation does not run or alter the original random function. It maps an input distance to the original privacy distance paired with `0.0`, using the source map's `Fallible` result. An exact guarantee is a special case of its approximate guarantee with zero slack; applying the same output measure while allowing an extra failure probability of zero changes neither the returned distribution nor the original distance constraint.

The FFI wrapper restricts dispatch to supported underlying measure types; that restriction is not a defect in the general typed constructor. The adapter does not validate arbitrary custom source privacy maps, nor should it. No executable native Rust test was run for this specific conversion; the conclusion is limited to the source-level algebra and metadata wiring.

**Finding:** No new defect in zero-slack lifting for valid source measurements.

## Next checks

- Test FFI-supported output measure variants and error forwarding in compiled Rust.
- Reassess when a new approximate distance type with nonstandard zero-slack semantics is introduced.
