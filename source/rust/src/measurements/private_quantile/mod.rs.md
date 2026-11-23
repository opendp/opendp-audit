---
schema_version: 1
source: rust/src/measurements/private_quantile/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/private_quantile/mod.rs`

## Scope and assumptions

- **Audit scope:** Candidate validation and output membership for `make_private_quantile`, plus a bounded inspection of delegated `alpha` and noise-scale validation.
- **Invariants:** (1) Candidate lists that are empty, contain duplicates, or contain NaN do not construct a measurement. (2) A successfully invoked measurement yields an element of the supplied candidate list rather than an out-of-bounds index. (3) Invalid `alpha` and noise-scale arguments do not bypass downstream constructor guards.
- **Assumptions:** Supported numeric `T: Number` (integer and float) and `MI: UnboundedMetric`, `MO: TopKMeasure`; ordinary Rust `f32`/`f64` comparisons; successful execution of the downstream mechanism. These statements concern constructor-side correctness and output membership, **not** a complete differential-privacy proof.
- **Pinned code:** [Private quantile constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/private_quantile/mod.rs), [candidate and alpha guards](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/quantile_score_candidates/mod.rs), [Top-K scale and indexing](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noisy_top_k/mod.rs), and [float null checking](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/operations/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::private_quantile::make_private_quantile` | correctness/candidate-validation | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Candidate rejection](#candidate-rejection) |
| `measurements::private_quantile::make_private_quantile` | correctness/output-membership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Output index bounds](#output-index-bounds) |
| `measurements::private_quantile::make_private_quantile` | correctness/parameter-validation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Parameter delegation](#parameter-delegation) |

## Analysis

### Candidate rejection

The constructor checks `candidates.iter().position(|c| c.is_null())` before sorting and returns a construction error if any candidate is null. For `f32`/`f64`, the `CheckNull` implementation maps `is_null` to `is_nan`, so NaN cannot reach `partial_cmp(...).expect("candidates are not NaN")`. For supported non-NaN numeric values, comparison is defined, including infinities.

The constructor then sorts the candidate vector and delegates to `make_quantile_score_candidates`, whose `check_candidates` rejects empty vectors and any adjacent pair not strictly increasing. Because the input is sorted, repeated values become adjacent and are rejected. This also excludes an empty candidate list despite the absence of an explicit check in the outer constructor.

**Assessment:** These malformed candidate classes are rejected along the inspected constructor path. No candidate-validation defect was identified within these cases.

### Output index bounds

After validation, `check_candidates` ensures at least one candidate. The scoring transformation builds a vector with exactly one score per candidate. `make_noisy_max(..., k = 1, ...)` delegates to `make_noisy_top_k`, whose selection loop selects indices from the existing score vector and returns zero or one index. With at least one score, a successful `k = 1` invocation selects exactly one index from `[0, candidates.len())`. The final `Function::new(move |idx| candidates[*idx])` therefore indexes within the stored candidates on a successful invocation.

**Assessment:** The output is a member of the supplied candidate set (after sorting) on successful execution. Random sampling failures may still return an error and were not exercised here.

### Parameter delegation

The outer constructor does not validate `alpha` or `scale` directly. `score_candidates_constants`, called for both denominator calculation and construction of the scorer, rejects `alpha` outside the inclusive interval `[0, 1]` (including NaN). It checks integer scoring bounds.

The effective noise scale is `scale * denominator as f64`. `make_noisy_max` delegates to `make_noisy_top_k`, where the effective scale must be finite and not sign-negative; nonfinite, negative, and overflowed values are rejected. The scorer also requires an input atom domain that excludes NaN.

**Limitations:** The full behavior of near-boundary `alpha`, denominator approximation, subnormal or underflowed `scale`, and finite-precision effects in privacy accounting was not established. Therefore the parameter-validation row is **Partial** rather than `Audited`.

### Verification

Source-level inspection only. No compiled OpenDP tests or new counterexamples were executed during this review. The existing upstream unit tests inspect ordinary quantile releases and a subset of candidate/scoring validation, but this audit does not claim that those tests were run.

## Next checks

- Add dedicated upstream constructor regressions for `[]`, repeated candidates, a NaN candidate, a NaN-containing input domain, out-of-range `alpha`, and invalid `scale`.
- Review effective scale underflow/overflow and denominator rounding, plus the end-to-end privacy map and behavior across metric types; these are excluded from the scoped `Audited` rows.
- Revisit if upstream changes candidate ordering, scorer validation, or Top-K index selection.
