---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Partial
---

# ALP projection-size exponent reaches the machine word width

## Invariant and reviewed path

The public, fallible ALP measurement constructor must reject a projection size that is not representable as `usize`. See [source coverage](../source/rust/src/measurements/alp/mod.rs.md), [upstream implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/alp/mod.rs), and [FFI](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/alp/ffi.rs).

## Minimal witness (not compiled)

```rust
let result = make_alp_state::<u64, u64>(
    MapDomain::default(), L01InfDistance::default(),
    1.0, 1_000_000_000_000_000_000, Some(4), Some(50), Some(4),
);
```

Here `quotient = scale/alpha = 0.25`, `m = value_limit * quotient = 1`, and `x = size_factor * total_limit * quotient = 12_500_000_000_000_000_000`. This is within `u64` but greater than `2^63`. The helper returns `exp = 64`, then the constructor evaluates `1 << exp` with a `usize` left operand. When `usize::BITS = 64`, this is an invalid shift. With overflow checks enabled, the expected behavior is a panic, not `Err`. In unchecked configurations, the computed shift cannot represent `2^64` bits either. No allocation of the requested projection was attempted.

**Executed:** Python 3 standard-library binary64/integer reproduction verified `x < 2^64`, `x > 2^63`, and `exp = 64`. Boundary totals `7e17`, `8e17`, `1e18` produced exponents 63, 64, 64. The compiled Rust implementation and its FFI were not run.

## Disposition

**Candidate, low-severity availability defect; verification partial.** Only public construction parameters are involved; no data-dependent crash or DP-accounting defect was shown. No equivalent upstream issue or corrective PR was identified. The candidate is now tracked as [audit issue #6](https://github.com/opendp/opendp-audit/issues/6); upstream disposition remains **Unreported**. A native debug/release regression is the next decisive test; guard the exponent against `usize::BITS` and return a parameter-validation error before shifting. An exact fix must also address other oversized allocations and saturating size conversions.
