---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Partial
---

# zCDP-to-approximate-DP conversion: small-rho optimizer-bound overflow

## Invariant and threat model

For finite nonnegative inputs `rho` and `eps`, an approximation of the zCDP-to-approximate-DP conversion should be able to return a conservative finite `delta` whenever one is directly representable, without requiring its *optimal* alpha to be representable as a finite `f64`. The algorithm's formal proof permits `Err`; this review therefore tracks availability and usability, **not a demonstrated underestimate of privacy loss**.

## Affected symbols and source audits

- [`cdp_delta::cdp_delta`](../source/rust/src/combinators/measure_cast/zCDP_to_approxDP/cdp_delta/mod.rs.md) [upstream SHA](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/measure_cast/zCDP_to_approxDP/cdp_delta/mod.rs): constructs an upper optimizer bound before computing the profile.
- [`InfDiv` and `check_float_result`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/arithmetic/mod.rs): arbitrary-precision directed division converts back to `f64`, rejecting nonrepresentable finite results.
- [`ConcentratedMeasure::convert`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/measure_cast/zCDP_to_approxDP/mod.rs) and [`PrivacyProfile::delta`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measures/mod.rs): preserve the fallible conversion and expose it at profile evaluation time.

## Reasoning and evidence

For the minimal numeric witness `rho = 1e-310_f64`, `eps = 1.0_f64`, the initial upper bracket is `a_max = (eps+1)/(2*rho)+2`. Its mathematically finite value is approximately `1e310`, which exceeds `f64::MAX ≈ 1.7976931348623157e308`. The implementation evaluates this with `inf_add`, `neg_inf_mul`, `inf_div`, then `inf_add` and propagates errors with `?`. The relevant `InfDiv for f64` implementation evaluates a high-precision intermediate and converts to `f64`; overflow is an error. No clamp or fallback occurs in the caller.

A conservative alternative *exists*: using `alpha = 2`, the documented conversion bound equals `exp((alpha-1)*(alpha*rho-eps) + alpha*ln(1-1/alpha))/(alpha-1)`, approximately `exp(-1)/4 = 0.09196986029286057`. Thus the output could be safely nontrivial (though very loose), without evaluating an enormous search bracket.

**Actually executed:** Python 3 standard-library `decimal` and binary64 `float` calculations confirmed that the bound is finite in real arithmetic but overflows binary64, and evaluated the `alpha=2` expression. Tested several examples: `rho = 1e-310, eps = 0, 1, 10` all overflow the bracket while yielding finite `alpha=2` bounds. **Not executed:** OpenDP's compiled Rust implementation, OpenDP tests, or native numerical-error instrumentation; predicted propagation follows source code and arithmetic helper definitions.

This affects extreme, valid representable privacy parameters; it is a low-severity numerical robustness/availability candidate. The proof definition explicitly allows returning an error, so the mathematical privacy guarantee has not been contradicted.

## Findings

**Candidate, source-supported availability defect; upstream disposition: Unreported, subject to a final duplicate check.** Existing upstream [issue #1997](https://github.com/opendp/opendp/issues/1997) addressed a different directed-rounding underflow and is closed; [PR #2849](https://github.com/opendp/opendp/pull/2849) is closed and unmerged. Initial searches found no matching open issue in either repository and no open fix PR. No change to upstream OpenDP was made.

## Unresolved questions

- Execute the exact witness in compiled OpenDP and capture the error variant.
- Check whether an optimal search bracket can be replaced by a capped `f64` bound or explicit finite-alpha fallback while preserving conservative directed rounding and monotonicity.
- Add a regression checking that the extreme finite input produces a valid bound or a documented deliberate rejection; measure whether realistic mechanism parameters reach this range.
