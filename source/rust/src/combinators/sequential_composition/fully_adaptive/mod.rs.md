---
schema_version: 1
source: rust/src/combinators/sequential_composition/fully_adaptive/mod.rs
updated: 2026-11-23
---

# `rust/src/combinators/sequential_composition/fully_adaptive/mod.rs`

## Scope and assumptions

- **Scope:** `make_fully_adaptive_composition` / `new_fully_adaptive_composition_queryable`: pre-invocation supporting-element checks, failed postprocessing privacy accounting, sequential-child permission management, and `PrivacyLoss` query semantics. The paired filter's answer gating is reviewed only to validate the cross-file invariant.
- **Invariants:** Every measurement accepted for invocation must add its privacy map **before** accessing private data, including if fallible postprocessing later fails. For sequential-only composition, an accepted later invocation must retire earlier child queryables, even when the later invocation returns an error. A privacy filter must withhold both the success answer and postprocessing error until checking the cumulative loss.
- **Assumptions:** Caller supplies a valid underlying measurement/odometer (honest-but-curious contracts); runtime panics and external side effects are outside the standard `Fallible` error model; `ProductOrd` and `CompositionMeasure` implementations satisfy their documented contracts. Full proof of composability for pure-DP concurrent interaction is excluded (already tracked in [audit #18](https://github.com/opendp/opendp-audit/issues/18)).
- **Pinned OpenDP `main`:** [`a010591f55b1713c926f8e355091471634480307`](https://github.com/opendp/opendp/tree/a010591f55b1713c926f8e355091471634480307), including [odometer source](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/combinators/sequential_composition/fully_adaptive/mod.rs), [filter source](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/combinators/privacy_filter/mod.rs), [interactive wrappers](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/interactive/mod.rs), [odometer regression tests](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/combinators/sequential_composition/fully_adaptive/test.rs), and [filter regression tests](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/combinators/privacy_filter/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_fully_adaptive_composition` | privacy/composability-mode-guard | Partial | `a010591f55b1713c926f8e355091471634480307` | [Composition-mode selection](#composition-mode-selection) and existing proof issue [#18](https://github.com/opendp/opendp-audit/issues/18) |
| `new_fully_adaptive_composition_queryable` | privacy/failed-postprocessing-accounting | Audited | `a010591f55b1713c926f8e355091471634480307` | [Invocation ordering](#invocation-ordering); [cross-file investigation](../../../../../../investigations/privacy-filter-failure-accounting.md) |
| `new_fully_adaptive_composition_queryable` | privacy/sequential-child-retirement | Audited | `a010591f55b1713c926f8e355091471634480307` | [Sequential child permissions](#sequential-child-permissions) |
| `new_fully_adaptive_composition_queryable` | correctness/privacy-loss-query-precondition | Audited | `a010591f55b1713c926f8e355091471634480307` | [Privacy loss query](#privacy-loss-query) |
| `new_fully_adaptive_composition_queryable` | privacy/interactive-wrapper-panic-unwind | Partial | `a010591f55b1713c926f8e355091471634480307` | [Panic unwinding and pending upstream repair](#panic-unwinding-and-pending-upstream-repair); [upstream PR #3277](https://github.com/opendp/opendp/pull/3277) |

## Analysis

### Invocation ordering

The odometer tests supporting-element equality on the measurement's input domain, metric, and output measure first. Only a valid query reaches `privacy_maps.push(meas.privacy_map.clone())`. Crucially, this push occurs **before** `meas.invoke_wrap(&data, seq_wrapper)`, and the result is stored in `answer` rather than propagated early. The implementation enables sequentiality (`*enforce_sequentiality.borrow_mut() = true`) before `OdometerAnswer::Invoke(answer?)` can return an error. Thus an accepted measurement can fail after producing a private result in its postprocessor, and its full privacy map remains accounted.

Existing Rust tests `test_fully_adaptive_failed_postprocessing_counts_privacy_loss` and `test_fully_adaptive_pre_invocation_rejection_does_not_count` cover the expected distinction, and `test_privacy_filter_failed_postprocessing_cannot_refund_budget` covers the filter's response. These tests were **inspected, not compiled/executed**. This behavior was repaired previously by [merged upstream PR #3116](https://github.com/opendp/opendp/pull/3116); it is **not** a novel finding.

### Sequential child permissions

`require_sequentiality` derives from `output_measure.composability(Adaptivity::FullyAdaptive)`. When it is `Sequential`, a recursive child wrapper carries `child_id = privacy_maps.len()` after the entry is reserved. After the parent has exited invocation, the prehook asks the parent odometer for permission when querying the child or any wrapped descendant. Permission requires `id + 1 == privacy_maps.len()`. Every accepted parent invocation increments this length and therefore retires earlier children, **even if postprocessing fails**. The guard is enabled before the original `Fallible` answer is unwrapped.

Existing native tests `test_fully_adaptive_failure_retires_previous_sequential_child`, `test_fully_adaptive_failed_postprocessing_child_keeps_sequential_wrapper`, and `test_fully_adaptive_sequential_child_accepts_queries` cover the key transitions. The source trace finds no child-resumption bypass for accepted `Fallible` invocation paths. The recursive wrapper uses the thread-local `WRAPPER` to wrap nested spawned queryables (separately audited below).

### Privacy loss query

If a constructor supplies `d_in=Some(bound)`, `PrivacyLoss(d_in_q)` requires `d_in_q.total_cmp(bound) == Equal`; an inconsistent request errors before evaluating the vector of privacy maps. With `d_in=None`, the odometer permits different queried input distances. It computes `privacy_maps.iter().map(|m| m.eval(d_in_q))`, then `output_measure.compose(d_mids)`. The resulting cumulative loss includes prior accepted invocations regardless of postprocessing outcome. Source inspection does **not** prove each supplied privacy map is itself valid.

The paired `make_privacy_filter` [at this SHA](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/combinators/privacy_filter/mod.rs) checks its configured `d_out` against the output measure's zero, rejecting negative or NaN budgets before invocation; this is the new merged [PR #3287](https://github.com/opendp/opendp/pull/3287). The filter obtains the pending answer/error, queries cumulative loss, and withholds either kind of answer if the bound would be exceeded.

### Composition-mode selection

`make_fully_adaptive_composition` checks `output_measure.composability(Adaptivity::FullyAdaptive)` before accepting the odometer. The returned mode controls child sequentiality; the audit **does not** independently establish correctness of each measure's `composability` theorem. In particular, [audit #18](https://github.com/opendp/opendp-audit/issues/18) separately tracks the pure-DP proof/implementation mismatch, so this review makes no redundant defect claim.

### Panic unwinding and pending upstream repair

The cross-file `interactive::wrap` implementation at this SHA sets a thread-local `WRAPPER`, runs `f()`, and restores the previous wrapper only **after** `f` returns normally. A Rust panic unwinding through `f()` skips restoration. If the panic is caught, the thread can continue with a stale wrapper affecting later queryable construction. This is separate from an ordinary `Fallible::Err`, which restores the previous wrapper normally. The condition is already recognized and specifically fixed by **open, unmerged** [upstream PR #3277](https://github.com/opendp/opendp/pull/3277), which introduces an RAII restoration guard with a test for `catch_unwind`. Do **not** refile this as a new finding or claim that the fix is merged on `main`.

## Executed checks and limits

A connector-based source-text preflight checked **12 ordered predicates / regression-test names** against the pinned odometer, filter, and interactive sources. All 12 matched, including before-invocation accounting, before-return sequential lock, post-invocation filter privacy check, nonnegative filter budget, and the lack of unwind-safe thread-local restoration. This is a **source-order/coverage check**, not Rust execution or a privacy experiment.

**Not executed:** Native OpenDP Rust unit tests, FFI integration, caught-panic regression, or arbitrary measure composability. Infallible library guarantees are not inferred from source-text matches; the `Audited` rows refer solely to the declared source-control-flow properties under stated valid-measurement assumptions.

## Disposition

No **novel** privacy bypass established for failed `Fallible` invocations, response gating, or sequential child retirement. Existing error-accounting defect is fixed by merged [PR #3116](https://github.com/opendp/opendp/pull/3116); identified panic-unwind contamination is covered by pending [PR #3277](https://github.com/opendp/opendp/pull/3277). [Audit task #132](https://github.com/opendp/opendp-audit/issues/132) coordinates this negative result.

Next: execute pinned `fully_adaptive` and `privacy_filter` Rust tests; verify the pending RAII patch under nested wrappers and caught panics; separately investigate privacy-map failures/recovery and any formal composability theorem issues rather than conflating them with observed return-value gating.
