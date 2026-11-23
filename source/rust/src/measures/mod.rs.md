---
schema_version: 1
source: rust/src/measures/mod.rs
updated: 2026-11-22
---

# `rust/src/measures/mod.rs`

## Scope and assumptions

- **Audit scope:** `PrivacyProfile::epsilon`, `epsilon_unchecked`, and `delta` insofar as they are used by `make_fix_delta`; no review of other privacy measures or curve constructors.
- **Invariant:** Given a valid nonincreasing conservative profile and a target `delta` in `[0,1]`, the inverse returns an `epsilon` whose profile value does not exceed that target, or errors. It must never claim a lower epsilon without a valid profile bound.
- **Assumptions:** The privacy-profile callback is defined for finite nonnegative inputs and has the mathematical properties expected of a privacy profile. This code cannot verify those properties for arbitrary user-provided callbacks.
- **Source:** [Commit-pinned profile implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measures/mod.rs), [caller](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/fix_delta/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `PrivacyProfile::epsilon` | privacy/profile-inversion | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Inverse analysis](../../../../investigations/fix-delta-residual-accounting.md) |
| `PrivacyProfile::epsilon_unchecked` | privacy/profile-inversion | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Bracket and termination](../../../../investigations/fix-delta-residual-accounting.md) |

## Analysis

### Profile inversion — `privacy/profile-inversion`

**Conclusion:** Under a valid nonincreasing profile, the bracketing/bisection logic is directionally conservative. The method rejects negative or out-of-range `delta`, immediately returns zero for `delta == 1`, and otherwise searches a nonnegative epsilon interval. When the midpoint is exactly the target, it moves the upper boundary down; on convergence, it chooses the upper boundary unless the lower endpoint already has exactly the target profile value. If the expanding upper bracket overflows, it returns infinity, a conservative outcome for finite epsilon.

**Evidence:** `epsilon_unchecked` starts with `e_min=0`, `e_max=2`, expands the high bracket while `profile(e_max)>target`, then bisects based on `partial_cmp`. Under the assumptions, values on the high boundary are safe and values on the low boundary are either unsafe or already meet the target. It rejects incomparable midpoint results. The [investigation](../../../../investigations/fix-delta-residual-accounting.md) analyzes this in the context of `make_fix_delta`.

**Limitations:** Marked **Partial** because no native tests, adversarial valid-profile callbacks, or independent formal proof of the endpoint selection and floating-point bisection were completed. The method evaluates arbitrary callback code; valid monotonicity and conservativeness are assumed rather than enforced. The associated proof is an open item in [upstream issue #2943](https://github.com/opendp/opendp/issues/2943).

## Next checks

Validate boundary behavior for (i) profile already below target at zero, (ii) a discontinuous monotone profile, (iii) a constant profile, (iv) a profile with nonfinite evaluation, and (v) near-machine-precision adjacent epsilon values. Confirm the returned endpoint's profile certificate is never above target when the callback is valid.
