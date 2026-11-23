---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Primitive noisy max: scalar top-one postprocessing and empty-input contract

## Scope and invariant

This review narrows to the **non-deprecated primitive** `make_noisy_max`, not Polars `expr_noisy_max` or the previously audited primitive `make_noisy_top_k` probability distribution. A successful wrapper returns an index in `[0,n)` that corresponds to the selected top-1 candidate. A construction on a vector domain admitting input `x` should not silently promise a scalar index if no candidate exists for `x`. The wrapper's privacy map must inherit the source top-k map unchanged under deterministic postprocessing of the selected index.

Evidence: [wrapper source report](../source/rust/src/measurements/noisy_max/mod.rs.md), [upstream primitive source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noisy_max/mod.rs), [top-k source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noisy_top_k/mod.rs), [vector domain](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/mod.rs), [metric-space check](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/mod.rs), and [reference model](../tools/tests/test_noisy_max_wrapper_model.py).

## Control-flow trace and domain witness

`make_noisy_max(domain, LInfDistance::default(), MaxDivergence, 1.0, false)` delegates directly to `make_noisy_top_k(..., k=1, ...)` and composes a fallible vector-to-scalar postprocessor `arg.get(0).cloned()`. The top-k implementation on an input vector of length `n` loops `0..min(k,n)`. Thus successful top-k execution returns a vector with one selected index when `n≥1`, and returns **an empty vector** when `n=0`. The scalar postprocessor then reports `FailedFunction("candidates set is empty")` on the latter case.

The input `VectorDomain::new(AtomDomain::<i32>::default())` has `size=None`. Its `member` implementation iterates all elements and checks size only when `Some(size)`, so `[]` is a valid member. The compatible `LInfDistance` metric-space check only rejects NaN-permitting atomic domains; it does not require a fixed nonzero size. The top-k constructor checks `k<=size` only when size is known. Therefore the unsized measurement is constructible even though invocation fails on an input declared valid. For a fixed `with_size(0)` domain, `k=1` is correctly rejected before invocation.

The [independent source-model test](../tools/tests/test_noisy_max_wrapper_model.py) demonstrates the same conditional path, and [audit issue #90](https://github.com/opendp/opendp-audit/issues/90) includes a proposed native Rust regression. This is an **availability / output totality** defect, not a claimed privacy exploit. The `LInfDistance` definition does not explicitly establish finite closeness between vectors of unequal length, so the potential for data-dependent failure to distinguish neighbors remains unresolved.

## Nonempty postprocessing and privacy-map boundary

For `n≥1`, top-k with `k=1` has exactly one index, and its scalar extraction is deterministic postprocessing. The wrapper's output is the selected original index, with no further random draw and no additional privacy map; `Measurement >> Function` preserves the input measurement's certified cost. Negative scores or minimization merely change the internal ordering before selection. At scale 0, `max_by_key` returns the last tied argmax (or argmin when `negate=true`).

The top-k mechanism's privacy map is zero for `d=0`, infinity for `d>0` at `scale=0`, and otherwise applies `d_{{range}}=d` (monotonic) or `2d` (not monotonic), with `epsilon=d_{{range}}/scale` or `rho=(d_{{range}}/scale)^2/8`, respectively. This review inherits rather than reproves the top-k privacy analysis.

## Executed independent reference model

Ran `python -m unittest -v /mnt/data/test_noisy_max_wrapper_model.py`: **five tests passed**.

- Every ternary score vector of length 1–6, both max/min modes, yielded the correct zero-scale extreme and rightmost tie index: `2×(3+9+27+81+243+729)=2,184` cases.
- Unsized domain admits `[]`, `k=1` constructor's size guard is silent, top-k returns `[]`, and scalar extraction raises the modeled `FailedFunction` condition; fixed-size-zero constructor rejects.
- Singleton index and both signs were checked with multiple finite nonnegative scales.
- Scale and known-size guards were checked, including negative zero and NaN/nonfinite cases.
- A separate 64-case reference checked `k=1` pure-DP/zCDP map formulas for zero and positive sensitivity, monotonic/nonmonotonic metrics and zero/positive scales.

**Limits:** The reference model is standard-library Python, not compiled OpenDP, Polars, FFI, or actual noise sampling. In particular, it does not verify positive-scale distributions, top-k-directed floating-point rounding or `LInfDistance` cross-length adjacency.

## Disposition

A distinct source-confirmed empty-input availability defect was not found in upstream issues/PRs or audit defect tickets. Filed [audit issue #90](https://github.com/opendp/opendp-audit/issues/90) without the `canonical` label. Historical [upstream #2911](https://github.com/opendp/opendp/issues/2911) concerned a different zCDP calibration issue. Existing [top-k audit](../source/rust/src/measurements/noisy_top_k/mod.rs.md) already documents output-length observability; this report is solely about the wrapper's scalar invocation failure.

Overall privacy verification remains **Partial** pending native Rust execution and clarification of the cross-length metric relation. The next engineering decision is whether to enforce positive fixed size or supply an explicit nonempty-domain contract. No upstream edits were made; coordination [#89](https://github.com/opendp/opendp-audit/issues/89).
