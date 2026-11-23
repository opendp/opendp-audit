---
schema_version: 1
upstream_commit: a010591f55b1713c926f8e355091471634480307
updated: 2026-11-23
status: Partial
---

# Privacy-filter error accounting across adaptive composition

## Invariant and threat model

The `make_privacy_filter` wrapper must not disclose *either* an invocation's successful result or an invocation error after the cumulative privacy loss exceeds the configured output budget. A measurement can first perform a private computation and then fail in data-dependent postprocessing; that failure is an observable outcome and must be accounted for. Observations are restricted to results and errors of the OpenDP queryable API; runtime side effects and timing channels are excluded.

This is a property of a **valid odometer**, not an authorization to substitute an arbitrary queryable that lies about its privacy loss. The review specifically traces the non-deprecated `make_fully_adaptive_composition` implementation coupled with `make_privacy_filter` initially examined at upstream commit `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` and reverified at current main `a010591f55b1713c926f8e355091471634480307`.

## Affected symbols and source audits

- [Filter source report](../source/rust/src/combinators/privacy_filter/mod.rs.md) covering the output gate and its limitations; refreshed at `a010591f55b1713c926f8e355091471634480307` for the merged nonnegative-budget guard.
- [Fully adaptive odometer source audit](../source/rust/src/combinators/sequential_composition/fully_adaptive/mod.rs.md) reviewing failed-invocation accounting and child permissions at `a010591f55b1713c926f8e355091471634480307`.
- [Upstream `make_privacy_filter` and `new_continuation_rule`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/privacy_filter/mod.rs)
- [Upstream `new_fully_adaptive_composition_queryable`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/fully_adaptive/mod.rs)
- [Queryable forwarding and `Wrapper` machinery](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/interactive/mod.rs)
- [Odometer query/answer types](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs)

## Reasoning and evidence

### Accounting order

The fully adaptive odometer validates query input domain, metric, and output measure first. On acceptance it **pushes `meas.privacy_map.clone()` onto `privacy_maps` before invoking the measurement**. It stores `meas.invoke_wrap(&data, seq_wrapper)` in `answer`, turns on sequential child enforcement, and only then propagates `answer?`. Consequently, an error from the invocation or its postprocessing does not undo the privacy-map entry. Invalid pre-execution supporting elements are rejected without adding that entry.

The privacy filter's `new_continuation_rule` stores `queryable.eval_query(query)` as a `Fallible` value instead of propagating an error. It then obtains the updated `PrivacyLoss(d_in)`. Since the odometer's map entry was already pushed, the returned loss accounts for a query whose postprocessing failed. Only after the bound comparison does the filter return the stored result/error; if over-budget, it permanently drops its inner state and returns the generic exhaustion error.

### Case analysis (derived from source, not executed)

| Invocation path | Odometer entry | Filter's visible response |
| --- | --- | --- |
| Supporting-element validation rejects query | No new entry | Invocation error (unless accumulated loss already exceeds budget) |
| Accepted query succeeds, pending loss within budget | Added before invoking | Original answer |
| Accepted query errors after private computation, pending loss within budget | Added before invoking | Original error, with budget retained |
| Accepted query succeeds or errors, pending loss exceeds budget | Added before invoking | Generic exhaustion error; original result/error withheld |
| Further query after confirmed exhaustion | No invocation | Generic exhausted error |
| Privacy-loss query or distance comparison fails | Underlying state may have advanced | Filter returns error without releasing stored invocation result; recovery behavior not established |

The fourth row is the critical safety gate. Both the success and error paths use the same comparison because the original result is not unwrapped first. A failed `PrivacyLoss` query is a separate dependency failure rather than a demonstrated budget bypass; the wrapper withholds the stored answer but does not necessarily retire its state.

### Existing upstream evidence and dispositions

The reviewed code contains Rust tests `test_privacy_filter_failed_postprocessing_counts_privacy_loss`, `test_privacy_filter_exhaustion_withholds_postprocessing_error`, `test_privacy_filter_failed_postprocessing_cannot_refund_budget`, and fully adaptive odometer tests for failed-postprocessing accounting. Those tests were **read, not run**, in this session. Their historical execution is described in merged [PR #3116](https://github.com/opendp/opendp/pull/3116), which closed [issue #3104](https://github.com/opendp/opendp/issues/3104).

The filter's nonnegative-budget precondition was added by [merged PR #3287](https://github.com/opendp/opendp/pull/3287) after [upstream #3286](https://github.com/opendp/opendp/issues/3286) identified negative budget cancellation; current main rejects negative/NaN budgets prior to invocation. The filter's check-after-execution design was previously discussed in [issue #2960](https://github.com/opendp/opendp/issues/2960). Since the filter controls return values, not arbitrary printing or resource use inside user-defined measurements, that concern is not resolved by the current gate and is not presented as a new privacy bug. Performance of repeated odometer privacy-loss queries is already tracked as [issue #2909](https://github.com/opendp/opendp/issues/2909).

**Execution status:** A current-`main` source-order/coverage preflight executed twelve checks and matched all twelve, including budget reservation before invocation, response gating, sequential-child retirement, and expected native test names. No upstream Rust integration tests, dynamic repro, or model checker were executed. The source and existing test implementations were inspected at the pinned revision; the local environment did not have a Rust compiler and could not access GitHub by `git clone`.

## Findings

No **novel** defect identified within the reviewed source-level control-flow invariant and the valid-odometer assumptions. Historical error-accounting failure is fixed on current `main` by merged PR #3116; negative-budget construction is fixed by merged PR #3287; do not duplicate either. The separate **panic-unwind TLS restoration** weakness in `interactive::wrap` remains on main but is already addressed by **open, unmerged** [PR #3277](https://github.com/opendp/opendp/pull/3277), which introduces an RAII guard. This concerns caught Rust panics, not ordinary `Fallible` errors. No new candidate-defect issue was filed; audit task [#132](https://github.com/opendp/opendp-audit/issues/132) records the bounded re-review.

## Unresolved questions

- Whether an underlying odometer's `PrivacyLoss` failure can be data-dependent or can leave state inconsistent; the filter's error path does not permanently exhaust on every such failure.
- The semantics of nested interactive queryables, user-defined measurements with externally observable side effects, and exceptional comparisons of unusual budget types.
- Run the upstream Rust tests and add a focused regression covering `PrivacyLoss` failure followed by another invocation, using a deliberately conformant test odometer.
