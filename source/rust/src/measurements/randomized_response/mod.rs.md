---
schema_version: 1
source: rust/src/measurements/randomized_response/mod.rs
updated: 2026-11-22
---

# `rust/src/measurements/randomized_response/mod.rs`

## Scope and assumptions

- **Audit scope:** The lower probability boundary of `make_randomized_response<T>` and the resulting max-divergence privacy map for distinct categorical inputs. The boolean constructor, FFI, and timing side channels were not audited.
- **Invariant:** For every accepted probability and adjacent inputs under `DiscreteDistance`, `map(1)` must upper-bound the output distributions' max-divergence. In particular, an advertised epsilon of zero requires identical distributions.
- **Assumptions:** `sample_bernoulli_float` returns Bernoulli(`prob`) and `sample_uniform_uint_below` samples uniformly, conditional on successful entropy acquisition. Rust `f64` has IEEE-754 binary64 semantics. The outward-rounding helpers obey their documented contracts and preserve exactly representable results.
- **Reviewed source:** [categorical constructor at exact upstream commit](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/randomized_response/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::randomized_response::make_randomized_response` | privacy/lower-bound-calibration | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Boundary counterexample and pending upstream fix](../../../../../investigations/randomized-response-reciprocal-rounding.md) |

## Analysis

### `measurements::randomized_response::make_randomized_response` — `privacy/lower-bound-calibration`

**Conclusion:** The checked boundary violates the stated invariant on the reviewed `main` commit. For three categories and `prob = 1.0 / 3.0`, the constructor accepts a binary64 value below mathematical `1/3` and computes a zero privacy constant, despite a strictly positive exact divergence for two distinct in-set inputs. This is a numerical accounting discrepancy of approximately `8.33e-17`, not evidence of a material practical privacy compromise.

**Evidence:** The [investigation](../../../../../investigations/randomized-response-reciprocal-rounding.md) contains the exact rational counterexample, expected directed-rounding trace, a locally executed Python arithmetic check, and links to the relevant samplers and arithmetic implementations. A draft [upstream PR #3257](https://github.com/opendp/opendp/pull/3257) already addresses this exact boundary with direct uniform sampling and a regression test. The issue is therefore **pending upstream fix**, not a newly discovered unreported defect.

**Limitations:** This audit verifies one numerical boundary and its distributional consequence under the sampler contracts; it does not establish the entire constructor's privacy behavior. No OpenDP Rust build or runtime `Measurement::map` invocation was executed. The pending PR was inspected, not tested locally. No GitHub audit-task issue was opened, so this work has no exclusive lease.

## Next checks

- Execute a Rust regression on the reviewed `main` revision to confirm `map(&1)` is exactly zero while the correct bound is positive.
- Verify that PR #3257 or its eventual replacement merges to `main`, preserves the uniform boundary behavior, and passes the upstream test suite.
- Re-review this coverage row after the fix merges; do not mark it fixed based on the open PR alone.
