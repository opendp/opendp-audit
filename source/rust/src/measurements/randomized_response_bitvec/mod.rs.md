---
schema_version: 1
source: rust/src/measurements/randomized_response_bitvec/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/randomized_response_bitvec/mod.rs`

## Scope and assumptions

- **Audit scope:** The exactly-`f = 1.0` parameter boundary shared by the bit-vector randomizer and its frequency debiasing helper. This is a narrowly scoped numerical-correctness review, not a complete privacy proof.
- **Invariants:** Every accepted call to the debiasing helper should either provide a meaningful finite frequency estimate or reject a parameter at which the estimate is not identifiable. The randomizer itself may legitimately accept `f = 1` to provide zero privacy loss.
- **Assumptions:** Nonempty vectors of consistent length, one finite `f64` parameter, ordinary Rust/IEEE-754 floating-point division, and the current upstream `main` revision `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`.
- **Pinned source:** [Randomizer and parameter check](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/randomized_response_bitvec/mod.rs#L21-L83); [debiasing check and calculation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/randomized_response_bitvec/mod.rs#L86-L124); [FFI delegation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/randomized_response_bitvec/ffi.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::randomized_response_bitvec::make_randomized_response_bitvec` | correctness/f-one-boundary | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Endpoint behavior](#randomizer-at-f--1) |
| `measurements::randomized_response_bitvec::debias_randomized_response_bitvec` | correctness/f-one-boundary | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Nonfinite estimator](#debiasing-at-f--1) |

## Analysis

### Randomizer at `f = 1`

The constructor rejects only `f <= 0` or `f > 1`, so `f = 1` is allowed. It XORs each input bit with an independent Bernoulli sample at `f / 2 = 0.5`. Conditional on successful sampling, each released bit is uniform regardless of its corresponding input bit. The stated privacy cost `2m * ln((2-f)/f)` is zero at `f = 1` for finite `m`. This endpoint is intentional and no privacy violation was identified *within this endpoint review*.

The constructor now requires both a maximum weight and a fixed vector size. The previous variable-length disclosure is separately documented in [upstream issue #2930](https://github.com/opendp/opendp/issues/2930), resolved by [merged PR #3079](https://github.com/opendp/opendp/pull/3079). This audit does not reopen that finding.

### Debiasing at `f = 1`

**Finding (numerical correctness / utility, low severity):** The postprocessor independently accepts `f = 1` (lines 96-102) but computes `(y_i - (f / 2) * n) / (1 - f)` (lines 120-123). The denominator is exactly zero. For the minimal valid input of one one-bit answer containing `true`, `n = 1`, `y_0 = 1`, and the expression is `0.5 / 0.0`. Under Rust `f64` semantics, the function returns `Ok(vec![+infinity])` rather than rejecting the impossible estimation request. An all-`false` answer analogously gives negative infinity; some balanced samples give NaN.

This is not only a division-by-zero presentation problem. The expected released count per bit is `E[Y_i] = (1-f) * N_i + (f/2) * n`. At `f = 1` the coefficient of the unknown true count `N_i` vanishes, so no unbiased inverse exists. A targeted fix would reject `f = 1` **in the debiaser**, while preserving that valid zero-privacy endpoint in the randomizer, and document the estimator's domain as `0 < f < 1`.

The [FFI postprocessor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/randomized_response_bitvec/ffi.rs#L31-L41) forwards `f` without an additional check, making the Rust behavior reachable through the exposed binding. The scope of language-specific handling was not execution-tested.

**Verification:** This is direct source-level control-flow and floating-point arithmetic analysis, not an executed OpenDP regression test. The upstream Rust package was not built in this session. Searches for upstream bit-vector and debiasing issues/PRs found no equivalent report about the `f = 1` estimator singularity; that search is not proof of absence.

## Next checks

- Run a compiled Rust regression calling `debias_randomized_response_bitvec(vec![bitvec![u8, Lsb0; 1]], 1.0)`, then assert an error after the intended input-validation fix.
- Check and update Python/R-facing documentation for the debiaser's `f < 1` precondition.
- Separately assess nonfinite `f`, near-one conditioning, and end-to-end privacy for the constructor; none is included in the `Audited` status above.
- Candidate defect is documented here only. No GitHub issue or upstream change was created.
