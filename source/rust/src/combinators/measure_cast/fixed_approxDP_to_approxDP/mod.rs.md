---
schema_version: 1
source: rust/src/combinators/measure_cast/fixed_approxDP_to_approxDP/mod.rs
updated: 2026-11-22
---

# `rust/src/combinators/measure_cast/fixed_approxDP_to_approxDP/mod.rs`

## Scope and assumptions

Review the non-deprecated `make_fixed_approxDP_to_approxDP` conversion at upstream `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. Input measurement returns a **valid** fixed `(ε₀, δ₀)` approximate-DP bound for all adjacent input pairs, where `ε₀ ≥ 0` and `0 ≤ δ₀ ≤ 1`. This audit does not assume the cast validates invalid source privacy maps.

- Sources: [constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/measure_cast/fixed_approxDP_to_approxDP/mod.rs), [privacy profile definition](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measures/mod.rs), [upstream boundary test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/measure_cast/fixed_approxDP_to_approxDP/test.rs).
- [Finite reference model](../../../../../../investigations/measure-cast-privacy-boundary-model.md) and [tests](../../../../../../tools/tests/test_measure_cast_reference_model.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `combinators::measure_cast::fixed_approxDP_to_approxDP::make_fixed_approxDP_to_approxDP` | privacy/fixed-bound-to-profile | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Profile argument](#profile-argument); [finite model](../../../../../../investigations/measure-cast-privacy-boundary-model.md) |
| `combinators::measure_cast::fixed_approxDP_to_approxDP::fixed_approx_dp_privacy_curve` | correctness/step-boundary | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Profile argument](#profile-argument) |

## Analysis

### Profile argument

For a known `(ε₀, δ₀)` approximate-DP guarantee, the returned `PrivacyProfile` evaluates to `1` for `ε < ε₀` and `δ₀` for `ε ≥ ε₀`. For a smaller requested `ε`, `δ=1` is trivially sufficient because event probabilities are at most one. For `ε ≥ ε₀`, the inequality `P(S) ≤ exp(ε₀) Q(S)+δ₀` implies `P(S) ≤ exp(ε) Q(S)+δ₀`. Equality at `ε=ε₀` correctly returns `δ₀` rather than `1`.

The constructor copies the input measurement's function, input metadata, and privacy map into a new smoothed-max-divergence measurement without executing the mechanism or reinterpreting its output type. It wraps the source pair in a closure; any error evaluating the source map propagates.

An independent model enumerated finite binary and ternary distributions, computed the **optimal** approximate-DP `δ(ε)` by maximizing event residuals in both directions, and verified **29,970** step-curve inequalities at five fixed `ε₀` values and nine query `ε` values. No counterexamples. This tests the deterministic mathematical conversion, **not** compiled Rust. Upstream Rust tests cover `ε₀` and neighboring binary64 values; inspected, not run.

**Finding:** The profile conversion is sound for valid source parameters. No new defect identified in this bounded property. Invalid source `δ₀`/NaN values and `PrivacyProfile::epsilon` inversion are not certified by this review; related inversion limits are separately tracked in [audit issue #19](https://github.com/opendp/opendp-audit/issues/19).

## Next checks

- Run native Rust fixed-profile boundary tests and test custom-source-map failures.
- Audit profile inversion separately from forward `delta(ε)` evaluation; the latter is the guarantee assessed here.
