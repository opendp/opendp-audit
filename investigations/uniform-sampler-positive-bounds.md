---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Positive upper bounds at uniform-sampler call sites

## Invariant and threat model

The uniform integer samplers require a strictly positive `upper`; otherwise modulo/remainder by zero can panic rather than return a `Fallible` error. This investigation checks whether reachable internal calls supply a positive bound, including input-dependent sizes. An untrusted input that makes `upper=0` could create a data-dependent crash, but none was identified in the checked paths. This is a **bounded reachability review**, not a proof about every possible public caller or a claim of a privacy exploit.

## Affected symbols and source audits

[Uniform sampler source audit](../source/rust/src/traits/samplers/uniform/mod.rs.md) at upstream `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`:
- [`sample_uniform_uint_below`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/uniform/mod.rs#L47)
- [`sample_uniform_ubig_below`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/uniform/mod.rs#L71)

## Reasoning and evidence

- [Categorical randomized response](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/randomized_response/mod.rs#L95) rejects fewer than two categories before invocation. Its random-lie branch calls the sampler with `categories.len()` or `categories.len() - 1`, so `upper >= 1` for constructed measurements.
- [Vector resizing](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/resize/mod.rs#L58) requires `size > 0`. Its reservoir sampling loop begins with `i >= size`, and requests `sample_uniform_uint_below(i + 1)`. On representable slice lengths, `upper >= 2`. This area has a separate concurrent audit branch, so it is not an independent resize stability audit.
- [Noisy top-k](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noisy_top_k/mod.rs#L215) rejects empty candidate slices before constructing the permutation. Without replacement, the loop ranges `left < x.len()`; with replacement, `left=0` and `x.len() > 0`. Thus `x.len() - left >= 1`.
- [Rational Bernoulli](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/bernoulli/mod.rs#L135) passes the denominator from `RBig::into_parts()` to the `UBig` sampler. [Geometric exponential sampling](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/cks20/mod.rs#L113) passes a rational denominator. These are positive assuming `RBig` canonical denominators are strictly positive; this invariant was **not** independently audited.
- [Upstream unit tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/uniform/test.rs#L1) cover strictly positive k values and chi-square behavior; none of the inspected tests targets zero. No Rust or full upstream test suite was executed in this session.
- A standalone Python arithmetic model enumerated all 256 candidate bytes at every `u8` bound `upper=1..255` and verified equal accepted multiplicities across residues. This is an independent arithmetic check, **not** a native runtime test.

## Findings

**Static API-contract discrepancy:** Both samplers perform remainder by `upper` without rejecting zero. Their on-`main` proof comments currently claim general/non-negative bounds; open upstream [PR #2120](https://github.com/opendp/opendp/pull/2120) and [PR #2119](https://github.com/opendp/opendp/pull/2119) document a positive-bound precondition and change acceptance thresholds. The PRs remain unmerged at the reviewed SHA.

No evidence of zero reaching the samplers from the examined production callers, and no privacy violation identified. No candidate issue was opened.

## Unresolved questions

1. Verify all remaining call paths and the `RBig` denominator invariant; public direct calls can still pass zero.
2. Reproduce the zero-bound behavior with native Rust and determine whether the public API should reject it gracefully.
3. Confirm conditional uniformity after the pending upstream algorithm changes, including `upper=1`, byte boundaries, and high-width values.
4. Test external entropy failures and the RNG adapter separately; arithmetic uniformity does not establish cryptographic strength.
