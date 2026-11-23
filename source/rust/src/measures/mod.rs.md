---
schema_version: 1
source: rust/src/measures/mod.rs
updated: 2026-11-22
---

# `rust/src/measures/mod.rs`

## Scope and assumptions

- **Audit scope:** `PrivacyProfile::epsilon`, `epsilon_unchecked`, and `delta` as used by `make_fix_delta`; specifically, representable-endpoint safety for monotone profiles and extreme upper-bracket expansion. No review of other privacy measures or curve constructors.
- **Invariants:** For a valid nonincreasing conservative profile and target `delta` in `[0,1]`, a returned *finite* `epsilon` must have a profile value no greater than the target. Where a feasible finite bound is available within the algorithm's search bracket, the result should be the smallest representable safe epsilon. Separately, returning infinity for a feasible finite bound loses utility but is conservative for privacy.
- **Assumptions:** The privacy-profile callback is defined for finite nonnegative inputs and has the mathematical properties expected of a privacy profile. This code cannot verify those properties for arbitrary user-provided callbacks.
- **Source:** [Commit-pinned profile implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measures/mod.rs), [caller](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/fix_delta/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `PrivacyProfile::epsilon` | privacy/profile-inversion | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Inverse analysis](../../../../investigations/fix-delta-residual-accounting.md) |
| `PrivacyProfile::epsilon_unchecked` | privacy/profile-inversion | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Bracket and termination](../../../../investigations/fix-delta-residual-accounting.md) |
| `PrivacyProfile::epsilon_unchecked` | correctness/finite-inverse-availability | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Extreme bracket analysis](#extreme-bracket-availability) |

## Analysis

### Profile inversion — `privacy/profile-inversion`

**Conclusion:** Under a valid nonincreasing profile, the bracketing/bisection logic is directionally conservative. The method rejects negative or out-of-range `delta`, immediately returns zero for `delta == 1`, and otherwise searches a nonnegative epsilon interval. When the midpoint is exactly the target, it moves the upper boundary down; on convergence, it chooses the upper boundary unless the lower endpoint already has exactly the target profile value. If the expanding upper bracket overflows, it returns infinity, a conservative outcome for finite epsilon.

**Evidence:** `epsilon_unchecked` starts with `e_min=0`, `e_max=2`, expands the high bracket while `profile(e_max)>target`, then bisects based on `partial_cmp`. Under the assumptions, values on the high boundary are safe and values on the low boundary are either unsafe or already meet the target. It rejects incomparable midpoint results. The [investigation](../../../../investigations/fix-delta-residual-accounting.md) analyzes this in the context of `make_fix_delta`.

**Executed source-level checks:** A Python binary64 translation of this exact search/control flow ran 30,249 deterministic cases: 210 step-profile boundaries (including discontinuities and adjacent subnormals), 30 constant-profile cases (15 feasible, 15 legitimately infinite), 20,000 monotone piecewise-constant profiles, 10,000 exponential profiles, four invalid-target cases, and five extreme-threshold cases. All assertions passed. Every finite result checked against a monotone profile was safe and had no smaller *representable* safe predecessor. The 4 extreme thresholds above the expansion cap were deliberately expected to return infinity rather than the available finite epsilon. This was **not** an execution of the compiled OpenDP code.

**Limitations:** The profile-inversion rows remain **Partial**: the local test translates Rust's binary64 control flow but does not prove behavior for all valid callbacks, execute OpenDP's compiled implementation, or verify the framework's formal proof. Callback monotonicity and conservativeness remain assumptions. [Upstream issue #2943](https://github.com/opendp/opendp/issues/2943) tracks the outstanding `PrivacyProfile::epsilon` proof.

### Extreme bracket availability

**Conclusion:** An extremely high but finite safe epsilon is not always returned. `epsilon_unchecked` expands the initial high bracket by repeatedly squaring it: `2, 4, 16, ... , 2^512` (approximately `1.3407807929942597e154`), followed by overflow to `+inf`. At that point it returns `+inf` immediately without checking larger finite epsilon candidates. This is a **utility/availability limitation**, not a privacy underestimate.

**Minimal source-level witness:** Let the valid, nonincreasing user-provided profile be `p(epsilon) = 1.0` for `epsilon < 2e154`, and `p(epsilon) = 0.0` otherwise. For `target_delta = 0.0`, the smallest safe representable epsilon is `2e154` (finite), but the source algorithm returns `f64::INFINITY`. The translated algorithm reproduced this result; thresholds `1e155`, `1e200`, and `1e300` behaved similarly. At `1e154`, it returned the expected finite epsilon.

**Impact and disposition:** Extremely low practical severity. Epsilon in this range is already far beyond ordinary useful privacy budgets; no privacy unsoundness was observed. Searches of both repositories' issues and upstream PRs found no targeted fix, while the broader inverse-proof obligation is already tracked in [OpenDP issue #2943](https://github.com/opendp/opendp/issues/2943). No new issue was opened because this only loses utility at astronomical epsilon.

## Next checks

Run compiled Rust property-based regressions against discontinuous valid profiles and adjacent finite epsilon values, including a threshold above `2^512`; test whether a bounded finite-search fallback would preserve the inversion certificate. Also test error propagation for NaN/nonfinite callback results; those were outside the monotone-profile checks. Revisit the status after the formal profile inversion proof is completed.
