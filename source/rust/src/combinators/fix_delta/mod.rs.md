---
schema_version: 1
source: rust/src/combinators/fix_delta/mod.rs
updated: 2026-11-22
---

# `rust/src/combinators/fix_delta/mod.rs`

## Scope and assumptions

- **Audit scope:** `make_fix_delta` and the `FixDeltaMeasure::fix_delta` implementations for `SmoothedMaxDivergence` and `Approximate<SmoothedMaxDivergence>`, limited to failure-probability accounting when converting a privacy profile to fixed approximate DP.
- **Invariant:** The fixed approximate-DP output `(epsilon, delta)` must not permit more privacy failure mass than the requested total `delta`. When the source output carries additional slack `delta_0`, the profile is inverted at a residual no greater than `delta - delta_0`.
- **Assumptions:** The input privacy map is a valid privacy guarantee; its profile is nonincreasing and conservative, and any source `delta_0` lies in `[0,1]`. The `PrivacyProfile::epsilon` inverse is correct under its own input assumptions. This review makes no claim about arbitrary user-supplied invalid profiles.
- **Source links:** [This file](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/fix_delta/mod.rs), [FFI dispatcher](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/fix_delta/ffi.rs), [profile inversion](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measures/mod.rs), [directed subtraction](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/arithmetic/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_fix_delta` | privacy/residual-delta-accounting | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file reasoning](../../../../../investigations/fix-delta-residual-accounting.md) |
| `SmoothedMaxDivergence::fix_delta` | privacy/residual-delta-accounting | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Simple profile path](#analysis) |
| `Approximate<SmoothedMaxDivergence>::fix_delta` | privacy/residual-delta-accounting | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Existing failure slack](#analysis) |

## Analysis

### Fixed-delta privacy map — `privacy/residual-delta-accounting`

**Conclusion:** No privacy-under-accounting defect was found within the stated valid-profile assumptions. The direct profile branch calls `profile.epsilon(delta)` and returns the requested `delta`. The approximate-profile branch computes `remaining_delta = delta.neg_inf_sub(&fixed_delta)`, then calls `curve.epsilon(remaining_delta)` and returns the *original* total `delta`, not the residual. Directed downward rounding makes the residual at most the exact available budget. The FFI wrapper dispatches only the two supported measures and preserves the same privacy-map semantics. `Measurement::with_map` retains the original function.

**Evidence:** The source's `neg_inf_sub` is specified to return a result no greater than exact subtraction (or error). Hence when `curve(epsilon) <= remaining_delta`, `fixed_delta + curve(epsilon) <= delta`. Invalid `delta`, negative residual, or non-comparable inputs propagate errors rather than producing a misleading output privacy map. The [investigation](../../../../../investigations/fix-delta-residual-accounting.md) gives the algebra and the local standard-library check (10,000 floating-point residual pairs, plus equality boundaries). Upstream tests cover direct and preexisting-slack paths but not the complete edge matrix.

**Limitations:** No compiled OpenDP Rust or FFI tests were run. The algebra assumes a valid input privacy map, a conservative profile, and the inversion guarantee. The separate inversion audit is [Partial](../../measures/mod.rs.md) because it does not establish arbitrary callback monotonicity or floating-point behavior for all curves. Formal proof work is tracked by [upstream issue #2943](https://github.com/opendp/opendp/issues/2943).

**Related:** No distinct confirmed defect; no candidate issue needed. The source file is not the subject of a known open corrective PR in the reviewed scope.

## Next checks

Prove the inverse's one-sided guarantee for valid profiles in the presence of rounded `delta` values; run compiled regression cases for equal budgets, insufficient residual, signed zero, and very small positive residual. Check the FFI wrapper's constructed-output measure under those cases.
