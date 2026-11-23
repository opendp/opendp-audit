---
schema_version: 1
source: rust/src/combinators/amplify/mod.rs
updated: 2026-11-22
---

# `rust/src/combinators/amplify/mod.rs`

## Scope and assumptions

- **Scope:** Construction-time validation and the finite/zero/infinite boundary branches of the privacy accounting utility `amplify_without_replacement` and its `MaxDivergence` / `Approximate<MaxDivergence>` implementations. This review does not claim to prove the amplification theorem or the full library's privacy behavior.
- **Invariants:** The utility accepts only `1 <= sample_size <= population_size`; it applies a conservative one-substitution bound and a valid group-privacy extension; invalid sample-level epsilon/delta values are rejected; zero loss stays zero; integer and float overflows fail closed rather than silently reducing a bound.
- **Assumptions:** Sampling is uniform without replacement, independent of the private data; membership of the sample is not disclosed; `privacy_map` describes *all* releases using the same sample; input/output metric is `ChangeOneDistance`. Fallible directed arithmetic meets its documented upward/downward rounding semantics.
- **Reviewed upstream:** `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`, [implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/amplify/mod.rs), [regressions](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/amplify/test.rs), [FFI adapter](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/amplify/ffi.rs), [directed arithmetic](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/arithmetic/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `combinators::amplify::amplify_without_replacement` | correctness/parameter-validation | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Constructor and FFI checks](#constructor-and-ffi-checks) |
| `combinators::amplify::amplify_epsilon` | privacy/amplification-bound | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Adjacent privacy accounting](#adjacent-privacy-accounting) |
| `combinators::amplify::group_privacy_approx` | privacy/group-privacy | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Group privacy boundary cases](#group-privacy-boundary-cases) |

## Analysis

### Constructor and FFI checks

**Scoped conclusion:** No counterexample was identified to the explicit sample-size and privacy-parameter validation checks. `sample_size == 0` and `sample_size > population_size` reject before computing `sample_size / population_size`. Thus a successful constructor has positive `population_size` and `0 < q <= 1`. The pure and approximate implementations evaluate the sample-level map at distance one; `amplify_epsilon` rejects NaN or negative epsilon, normalizes signed zero, and treats genuine positive infinity as infinite loss. The approximate variant independently rejects delta outside `[0,1]` and normalizes negative zero. The FFI wrapper downcasts the metric to `ChangeOneDistance` and rejects negative signed population distances on invocation.

**Limits of Audited:** This covers the named validation branches and their stated assumptions, not the semantics of arbitrary user-supplied privacy callbacks or the soundness of data-sampling behavior. No compiled Rust or FFI execution occurred in this review.

### Adjacent privacy accounting

The implementation uses `q = sample_size / population_size` and the stated substitution-adjacency amplification formula `epsilon_1 = ln(1 + q * expm1(epsilon))`. For approximate DP it also uses `delta_1 = q * delta`. The code directs division, exponential-minus-one, multiplication and logarithm-minus-one upward; provided their rounding contracts hold, the calculated quantities are upper bounds. At `epsilon = 0` the epsilon output is normalized to `+0`, at `epsilon = +infinity` the output remains infinite, and finite arithmetic overflow becomes an error.

**Status: Partial.** The subsampling theorem, the honesty of supplied privacy maps, and the directed arithmetic implementation have not been independently proven or executed here. Upstream source tests exercise no sampling, tiny rates, overflow, invalid parameters, and signed zero, but were read rather than run.

### Group privacy boundary cases

For a group of `d` substitutions, the approximate-DP branch uses `epsilon_d = d * epsilon_1` and `delta_d = min(1, delta_1 * sum(exp(j * epsilon_1) for j in 0..d-1))`. It evaluates the geometric sum with an `expm1` quotient when epsilon is positive, directing its denominator downward and numerator upward. A zero epsilon uses the linear `d * delta_1` branch and a zero delta stays zero. At `d = 0` the bound is zero, at `d = 1` the bound is unchanged, and an infinite epsilon with positive delta gives the conservative pair `(infinity, 1)` for groups larger than one. The implementation only clips delta after successful arithmetic; a finite intermediate overflow propagates an error.

**Independent arithmetic check executed:** Python's standard-library `decimal` at 80-digit precision verified the reference sum for `(epsilon_1, delta_1, d)` of `(0, 0.02, 3)` yielding `delta_d = 0.06`, `(1, 0.01, 2)` yielding approximately `0.03718281828459045`, `(1, 0.01, 3)` yielding approximately `0.11107337927389695`, and `(0, 0.5, 4)` saturating at one. These are mathematical cross-checks, **not** a run of the OpenDP arithmetic code.

**Status: Partial.** Correctness of the code's directed rounding for every representable `f64` input, sampler assumptions, and full composition across data releases remain unverified. Existing upstream tests cover examples and overflow branches but do not constitute a full proof.

## Context and findings

The old measurement-based population-amplification API had a composition unsoundness tracked in [upstream #2933](https://github.com/opendp/opendp/issues/2933). [PR #3071](https://github.com/opendp/opendp/pull/3071) merged on 2026-11-06, replacing that combinator with this accounting helper. The new API explicitly requires the provided sample-level privacy map to cover *all* releases involving the sample. That prerequisite is caller-enforced, not mechanically verified. A correct numeric result does not by itself make an analysis private if the sample is reused without accounting.

**Finding:** No new defect identified within the bounded validation and boundary-case review. This is not a claim that the entire amplification procedure is sound for arbitrary callers. No GitHub issue or PR was created.

## Next checks

- Run the upstream Rust tests in `rust/src/combinators/amplify/test.rs` with the `partials` feature and exercise the exposed FFI binding.
- Independently verify `InfExpM1`, `InfLn1P`, and `InfDiv` implementations for subnormal and near-overflow values.
- Establish the sampling-without-replacement theorem assumptions and audit caller instructions to ensure all releases sharing a sample are included in the supplied sample-level privacy map.
