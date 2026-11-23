---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Partial
---

# Fixed-delta privacy budget: existing slack and profile inversion

## Invariant and threat model

The conversion from profile privacy guarantees to approximate-DP must not silently spend more total failure probability than requested. For a source `(curve, delta_0)` and target `delta`, if the inverse chooses `epsilon` with `curve(epsilon) <= r`, then it is sufficient that `delta_0 + r <= delta`. This is a **privacy-soundness** condition, not merely a utility check. Preconditions are that the source privacy profile is valid and nonincreasing, and the fixed delta parameter represents failure probability in `[0,1]`.

## Affected symbols and source audits

- [`make_fix_delta` and both `FixDeltaMeasure::fix_delta` implementations](../source/rust/src/combinators/fix_delta/mod.rs.md): [commit-pinned source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/fix_delta/mod.rs).
- [`PrivacyProfile::epsilon` and `epsilon_unchecked`](../source/rust/src/measures/mod.rs.md): [commit-pinned source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measures/mod.rs).
- [FFI dispatcher](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/fix_delta/ffi.rs), [directed arithmetic](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/arithmetic/mod.rs), and [`Measurement::with_map`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs).

## Reasoning and evidence

The direct `SmoothedMaxDivergence` branch returns `(profile.epsilon(delta), delta)`: the output is valid when inversion finds `epsilon` with `profile.delta(epsilon) <= delta`.

The `Approximate<SmoothedMaxDivergence>` branch uses `r = delta.neg_inf_sub(&delta_0)`. The operation is directed **down**, so its contract gives `r <= delta - delta_0` for finite exact inputs. If the inverted profile returns `epsilon` satisfying `curve.delta(epsilon) <= r`, then `curve.delta(epsilon) + delta_0 <= r + delta_0 <= delta` in real arithmetic. Returning the original total `delta` is correct. A negative residual is rejected by `PrivacyProfile::epsilon`, rather than interpreted as an available budget.

The inverse checks `delta` in `[0,1]`, uses an expanding high epsilon boundary with `delta(e_max) <= target`, and shrinks the bracket based on callback evaluations. On convergence it returns either `e_max` or `e_min` only when the profile value at `e_min` exactly equals the target. These choices appear conservative for valid monotone profiles; the full floating-point argument, possible callback behavior, and proof obligations remain open.

**Executed checks:** Using Python 3 standard library `fractions.Fraction`, `math.nextafter`, and deterministic pseudo-random input pairs, a model of downward-rounded binary64 subtraction passed 10,000 ordered `(delta, delta_0)` pairs: for each pair `r + delta_0 <= delta` in exact rationals. Five equality cases, including zero and the minimum positive subnormal, also passed. This tests the algebraic rounding obligation, **not OpenDP's compiled `InfSub` implementation**. Current upstream Rust tests `test_fix_delta_adp` and `test_fix_delta_approx_adp` already exercise normal direct and existing-slack paths. **Not executed:** compiled Rust tests, FFI binding tests, or a formal verification of callback monotonicity.

## Findings

**No new defect identified within the stated valid-profile assumptions.** This is a bounded negative finding, not a proof that arbitrary privacy-profile callbacks are safe. Open upstream [issue #2943](https://github.com/opendp/opendp/issues/2943) tracks formal proofs for both `make_fix_delta` and `PrivacyProfile::epsilon`; there is therefore no reason to open a duplicate proof issue. No upstream code was changed.

## Unresolved questions

- Establish a formal or property-based proof that `PrivacyProfile::epsilon` returns an epsilon with profile value no greater than target for every valid (potentially discontinuous) profile, including adjacent representable epsilon endpoints.
- Run Rust native regressions with `delta < delta_0`, `delta == delta_0`, near-zero residual, and extreme nonnegative parameters; verify error behavior across the FFI path.
- Recheck staleness if upstream introduces a different profile representation or changes directed subtraction semantics.
