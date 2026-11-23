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

**Candidate, source-supported availability defect; upstream disposition: Pending PR.** Final duplicate checks found open draft [upstream PR #2868](https://github.com/opendp/opendp/pull/2868), which replaces `cdp_delta` with `zcdp_delta` and explicitly catches `ErrorVariant::Overflow` when constructing the alpha upper bracket, substituting the valid `alpha=2` fallback. The PR is **not merged** into upstream `main`, so this is not fixed on the reviewed revision. The PR includes a related high-epsilon alpha-heuristic overflow regression but not the exact small-rho witness. No new audit or upstream issue was opened because a fix PR already exists. Historical [issue #1997](https://github.com/opendp/opendp/issues/1997) is a closed, distinct rounding-underflow case; [PR #2849](https://github.com/opendp/opendp/pull/2849) is closed unmerged.

## Unresolved questions

- Execute the exact witness against compiled upstream `main` and draft PR #2868, capturing the error variant before the fix and the conservative `delta` after it.
- Add a regression for the small-rho boundary; PR #2868 covers a different high-epsilon overflow case.
- Recheck the merged implementation and the relevance to realistic mechanism parameters; do not file a duplicate issue while the fix PR is pending.
