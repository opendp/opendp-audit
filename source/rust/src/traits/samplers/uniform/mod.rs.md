---
schema_version: 1
source: rust/src/traits/samplers/uniform/mod.rs
updated: 2026-11-23
---

# `rust/src/traits/samplers/uniform/mod.rs`

## Scope and assumptions

- **Audit scope:** Correctness of positive-bound rejection sampling and behavior when `upper = 0`, for `sample_uniform_uint_below` and `sample_uniform_ubig_below`.
- **Invariant:** For an integer `upper > 0`, assuming independent uniform input bytes, each result in `[0, upper)` occurs with equal probability. For an unsupported empty range, the current public proof descriptions claim fallible behavior rather than a panic; assess that contract separately.
- **Assumptions:** Native integer `T` is one of OpenDP's implemented unsigned primitive types; `T::MAX_FINITE = 2^(8N)-1`. An arbitrary precision `UBig` has the expected bit length and modular arithmetic. This review does not verify OpenSSL entropy, the full `rand` implementation, or arbitrary user-defined implementations of the traits.
- **Pinned source:** [Implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/uniform/mod.rs#L35); [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/uniform/test.rs#L1).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `traits::samplers::sample_uniform_uint_below` | correctness/uniform-positive-bound | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Analysis](#analysis); modulo classes receive equal multiplicity for `upper > 0` under the stated random-byte assumption. |
| `traits::samplers::sample_uniform_uint_below` | correctness/zero-bound-totality | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Analysis](#analysis); the unconditional `MAX_FINITE % upper` is undefined for zero; not a fallible error. |
| `traits::samplers::sample_uniform_ubig_below` | correctness/uniform-positive-bound | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Analysis](#analysis); the acceptance count is a positive multiple of `upper`. |
| `traits::samplers::sample_uniform_ubig_below` | correctness/zero-bound-totality | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Analysis](#analysis); the `max % upper` expression has a zero divisor if supplied zero. |

## Analysis

For a native `T` with `M = 2^(8N) - 1`, the code sets `threshold = M - (M mod upper)` and accepts integers `0 <= sample < threshold`. Given `upper > 0`, `threshold` is a positive multiple of `upper` and no larger than `M`. Each residue modulo `upper` is represented exactly `threshold / upper` times. The arbitrary-precision sampler chooses `N = ceil(bit_len(upper) / 8)` and `M = 2^(8N)-1`, so the same counting argument applies. This **establishes uniformity of the modulo mapping conditional on uniform random bytes**; it does not independently certify the entropy source.

A Python arithmetic model (not OpenDP execution) exhaustively enumerated `u8` candidate bytes for each positive `upper` in `1..=255`. All 255 cases had equal accepted counts per residue, including powers of two and the maximum bound. The arithmetic model raises `ZeroDivisionError` for `upper=0`. No native Rust or OpenDP test was run in this session.

**Zero bound:** Both Rust functions execute a remainder by `upper` before entering the sampling loop, without validating that `upper > 0`. At zero, that arithmetic does not implement the documented `Fallible` success/error contract; Rust integer remainder by zero panics. The current [native proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/uniform/sample_uniform_uint_below.tex#L1) states no caller-verified precondition and says the postcondition holds for any `upper`; the [UBig proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/uniform/sample_uniform_ubig_below.tex#L1) is similarly broad. Severity is **low / API correctness** on present evidence; no privacy issue or production call with zero was established.

**Upstream coordination:** Existing open [PR #2120](https://github.com/opendp/opendp/pull/2120) and [PR #2119](https://github.com/opendp/opendp/pull/2119) explicitly change the contracts to caller-verified positive bounds and improve rejection efficiency; they are **pending**, not merged on the reviewed `main`. Related [issues #2071](https://github.com/opendp/opendp/issues/2071) and [#2070](https://github.com/opendp/opendp/issues/2070) remain open. No new issue was opened in this audit.

The [cross-file investigation](../../../../../../investigations/uniform-sampler-positive-bounds.md) documents checked callers and limits of the reachability assessment.

## Next checks

- Execute native tests with `upper=0` behind a panic-catching harness to verify runtime behavior without assuming the Rust toolchain outcome.
- Consider whether direct public calls to these samplers should return a `FailedFunction` error on `upper=0` rather than relying solely on a positive-bound precondition.
- Reassess the arithmetic after review PRs #2119 and #2120 merge. Validate any changes with `u8` edge bounds, wide integers, and entropy-failure paths.
