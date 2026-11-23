---
schema_version: 1
source: rust/src/measurements/alp/mod.rs
updated: 2026-11-22
---

# `rust/src/measurements/alp/mod.rs`

## Scope and assumptions

- **Property:** `correctness/projection-size-bounds`, for `make_alp_state` and `exponent_next_power_of_two`. The fallible constructor should reject unrepresentable projection sizes, not perform an invalid `usize` shift.
- **Assumptions:** Public parameters and a 64-bit `usize` in the concrete witness; integer `MapDomain` and `L01InfDistance` input space. This is not an audit of the ALP distribution or its DP proof.
- **Upstream:** [implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/alp/mod.rs), [tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/alp/test.rs), [FFI](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/alp/ffi.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `exponent_next_power_of_two` | correctness/projection-size-bounds | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Boundary analysis](../../../../../investigations/alp-projection-size-overflow.md) |
| `make_alp_state` | correctness/projection-size-bounds | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Constructor witness](../../../../../investigations/alp-projection-size-overflow.md) |
| `make_alp_state_with_hashers` | correctness/nonfinite-constructor-guards | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Nonfinite parameter panic](#nonfinite-parameter-panic) |

## Analysis

**Finding:** The `make_alp_state` constructor computes `exp = exponent_next_power_of_two(size_factor * total_limit * scale / alpha)` and passes `1 << exp` as `projection_size: usize`. For `total_limit = 1_000_000_000_000_000_000u64`, `value_limit = 4u64`, `scale = 1.0`, `alpha = 4`, `size_factor = 50`, the sizing numerator is `12_500_000_000_000_000_000`, between `2^63` and `2^64`. Hence `exp == 64`. An unchecked `1 << 64` cannot represent the intended projection size in 64-bit `usize`, and in a checked-overflow build this panics rather than returning an error. `m` (number of hash functions) is only `1`, so no earlier large allocation prevents reaching the shift. The FFI entrypoint exposes this constructor for supported integer types.

**Executed:** A Python 3 binary64/integer model independently reproduced the `exp == 64` result, including nearby `total_limit` values `7e17` (exponent 63) and `8e17` (exponent 64). The resulting integer is within `u64`, so the witness does not require saturating casts. The audit validator and eight validator unit tests passed locally. **Not executed:** compiled OpenDP, FFI, or a Rust debug/release boundary regression.

**Impact:** Low-severity constructor availability/robustness issue from public parameters, not a demonstrated privacy leak or inaccurate DP map. A requested `2^64`-sized projection cannot be supported, so fallible parameter rejection is appropriate. Existing upstream tests only check exponents for inputs 1, 2, 3, and 7. Checks of audit/upstream issues and PRs found no equivalent tracked fix; no new issue was created in this run.

### Nonfinite parameter panic

**Finding:** `make_alp_state_with_hashers` validates `scale` and `alpha` using `is_sign_negative() || is_zero()` but not `is_finite()`. A positive-sign NaN, explicitly represented by `f64::from_bits(0x7ff8_0000_0000_0000)`, passes the check. `are_parameters_invalid(alpha, scale)` subsequently invokes `FBig::<Zero>::inf_cast(scale).expect("impl is infallible")` and the analogous `alpha` conversion. The [fallible `FBig` cast](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/cast/mod.rs) wraps `FBig::try_from(v)` and returns `FailedCast` for a NaN, so `expect` panics instead of returning `Err`.

**Minimal proposed Rust regression (not compiled):** `make_alp_state_with_hashers::<u32, u32>(MapDomain::default(), L01InfDistance::default(), f64::from_bits(0x7ff8_0000_0000_0000), 1.0, 1, vec![])`. An `alpha` NaN analog reaches the second `expect`. The separate size-overflow finding is avoided by `projection_size = 1`.

**Executed:** Python 3 checked that the specified NaN has a positive sign and is not zero. **Not executed:** Compiled OpenDP, Rust `catch_unwind` regression, or FFI. The finding is tracked in [candidate issue #5](https://github.com/opendp/opendp-audit/issues/5) (upstream disposition `Unreported`), distinct from [upstream ALP privacy-rounding issue #3249](https://github.com/opendp/opendp/issues/3249).

**Impact:** Low-severity constructor availability / public-parameter validation. This does **not** demonstrate a data-dependent panic or privacy breach. The high-level `make_alp_queryable` was not shown to reach the same NaN `expect` path.

## Next checks

Execute a native Rust checked-overflow regression; validate `exp < usize::BITS` before shifting; reject overflow through `Fallible`; verify boundary behavior with debug/release builds and 32-bit `usize` targets. See [investigation](../../../../../investigations/alp-projection-size-overflow.md).

- For [candidate #5](https://github.com/opendp/opendp-audit/issues/5), add a regression for positive-sign NaN `scale` and `alpha` and reject nonfinite values before `are_parameters_invalid`.
