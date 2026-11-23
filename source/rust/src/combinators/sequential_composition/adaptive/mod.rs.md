---
schema_version: 1
source: rust/src/combinators/sequential_composition/adaptive/mod.rs
updated: 2026-11-23
---

# `rust/src/combinators/sequential_composition/adaptive/mod.rs`

## Scope and assumptions

- **Scope:** Fixed-budget, non-deprecated `make_adaptive_composition` constructor and its queryable, including pre-invocation checks, budget entry reservation, errors, and interactive child permission when sequential composability is required.
- **Invariants:** A rejected query does not consume a slot or access protected data. An accepted query consumes exactly one slot **before** invoking its mechanism, even on later failure. Only the most recently accepted query's interactive child remains usable when the measure requires sequential execution. The announced total map is the composition of up-front allocations for requested distances up to the configured `d_in`.
- **Assumptions:** Each query measurement's asserted privacy map is valid and pure, the measure's `CompositionMeasure` theorem applies, `ProductOrd` implements the specified ordering, and `Wrapper::new_recursive_pre_hook` wraps all queryables created in a child invocation. This audit does not prove arbitrary user callbacks private or verify host-language error reconciliation.
- **Pinned upstream:** [Adaptive constructor and queryable](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/adaptive/mod.rs), [`Measurement::check`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs), [`Queryable` and recursive `Wrapper`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/interactive/mod.rs), [composition measures](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/mod.rs), and [upstream regression tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/adaptive/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `combinators::sequential_composition::adaptive::make_adaptive_composition` | privacy/failed-query-budget-accounting | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file reservation trace](../../../../../../investigations/adaptive-composition-reservation-and-retirement.md) |
| `combinators::sequential_composition::adaptive::make_adaptive_composition` | correctness/sequential-child-retirement | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Permission-token reasoning](../../../../../../investigations/adaptive-composition-reservation-and-retirement.md) |
| `combinators::sequential_composition::adaptive::make_adaptive_composition` | privacy/adaptive-compositor-map-bound | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Fixed budget map](#constant-map-and-constructor-validation) |

## Analysis

### Constant map and constructor validation

The constructor computes `zero = output_measure.compose(vec![])` and rejects any proposed `d_mid` that is not greater than or equal to zero under `ProductOrd::total_ge`. It then reverses the list to take entries from its tail in the original caller order, computes `d_out = output_measure.compose(d_mids.clone())` once, and uses a privacy map that returns this constant `d_out` if `d_in_map ≤ d_in_constructor`. If a map query exceeds the configured input distance, it returns an error.

This is conservative **up-front allocation accounting**, not a claim that the map reports actual expenditure after a partial session. For meaningful nonnegative input distances and valid child privacy maps, this use of a fixed upper bound is consistent with the constructor contract. The measure's underlying numeric composition and interactive theorem are separately audited/assumed; see [composition coverage](../mod.rs.md) and the [cross-file investigation](../../../../../../investigations/adaptive-composition-reservation-and-retirement.md).

### Reservation after validation, before invocation

The queryable checks domain, metric, measure, available slot, and `meas.check(&d_in, d_mid)` **before touching protected data**. A failed check returns an error without modifying `d_mids`. On validation success, it creates any needed sequential wrapper, calls `d_mids.pop()` to reserve one slot, then calls `meas.invoke_wrap(&data,seq_wrapper)`. The invocation result may fail; the later `answer?` propagates the error **without restoring the popped entry**. This prevents a failure after a private release from becoming a free retry.

The current upstream implementation includes the failure-accounting fix from merged [PR #3116](https://github.com/opendp/opendp/pull/3116). Existing native tests check failed postprocessing, pre-invocation rejection and negative-budget rejection; those tests were inspected **but not executed** in this review.

The independent [Python state model](../../../../../../tools/tests/test_adaptive_budget_state_model.py) exhaustively checks 3,125 five-action transcripts against the reservation invariant, in addition to direct success/error edge cases. This is a control-flow reference model, not native OpenDP execution or a general interactive-DP proof.

### Permission to interact with children

When `composability(Adaptive) == Sequential`, the created recursive pre-hook obtains a child token `child_id = remaining_before_pop - 1`. After pop the remaining count equals `child_id`. The parent approves a child's internal permission request only when its token equals the **current** remaining count. An over-budget or mismatched-domain query leaves the count unchanged, so the prior child remains active; a subsequent accepted query decreases the count, making all earlier child tokens invalid, even if its invocation/postprocessing subsequently fails.

The `enforce_sequentiality` flag is set after `invoke_wrap` returns, **before** checking `answer?`, which handles child queryables that escape from a failing postprocessor. The recursive `Wrapper` propagates the same hook to nested queryables. Under measures reporting `Concurrent`, these sequential restrictions are intentionally absent; soundness then relies on the concurrent composition theorem.

This is source-consistent with the upstream [retired-child error tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/adaptive/test.rs). Native reentrancy, wrapper type erasure, panics and FFI behavior remain **Partial**.

## Findings

**Bounded negative result:** No confirmed defect in the fixed-budget Rust compositor's validated query handling, reservation timing or ordinary sequential child retirement after the merged failure-accounting fix. This is separate from the [fully adaptive odometer proof mismatch #18](https://github.com/opendp/opendp-audit/issues/18) and from Python `Context` failure reconciliation in pending [upstream PR #3272](https://github.com/opendp/opendp/pull/3272).

## Next checks

- Execute native adaptive compositor tests with all supported `CompositionMeasure` variants, including nested, escaped and failed child queryables.
- Verify panic/unwind handling in `interactive::wrap` and host-language reconciliation separately; the state model does not cover these execution semantics.
- Revalidate the fixed-budget map against the specific output measure's composition theorem and negative/NaN distance semantics at numeric boundaries.
