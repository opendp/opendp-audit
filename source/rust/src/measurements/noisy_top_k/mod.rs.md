---
schema_version: 1
source: rust/src/measurements/noisy_top_k/mod.rs
updated: 2026-11-22
---

# `rust/src/measurements/noisy_top_k/mod.rs`

## Scope and assumptions

- **Scope:** Correctness of original-index restoration in `peel_permute_and_flip` and index bounds in `permute_and_flip`. Separately, positive-scale selection distributions and pure-DP/zCDP privacy-map calibration were reviewed against a finite exhaustive model (see the new coverage rows and investigation).
- **Invariant:** Given `n` input scores and any request for `k` indices, a successful execution emits exactly `min(k,n)` distinct indices, each in `[0,n)`, in the order in which their corresponding scores were selected from the shrinking vector.
- **Assumptions:** Successful calls to `sample_uniform_uint_below(upper)` return integers in `[0,upper)`, and Rust `Vec::remove` and `BTreeSet` implement their documented semantics. Random/entropy errors abort the measurement rather than producing a partial result.
- **Source links:** [Pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noisy_top_k/mod.rs), [uniform sampler](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/uniform/mod.rs), [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noisy_top_k/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::noisy_top_k::peel_permute_and_flip` | correctness/index-rebasing | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Proof and exhaustive model](#analysis) |
| `measurements::noisy_top_k::permute_and_flip` | correctness/selected-index-range | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Selection branch inspection](#analysis) |
| `measurements::noisy_top_k::make_noisy_top_k` | privacy/calibration | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Distribution and calibration investigation](../../../../../investigations/noisy-top-k-privacy-calibration.md) |
| `measurements::noisy_top_k::permute_and_flip` | privacy/selection-distribution | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Two sampling modes](../../../../../investigations/noisy-top-k-privacy-calibration.md) |
| `measurements::noisy_top_k::TopKMeasure::privacy_map (MaxDivergence)` | privacy/calibration | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Pure-DP comparison](../../../../../investigations/noisy-top-k-privacy-calibration.md) |
| `measurements::noisy_top_k::TopKMeasure::privacy_map (ZeroConcentratedDivergence)` | privacy/calibration | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [zCDP comparison](../../../../../investigations/noisy-top-k-privacy-calibration.md) |

## Analysis

### Index-rebasing argument

Let `A` denote the set of original indices already removed, maintained in ascending order as `sorted_order`. Before a peeling step, the working vector is the original vector with positions `A` removed. Suppose a successful selection returns working index `j`. The loop initializes `index = j` and visits deleted original indices `del` in ascending order. For each `del <= index` it increments `index`, skipping that removed position. At the first `del > index`, all later deletions are also greater, so the loop terminates. This computes exactly the `j`th smallest original position not in `A`. Appending the resulting original position to `natural_order` and inserting it in `sorted_order` maintains the invariant inductively.

The peeling loop runs `min(k, x.len())` times. For both replacement modes, the selected position always lies in the current vector: at zero scale `max_by_key` returns an index in `0..x.len()`; at positive scale, the sampled candidate is an element of a length-`x.len()` index vector. With replacement disabled, Fisher–Yates uses `right = left + sample_uniform_uint_below(x.len() - left)`, which lies in `[left,x.len())`; with replacement enabled, `left` stays zero and the random index is in `[0,x.len())`. All successful selections are therefore valid, their re-based original indices are distinct, and the output size is `min(k,n)`. Empty vectors and `k=0` yield an empty output without invoking the selection subroutine. This holds regardless of score ties.

### Executed test

An independent Python 3 reference model mirrored the Rust `Vec::remove` and ordered-deletion index adjustment. For every original length `n=0..8`, every requested `k=0..n+2`, and every ordered selection of `min(k,n)` distinct original indices, the test reconstructed the successive working-vector indices, applied the Rust-style re-basing loop, and compared the resulting original-index sequence with the reference. It also asserted uniqueness and bounds. **All 218,141 exhaustive cases passed.**

The test exercised the index bookkeeping **model**, not compiled Rust or a full OpenDP measurement. The range argument is based on direct inspection of the constructor's two selection branches and the sampler's contract. The existing upstream Rust tests were inspected but not run. This scoped review found **no index-restoration defect**; it does not establish privacy, sampler distributions, or general correctness.

### Positive-scale selection and privacy-map calibration

The [cross-file investigation](../../../../../investigations/noisy-top-k-privacy-calibration.md) traces both proposal modes, the sampler contract, the L-infinity-to-range sensitivity conversion, per-step privacy maps, and composition over `k` selections. An independently implemented Python probability model exhaustively compared 61,848 ordered neighboring-input cases against the pure-DP bound and 371,088 Rényi-order checks against the zCDP bound (scores in `{-1,0,1}`, vector sizes `2..4`, scales `0.5`, `1`, `2`, both signs, and `k=1..n`). None exceeded the bound by more than the declared `1e-10` tolerance. The comparison was not a native OpenDP execution and does not establish soundness for arbitrary score domains or scales; all new privacy/distribution coverage rows remain **Partial**.

## Next checks

- Run the native Rust regression suite for this module when a runnable upstream checkout is available.
- Extend the privacy-map and selection-distribution review beyond finite small-vector models and resolve the assumptions on unsized input domains.
- Re-review if the index-removal logic or sampler contracts change materially.
