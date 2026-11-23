---
schema_version: 1
source: rust/src/combinators/measure_cast/zCDP_to_approxDP/mod.rs
updated: 2026-11-22
---

# `rust/src/combinators/measure_cast/zCDP_to_approxDP/mod.rs`

## Scope and assumptions

Review the non-deprecated **wrapper/dispatch only** at upstream `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`: carrying the original randomized function and input space through `make_zCDP_to_approxDP`, and constructing `PrivacyProfile` from `ZeroConcentratedDivergence` (or `Approximate<ZeroConcentratedDivergence>`). **The mathematical correctness, numerical conservatism, and exceptional behavior of `cdp_delta` are not newly audited here**; they are substantial independent dependencies.

- [Constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/measure_cast/zCDP_to_approxDP/mod.rs), [cdp_delta source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/measure_cast/zCDP_to_approxDP/cdp_delta/mod.rs), [existing native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/measure_cast/zCDP_to_approxDP/test.rs).
- Related [zCDP small-ρ overflow investigation](../../../../../../investigations/zcdp-small-rho-bound-overflow.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `combinators::measure_cast::zCDP_to_approxDP::make_zCDP_to_approxDP` | correctness/measurement-repackaging | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Dispatch trace](#dispatch-trace) |
| `combinators::measure_cast::zCDP_to_approxDP::ConcentratedMeasure::convert` | privacy/profile-conversion | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Dispatch trace](#dispatch-trace); dependent on `cdp_delta` |

## Analysis

### Dispatch trace

`make_zCDP_to_approxDP` clones the source input domain, metric and function, changes only the output privacy measure, and evaluates the original privacy map before invoking `MO::convert`. The zCDP implementation captures a public `ρ` and produces `PrivacyProfile::new(move |ε| cdp_delta(ρ, ε))`. The approximate-zCDP implementation produces a pair `(profile, δ)`, retaining the original `δ` without inadvertent discarding. Errors from the source map or conversion propagate.

This is **not** a fresh proof that `cdp_delta` always produces conservative profiles under floating-point rounding, nor that all profile inversion paths are numerically complete. See the separate [small-ρ investigation](../../../../../../investigations/zcdp-small-rho-bound-overflow.md) and [PrivacyProfile issue #19](https://github.com/opendp/opendp-audit/issues/19). Upstream tests were inspected but not run.

**Finding:** No incorrect repackaging or missing slack term found in the examined source; the full privacy guarantee remains **Partial**.

## Next checks

- Check `cdp_delta` in compiled Rust at numerical extremes, without duplicating existing audit work.
- Test source-map failure propagation and approximate slack retention through FFI.
