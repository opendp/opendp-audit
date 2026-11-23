---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Partial
---

# Fully adaptive pure-DP concurrent composition

## Invariant and threat model

For a fixed input distance and threshold `E >= 0`, a fully adaptive `MaxDivergence` odometer with valid, nonnegative child epsilon guarantees must produce an `E`-DP **truncated adversary view**, even when child parameters and queries depend on earlier answers and live children are queried concurrently. Child privacy budgets are charged at launch. This claim assumes finite communication and does not claim that the untruncated view is `E`-DP when the realized total exceeds `E`.

## Affected symbols and source audits

- [Source report: `CompositionMeasure for MaxDivergence::composability`](../source/rust/src/combinators/sequential_composition/mod.rs.md) (`privacy/fully-adaptive-composability`).
- [Rust `composability` and `compose`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/mod.rs).
- [Fully adaptive constructor and queryable](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/fully_adaptive/mod.rs).
- [Pure-DP proof table](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/CompositionMeasure_for_MaxDivergence.tex), [proof pseudocode](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/pseudocode/CompositionMeasure_for_MaxDivergence.py) and [queryable proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/fully_adaptive/new_fully_adaptive_composition_queryable.tex).

## Reasoning and evidence

1. An additive pure-DP privacy filter at threshold `E` accepts only children whose cumulative `epsilon_i` is at most `E`. Adaptive basic composition makes this a valid noninteractive filter when each child has its stated guarantee. By Lemma 2.19 of [Haney et al., CCS 2023](https://doi.org/10.1145/3576915.3623128), `G(epsilon_1, ..., epsilon_k) = sum(epsilon_i)` is a valid noninteractive privacy-loss accumulator in the paper's **truncated-view** sense.
2. The paper's Theorem 1.19(2) lifts valid noninteractive `(epsilon, delta)` accumulators to concurrent interactive mechanisms with adaptively chosen parameters. Specializing all `delta_i = 0` covers pure DP. The concurrency theorem assumes finite communication (Theorem 1.24). For successful sums, OpenDP's `inf_add` reports an outward-rounded bound, conditional on its arithmetic contract.
3. The Rust constructor takes the `Concurrent` branch, records each child's privacy map **before** `invoke_wrap`, and reports the `compose` of all stored maps at queried `d_in`. The [queryable proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/fully_adaptive/new_fully_adaptive_composition_queryable.tex) compares these semantics with Algorithm 6 of the paper. The paper's Section 5 explicitly discusses OpenDP's map-based accounting and user-specified `d_in`.
4. **Proof mismatch:** current Rust `MaxDivergence::composability` returns `Concurrent` even for `FullyAdaptive`, but its accompanying pseudocode throws an error for this case and its proof table lists neither sequential nor concurrent theorem. The approximate max-divergence proof cites a newer concurrent result whose pure specialization plausibly closes the theoretical gap.

**Execution:** Static inspection of the pinned Rust files, tests, proof artifacts, and cited publication. No Rust binaries or end-to-end privacy regressions were executed. Existing upstream tests check failed-invocation accounting, but do not by themselves verify the full odometer theorem.

## Findings

A concrete **proof artifact mismatch** exists, tracked as [audit issue #18](https://github.com/opendp/opendp-audit/issues/18). No privacy failure was confirmed within this scope. The theorem supports the intended behavior conditional on valid child maps, finite communication, and faithful odometer semantics. **Upstream disposition: unreported; no matching corrective PR found.**

## Unresolved questions

- Verify every child privacy-map validity and queryable lifetime/error path against the paper's assumptions.
- Update upstream proof pseudocode and table to match Rust, citing Theorem 1.19(2) and its preconditions.
- Execute adaptive-budget and interleaved-query tests to strengthen the source-to-paper correspondence.
