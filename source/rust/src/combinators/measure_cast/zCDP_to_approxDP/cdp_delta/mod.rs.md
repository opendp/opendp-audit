---
schema_version: 1
source: rust/src/combinators/measure_cast/zCDP_to_approxDP/cdp_delta/mod.rs
updated: 2026-11-22
---

# `rust/src/combinators/measure_cast/zCDP_to_approxDP/cdp_delta/mod.rs`

## Scope and assumptions

- **Audit scope:** Initialization of the optimizer's `a_max` upper bound in `cdp_delta` for strictly positive, finite, very small `rho` and finite nonnegative `eps`, and whether evaluation can proceed when the ideal search bound exceeds the representable `f64` range.
- **Property:** `correctness/finite-parameter-evaluation`. A conservative approximate-DP profile can be formed at the chosen input even when the search bound is too large for `f64`; failure is a numerical availability concern rather than a privacy-bound underestimation.
- **Assumptions:** Directed `InfDiv` on `f64` uses arbitrary-precision intermediate arithmetic followed by conversion to `f64`, which rejects an overflowing finite result; `rho` and `eps` are valid nonnegative finite `f64` values. The `cdp_delta` proof explicitly permits returning errors, so this is *not* a violation of its formal safety postcondition.
- **Source links:** [Reviewed `cdp_delta`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/measure_cast/zCDP_to_approxDP/cdp_delta/mod.rs), [directed arithmetic](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/arithmetic/mod.rs), [concentrated-measure conversion](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/measure_cast/zCDP_to_approxDP/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `cdp_delta::cdp_delta` | correctness/finite-parameter-evaluation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file analysis](../../../../../../../investigations/zcdp-small-rho-bound-overflow.md) |

## Analysis

### `cdp_delta::cdp_delta` — `correctness/finite-parameter-evaluation`

**Conclusion:** For a finite positive subnormal input such as `rho = 1e-310` and `eps = 1.0`, the upper-bound computation `(eps + 1) / (2 * rho) + 2` is approximately `1e310`, outside finite `f64`. The `InfDiv` implementation converts the arbitrary-precision result back to `f64` and rejects a nonrepresentable finite result. Consequently, this path returns an overflow instead of a conservative `delta`. The function's stated proof contract allows errors: the defect classification is low-severity numerical availability, not privacy unsoundness.

**Evidence:** The direct source has no fallback once the upper bound overflows, and its subsequent search is bypassed by `?`. A valid non-optimal alpha exists: `alpha = 2` produces `exp(-1)/4 ≈ 0.09196986029286057` for this rho and epsilon. A local Python standard-library check reproduced the native binary64 bound overflow and calculated the finite-alpha value. No OpenDP Rust binary or unit test was executed.

**Limitations:** Other alpha-search regimes, conservative rounding of the final certificate, and the actual upstream Rust error variant remain untested. The scope does not claim universal completion for every finite input. See [investigation](../../../../../../../investigations/zcdp-small-rho-bound-overflow.md).

**Related:** Open draft [upstream PR #2868](https://github.com/opendp/opendp/pull/2868) replaces this converter and explicitly catches `ErrorVariant::Overflow` in the alpha upper-bound heuristic, falling back to `alpha=2`. This is a **pending fix**, not merged into reviewed `main`. Historical upstream [issue #1997](https://github.com/opendp/opendp/issues/1997) concerns a different underflow defect; [PR #2849](https://github.com/opendp/opendp/pull/2849) was closed unmerged.

## Next checks

Run the exact `rho=1e-310, eps=1.0` witness on current `main` and on draft PR #2868, checking that the fallback remains conservative. The PR tests a related overflow regime, but the inspected diff does not add this exact small-rho regression. Re-audit after merge; do not create a duplicate issue while the fix PR is open.
