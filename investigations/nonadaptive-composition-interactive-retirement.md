---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Non-adaptive composition: interactive child retirement and static privacy accounting

## Invariant and threat model

For `make_composition` on N compatible child measurements, the composite privacy bound must include all N privacy maps, including when child invocation errors. If `CompositionMeasure::composability(NonAdaptive)` returns `Sequential`, no queryable produced by child i can be queried after child i+1 begins (including nested descendants). Otherwise an interactive child could continue releasing data concurrently without the sequential theorem's premise. The underlying child mechanisms and privacy maps are assumed valid; runtime panics, malicious custom internal `Queryable::new_raw` implementations, and FFI callbacks require separate analysis.

## Affected symbols and source audits

- [Non-adaptive source report](../source/rust/src/combinators/sequential_composition/non_adaptive/mod.rs.md) and pinned [constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/non_adaptive/mod.rs).
- Pinned [`CompositionMeasure` definitions](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/mod.rs); [wrapper and `Queryable::new`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/interactive/mod.rs); [`Measurement::new` and `Function::eval`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs).

## Reasoning and evidence

1. At construction, all child privacy maps are cloned and retained. The composite map computes `compose([map_0(d), ..., map_(N-1)(d)])` regardless of which functions later succeed. Even a result discarded by a downstream error was included in the *static* map. This rules out the particular failure-accounting mistake of composing only successful child evaluations; it does not prove individual child map validity.
2. In the sequential branch, each function call is preceded by `active_id += 1`. The `Wrapper::new_recursive_pre_hook` check compares the captured child ID with the live counter. Consequently, previously emitted queryables cease to pass the hook after the next child is entered. The wrapper is applied to new queryables in the child's invocation scope and recursively to children spawned by those queryables.
3. The returned vector is assembled only after all N component calls complete. Therefore earlier *returned* queryables are already retired at the moment callers receive them. This limits interactivity but is not itself a violation of the sequential privacy theorem.
4. Ordinary errors short-circuit the collection, but do not change the static map. `wrap` restores its thread-local wrapper when the closure **returns**, even if it returns `Err`. On unwinding, current `wrap` does not restore it. [Upstream PR #3277](https://github.com/opendp/opendp/pull/3277) proposes a drop guard for this path. [Upstream PR #3276](https://github.com/opendp/opendp/pull/3276) addresses an FFI-exclusive-borrow reentrancy problem, which is separate from the token logic.

**Evidence type:** Static analysis of upstream `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` and reading [upstream composition tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/non_adaptive/test.rs). **Tests executed:** None; neither the native Rust tests nor an executable reproduction were run in this review.

## Findings

No new confirmed defect in ordinary-path component inclusion or sequential token retirement within the specified assumptions. The pre-existing wrapper unwind and FFI reentrancy limitations have **pending**, unmerged upstream fixes; do not open duplicate issues. The behavior that only the final returned child remains interactively usable under `Sequential` merits a regression test and user-facing clarification, not an unsupported privacy-severity claim.

## Unresolved questions

- Native tests for escaped previous-child queryables, nested descendants, and a failing later component, under the sequential-only `Approximate<ZeroConcentratedDivergence>` measure.
- Whether host-language type-erasure and FFI callbacks preserve the recursive wrapper, particularly after the pending queryable fixes.
- What guarantees are intended for panicking user-provided functions, versus ordinary `Fallible` errors.
