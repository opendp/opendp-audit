---
schema_version: 1
source: rust/src/measurements/noisy_max/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/noisy_max/mod.rs`

## Scope and assumptions

This audit reviews the **non-deprecated primitive `make_noisy_max`** scalar wrapper, which delegates to `make_noisy_top_k(..., k=1, ...)` and postprocesses the resulting index vector. It does **not** reassess the sampling distribution or the underlying top-k privacy proof, already covered in the [top-k source audit](../noisy_top_k/mod.rs.md). The reviewed OpenDP revision is `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. The independent model is **not compiled Rust/OpenDP** and does not sample random noise.

- [Pinned primitive wrapper](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noisy_max/mod.rs), [upstream native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noisy_max/test.rs).
- [Top-k constructor and peeling loop](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noisy_top_k/mod.rs), [vector membership](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/mod.rs), [`LInfDistance` metric-space check](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/mod.rs).
- [Cross-file investigation](../../../../../investigations/noisy-max-wrapper-empty-input.md), [independent reproducible model](../../../../../tools/tests/test_noisy_max_wrapper_model.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_noisy_max` | correctness/top-one-index-extraction | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Nonempty-input behavior](#nonempty-input-behavior) |
| `make_noisy_max` | correctness/totality-on-accepted-domain | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Empty accepted input counterexample](#empty-accepted-input-counterexample), [issue #90](https://github.com/opendp/opendp-audit/issues/90) |
| `make_noisy_max` | privacy/postprocessing-map-preservation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Privacy-map scope](#privacy-map-scope) |

## Analysis

### Nonempty-input behavior

`make_noisy_max` constructs `make_noisy_top_k(input_domain, input_metric, output_measure, 1, scale, negate)` and composes `Function::new_fallible` that takes `arg.get(0)`. For a successful nonempty top-k release, `min(k,n)=1`, and its sole index is in the original input range `[0,n)`. Thus the scalar wrapper returns exactly the first selected original index, preserving the `negate` direction and the top-k sampling law. At zero scale, the source uses `max_by_key` over signed scores; this selects the **last** tied maximum (or minimum when negated). Existing upstream Rust tests cover max/min under both `MaxDivergence` and `ZeroConcentratedDivergence`, but were inspected, not executed.

The [reference model](../../../../../tools/tests/test_noisy_max_wrapper_model.py) exhaustively tested **2,184** finite zero-scale inputs with positive length (all ternary score sequences of lengths 1–6, both `negate` modes), plus singleton and scale guards. The selected index was valid and attained the appropriate extremum in all model cases. It does not verify sampling randomness for positive scales.

### Empty accepted input counterexample

For `VectorDomain::new(AtomDomain::<i32>::default())`, `size=None` and the domain `member(&vec![])` returns true by vacuity. `MetricSpace` for `LInfDistance` checks non-NaN membership, without requiring a positive size. The top-k constructor checks `k>size` **only if** `input_domain.size` is `Some`, so `make_noisy_max` construction succeeds with `k=1` on this unsized domain. For empty invocation input, `peel_permute_and_flip` loops `0..min(1,0)` times and returns `[]`; the wrapper's `arg.get(0)` produces `FailedFunction("candidates set is empty")`.

This is a **source-confirmed accepted-input availability/postcondition mismatch**: the constructor admits an input for which it cannot return a selected index. The existing wrapper tests do not cover empty input. A fixed-size-zero input domain is rejected at construction, and a positive known size excludes empty input. [Unreported defect #90](https://github.com/opendp/opendp-audit/issues/90) includes a native Rust regression sketch. The [independent model](../../../../../tools/tests/test_noisy_max_wrapper_model.py) exercises the exact guard/loop/get behavior, but the native Rust regression is still unexecuted.

### Privacy-map scope

For nonempty vectors, the first index is a deterministic postprocessing of the `k=1` top-k output; `Measurement >> Function` preserves the upstream privacy map rather than composing an additional privacy cost. The inherited top-k map converts `L_\infty` to range sensitivity (`d` if monotonic, otherwise `2d`) and computes pure-DP or zCDP costs, with zero for zero input distance and infinity at zero noise scale with positive sensitivity. The reference model checked **64** regular guard/formula cases. This audit does **not** revalidate the top-k sampling proof, floating directed rounding, or cross-length `LInfDistance` relations; the privacy finding remains **Partial**.

A failure on an admitted input could become data-dependent error observability, but **no neighboring unequal-length pair at finite `LInfDistance` has been established**, and no privacy-budget violation is asserted.

## Findings and next checks

The primitive wrapper has a documented availability defect on the empty member of an unsized domain, tracked in [audit defect #90](https://github.com/opendp/opendp-audit/issues/90). Otherwise scalar top-one extraction and deterministic privacy-map preservation follow from the top-k contract for nonempty inputs. [Coordination task #89](https://github.com/opendp/opendp-audit/issues/89) tracks this bounded review.

Run the native Rust regression in #90, decide whether the API should require a nonempty domain or explicitly tolerate fallible empty invocations, and audit the full cross-length metric semantics before assigning any privacy impact. No upstream code was modified.
