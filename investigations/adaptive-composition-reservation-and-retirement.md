---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Fixed-budget adaptive composition: reservation and sequential-child lifecycle

## Invariant and threat model

The non-deprecated `make_adaptive_composition` creates an interactive queryable with a **fixed list** of maximum privacy expenditures. Two failure boundaries matter: an invalid query rejected **before** private invocation must leave the current budget entry intact, while a query accepted for invocation must consume one entry **even if its randomized mechanism or later postprocessor fails**. Where the output measure permits only sequential interactive composition, only the most recent spawned interactive child may be queried after a later accepted query. An error from an accepted query must still retire older children.

This property is conditional on child measurements' declared privacy maps and the selected measure's composition theorem. It does not prove arbitrary child mechanisms private, nor does it audit Python `Context` budget bookkeeping.

## Cross-file evidence

- [Adaptive compositor source audit](../source/rust/src/combinators/sequential_composition/adaptive/mod.rs.md) and [pinned constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/adaptive/mod.rs).
- [`Measurement::check` and `map`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs) provide pre-invocation privacy-map validation, without accessing the protected dataset.
- [`Queryable::eval_query`, recursive wrappers, `invoke_wrap`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/interactive/mod.rs) supply the permission hooks and fallible execution.
- [`CompositionMeasure::compose`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/mod.rs) computes the declared total budget from the fixed list.
- [Native upstream tests inspected](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/adaptive/test.rs), [independent model regression](../tools/tests/test_adaptive_budget_state_model.py).
- Prior merged [upstream PR #3116](https://github.com/opendp/opendp/pull/3116) changed the reservation order and includes tests of failed invocations. Open [PR #3272](https://github.com/opendp/opendp/pull/3272) concerns Python `Context` reconciliation; it does not establish a separate defect in this Rust compositor.

## State machine and reservation ordering

The constructor compares every `d_mid` to the measure's zero element via `ProductOrd::total_ge`, rejecting negative allocations and NaNs under the supported distance types. It reverses the budget list so successive accepted queries inspect its **last** entry while preserving the caller's original query order. It composes a constant `d_out` upper bound once. The resulting privacy map rejects any requested `d_in_map` greater than the constructor's `d_in`; otherwise it returns `d_out`. This is an **upper bound**, not a history-dependent report of actual spent privacy.

Inside the queryable, a query first checks input domain, metric and output measure equality, finds an unspent slot, then executes `meas.check(&d_in,d_mid)`. Only after all checks succeed does it call `d_mids.pop()`, immediately followed by `meas.invoke_wrap(&data,seq_wrapper)`. Thus an invalid domain, budget overrun, malformed privacy-map result, or exhausted slot is a **pre-invocation rejection** with no expenditure. Conversely, any successfully validated query occupies a slot before the function touches private data. The `?` on `answer` occurs **after** the pop, so a failed invocation or postprocessing cannot refund the charge.

This sequencing addresses the scenario corrected by merged [PR #3116](https://github.com/opendp/opendp/pull/3116), which introduced explicit failure accounting. The tests in upstream `adaptive/test.rs` cover a failing postprocessor consuming its budget, an over-budget query preserving its budget, errors retiring prior children, and rejection of negative/NaN allocations. The audit inspected these tests but **did not run compiled OpenDP Rust**.

## Sequential versus concurrent child permission

When `output_measure.composability(Adaptive)` returns `Sequential`, the queryable creates a recursive wrapper for any child queryables that its selected measurement spawns. Before reserving a slot, `child_id = d_mids.len() - 1`. Immediately after reserving, remaining length is `d_mids.len() = child_id`. Once the selected measurement returns (successfully or with error), the associated `enforce_sequentiality` flag becomes true.

For a wrapped child, the pre-hook calls its parent with an internal `AskPermission(child_id)`. The parent approves exactly if `child_id == d_mids.len()`. Therefore the most recent child's token remains live while no later query has been **accepted**, and an older child becomes inaccessible as soon as a later accepted query decreases `d_mids.len()`. The condition remains false for an old token even if the later invocation fails. A failed postprocessor can leak a captured child queryable to caller-owned state; the native regression covers that exceptional case and verifies its wrapper remains attached.

For measures whose `composability` returns `Concurrent`, the wrapper is omitted intentionally. Continued use of previous children then relies on the measure's **concurrent interactive composition theorem**. This is not an indication that sequential-only children may be freely interleaved.

The recursive wrapper's exact behavior depends on foreign queryable type erasure and the `thread_local!` wrapper implementation. Those runtime details were traced but **not** exercised across real nested interactive measurements in this audit.

## Independent finite state-model evidence

The standard-library [Python state-machine test](../tools/tests/test_adaptive_budget_state_model.py) models slots, errors, child IDs and authorization checks, and includes:

- **3,125** action transcripts (all length-five sequences over success, domain rejection, budget rejection, invocation failure and postprocessing failure), checking spent slots and state invariant after every transition.
- Direct checks that failures **before** invocation leave an entry, and failures **after** reservation consume exactly one entry.
- The original allocation order despite internal list reversal.
- An earlier sequential child surviving a rejected query but becoming unusable after a later accepted failure.
- A captured child from a failed postprocessor retaining its wrapper; root-invocation isolation; concurrent-mode behavior; empty and invalid allocations.

This model reproduces the **pinned control-flow decisions**, but it is not a native OpenDP Rust test, not a statistical privacy proof, and not evidence that all FFI queryable wrappers have identical runtime behavior.

## Findings

**Bounded negative result:** No confirmed defect in the fixed-budget Rust adaptive compositor's reservation order or source-level child retirement under supported measure and honest child-map assumptions. Merged PR #3116 is present in current main and its source explicitly consumes budget before invocation. No new defect issue warranted.

**Residual Partial:** Full interactive composability theorem, actual nested child execution, host-language failure handling (including open PR #3272), arbitrary callback purity and panic/unwind behavior were not established by this finite model. Distinct fully adaptive odometer/proof alignment remains tracked as [audit issue #18](https://github.com/opendp/opendp-audit/issues/18).

## Next checks

- Run the upstream `adaptive/test.rs` suite on a compiled OpenDP library with the supported output-measure combinations.
- Add native tests for nested sequential children across rejected, accepted-failed and accepted-successful parent queries, including escaped children after failure.
- Separately verify Python `Context` to Rust budget reservation reconciliation and the outcome of pending upstream PR #3272, without conflating it with the fixed-budget constructor.
