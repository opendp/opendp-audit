---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Float threshold mechanism releases values equal to its public threshold

## Invariant and threat model

The public non-deprecated `make_laplace_threshold` and `make_gaussian_threshold` constructors promise to release noisy values strictly beyond the threshold. The integer threshold filter enforces this invariant before float postprocessing, but the final nearest-representable-float projection is many-to-one. This audit asks whether **returned numeric values** still satisfy the strict comparison. It does not assert that the extra outputs leak information beyond the advertised differential-privacy accounting.

## Affected symbols and source audits

- [Float threshold adapter source audit](../source/rust/src/measurements/noise_threshold/nature/float/mod.rs.md).
- [Integer-stage core source audit](../source/rust/src/measurements/noise_threshold/mod.rs.md).
- [Float adapter and `then_deintegerize_hashmap`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/nature/float/mod.rs), [`ZExpFamily<P>` thresholding](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/mod.rs), [`CastInternalRational` nearest-float rounding contract](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/cast/mod.rs).
- [Laplace API contract](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/laplace/mod.rs), [Gaussian API contract](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/gaussian/mod.rs).
- **Candidate defect:** [audit issue #44](https://github.com/opendp/opendp-audit/issues/44).

## Reasoning and evidence

### Deterministic and positive-probability witness

Consider one-element input map `{"key": 1.0}`, public threshold `1.0`, `k=-54`, `scale=2^-54`, value type `f64`, and either Laplace (`P=1`) or Gaussian (`P=2`) noise. Both input value and public threshold are representable finite floats; the scale is positive and the integerized scale is exactly `1`. All constructors are in the documented supported, non-deprecated paths. Select the legitimate discrete-noise event `Z=+1`.

| Stage | Exact value or condition | Result |
| --- | --- | --- |
| Float-to-grid conversion | `1.0 * 2^54` | Integer `2^54` |
| Threshold conversion | `floor(1.0 * 2^54)` | Integer `2^54` |
| Integerized noise | `2^54 + Z` where `Z=1` | Integer `2^54+1` |
| Strict core filtering | `2^54+1 > 2^54` | **Retained** |
| Deintegerization before float cast | `(2^54+1)*2^-54` | Rational `1+2^-54` |
| Nearest binary64 conversion | `1+2^-54` is less than halfway to `1+2^-52` | **Returned 1.0** |

The returned value **equals** the public threshold. There is no reliance on ties or an ambiguous rounding convention: `2^-54 < 2^-53`. For the discrete Laplace mechanism with integerized scale 1, the probability of this specific event is approximately `0.17000340156854793`. The discrete Gaussian at the same positive finite scale likewise assigns positive probability to `Z=1`.

Two additional minimal witnesses:

- `f32`: threshold `1.0f32`, `k=-26`, `scale=2^-26`, `Z=1`; the next representable `f32` above `1.0` is `1+2^-23`, so `1+2^-26` rounds down to `1.0f32`.
- `f64` without a fine grid: threshold `2^54`, `k=0`, `scale=1.0`, `Z=1`; the exact retained integer `2^54+1` rounds to `2^54` in binary64.

### Reproducible independent checks

[Python test harness](../tools/tests/test_float_threshold_postrounding.py) uses exact `fractions.Fraction` arithmetic to mirror the grid rounding, floor of threshold, strict integer comparison, and native output cast. It verifies **522** power-of-two threshold/scale witnesses across `f64` exponents `-200..200` and `f32` exponents `-60..60`, and checks the specific `1.0` and `2^54` witnesses plus control cases where output is observably above threshold. All **six** tests passed locally under Python 3 before publication.

[Standalone Rust test harness](../tools/tests/float_threshold_postrounding.rs) exercises native casts of the same accepted integer numerators, verifying that integer support decisions can be reversed by floating-point rounding. This is not a compiled OpenDP integration test: no noise sampler was executed, and the Rust test models the last cast rather than linking Dashu `RBig`. The exact-rational witness is independent of RNG behavior conditional on `Z=+1`.

### Privacy interpretation and upstream disposition

This is a **functional output-contract defect**, not an established DP violation. Filtering after noisy integer release and conversion are both deterministic postprocessing. Enforcing a second strict filter on the returned float values can remove aliases without violating the preexisting privacy guarantee. Alternatively, the API can explicitly say that the threshold applies to the exact pre-rounded noisy grid value rather than the returned float.

Targeted issue/PR searches in upstream `opendp/opendp` and `opendp/opendp-audit` found no report or fix for this aliasing defect. Existing [audit issue #3](https://github.com/opendp/opendp-audit/issues/3) reports a distinct rare-release **privacy-delta precision floor**, not a returned-value threshold mismatch.

## Findings

**Confirmed conditional output counterexample:** With positive-probability discrete noise increment `+1`, the mechanism retains an integerized noisy value strictly above the integer threshold but returns the original threshold after nearest-float rounding. Tracked in [issue #44](https://github.com/opendp/opendp-audit/issues/44). The source-level cast/threshold ordering establishes the discrepancy; complete native OpenDP execution is outstanding. Broader privacy and stability coverage remains **Partial**.

## Unresolved questions

- Construct an OpenDP integration test with deterministic noise injection if supported, or a high-probability version of the witness for a statistical integration regression.
- Decide whether the public threshold guarantee is about returned values (as currently worded) or pre-rounded values; either enforce the returned-value predicate or clarify the contract.
- Review signed negative threshold handling separately for integer-valued releases; this witness applies to accepted nonnegative float thresholds.
