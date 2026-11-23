---
schema_version: 1
source: rust/src/combinators/privacy_filter/mod.rs
updated: 2026-11-23
---

# `rust/src/combinators/privacy_filter/mod.rs`

## Scope and assumptions

- **Audit scope:** Non-deprecated, `contrib`-gated `make_privacy_filter` and `new_continuation_rule`: the post-query privacy-loss gate, handling of failed measurement/postprocessing invocations, permanent exhaustion, and the stated privacy-map boundary. Not a general proof of arbitrary odometers.
- **Invariants:** A query outcome (including an `Err`) is never returned if the *updated* odometer privacy loss exceeds the configured budget. A successful threshold crossing irreversibly exhausts the wrapper. The outer measurement's privacy map returns `d_out` only for input distances at most configured `d_in`.
- **Assumptions:** A valid underlying odometer reliably accounts for every accepted query, including errors after private releases; `PrivacyLoss(d_in)` returns the correct cumulative bound without exposing private information; comparisons via `ProductOrd` are sound; the programmer observes return values, not unmodeled side effects, timing, or resource exhaustion. Incomparable values can produce errors, not a successful release.
- **Initial reviewed upstream revision:** `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. **Budget validation and response gating re-reviewed on current main:** [`a010591f55b1713c926f8e355091471634480307`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/combinators/privacy_filter/mod.rs). Evidence: [privacy filter](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/privacy_filter/mod.rs), [fully adaptive odometer](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/fully_adaptive/mod.rs), [interactive query wrapper](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/interactive/mod.rs), [core odometer](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs), [upstream regression tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/privacy_filter/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `combinators::privacy_filter::new_continuation_rule` | privacy/over-budget-answer-withholding | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Transition analysis](#transition-analysis) and [investigation](../../../../../investigations/privacy-filter-failure-accounting.md) |
| `combinators::privacy_filter::new_continuation_rule` | correctness/terminal-exhaustion | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Transition analysis](#transition-analysis) |
| `combinators::privacy_filter::make_privacy_filter` | privacy/map-bound | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Map analysis](#map-analysis); relies on a valid odometer contract |
| `combinators::privacy_filter::new_continuation_rule` | privacy/failed-postprocessing-accounting | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file investigation](../../../../../investigations/privacy-filter-failure-accounting.md), dependent on odometer bookkeeping |
| `combinators::privacy_filter::make_privacy_filter` | privacy/nonnegative-budget-precondition | Audited | `a010591f55b1713c926f8e355091471634480307` | [Budget construction validation](#budget-construction-validation) and merged [upstream PR #3287](https://github.com/opendp/opendp/pull/3287) |
| `combinators::privacy_filter::new_continuation_rule` | privacy/over-budget-answer-withholding | Audited | `a010591f55b1713c926f8e355091471634480307` | [Transition analysis](#transition-analysis) and [fully adaptive audit](../../../../../source/rust/src/combinators/sequential_composition/fully_adaptive/mod.rs.md) |

## Analysis

### Transition analysis

**Conclusion:** The wrapper's source control flow withholds *both* successful answers and invocation errors when a pending privacy-loss check succeeds and exceeds the configured budget.

The transition starts with `state: Option<Queryable>`. When it is `None`, it immediately returns the generic exhausted error, without invoking the underlying odometer. Otherwise, it calls `queryable.eval_query(query)` and **stores the `Fallible` result without propagating it**. Next it requests `OdometerQuery::PrivacyLoss(d_in.clone())` from the same underlying queryable, after the attempted invocation. If that query fails or produces the wrong answer variant, no stored invocation result is exposed. If `pending_d_out.total_gt(&d_out)?` returns `true`, the wrapper invokes `state.take()` and returns its own exhausted error. Only when the comparison returns `false` does it return the original `answer`, which may be `Ok` or `Err`.

This ordering is essential: returning an error from private postprocessing before checking spent budget could reveal a private-data-dependent event without charging privacy loss. The wrapper does **not** prevent the underlying measurement from executing before rejection; instead, it prevents disclosure of its result under the model's observable-output assumptions.

**Conditioned limitations:** If `PrivacyLoss` or `ProductOrd` fails, the outer wrapper returns an error rather than the pending invocation outcome, but the underlying state may have advanced. The code does not forcibly set `state = None` on those error paths. Whether *subsequent* queries are safe depends on the validity, failure semantics, and state integrity of the underlying odometer. Externally visible side effects during execution are outside the return-value gate; [upstream issue #2960](https://github.com/opendp/opendp/issues/2960) discussed this design.

**Existing tests examined (not executed):** `test_privacy_filter_exhaustion_withholds_postprocessing_error`, `test_privacy_filter_failed_postprocessing_counts_privacy_loss`, and `test_privacy_filter_failed_postprocessing_cannot_refund_budget` cover the key paths with a genuine Rust failing-postprocessing measurement. The tests also cover constructor distance mismatch. They were introduced by merged [PR #3116](https://github.com/opendp/opendp/pull/3116) addressing [issue #3104](https://github.com/opendp/opendp/issues/3104). This is an already-remediated historical defect, **not** a new finding on reviewed `main`.

### Map analysis

**Conclusion:** For comparable input distances, the map returns the configured budget when `d_in_p <= d_in`, and otherwise fails with `RelationDebug`. The original reviewed revision did **not** enforce nonnegative/well-formed budget distances, but that assessment is superseded **on current main** by [merged PR #3287](https://github.com/opendp/opendp/pull/3287). The constructor now sets `zero = odometer.output_measure.compose(vec![])?` and rejects `d_out` if `!d_out.total_ge(&zero)?`, so negative and NaN budgets cannot silently cancel positive privacy loss. The constructor does not verify that an arbitrary supplied odometer meets its semantic contract. The constructor delegates validation of the input metric/domain pair to `Measurement::new`. The map relies on `Odometer`'s abstract guarantees.

**Status:** Partial for the *general-odometer validity* property; the newly isolated nonnegative-budget precondition is source-audited. Full general-odometer contract, unusual distance types, and failure behavior of custom queryables remain unverified.

### Budget construction validation

On upstream main `a010591f55b1713c926f8e355091471634480307`, the filter's `make_privacy_filter` checks `d_out.total_ge(&zero)?` where `zero` is `odometer.output_measure.compose(vec![])?`. The float `ProductOrd` implementation errors on NaN; negative scalar and negative components of tuple budgets are rejected. The [current native regression](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/combinators/privacy_filter/test.rs) explicitly checks negative and NaN `d_out` for `MaxDivergence` and `Approximate<MaxDivergence>`; these tests were inspected only. This addresses the previously open negative-budget counterexample [upstream issue #3286](https://github.com/opendp/opendp/issues/3286), merged as [PR #3287](https://github.com/opendp/opendp/pull/3287). The error-answer withholding control flow is unchanged from the prior review and reverified by the source-order check in [fully adaptive source audit](../../../../../source/rust/src/combinators/sequential_composition/fully_adaptive/mod.rs.md). No new leak shown.

`interactive::wrap` has a separate panic-unwind TLS restoration bug under a **caught Rust panic**; the targeted repair exists in [open PR #3277](https://github.com/opendp/opendp/pull/3277), not on main. This is **not** a normal `Fallible` error and does not invalidate the source-traced failure accounting, but it is a remaining runtime robustness boundary.

## Next checks

- Execute upstream Rust tests with an upstream checkout and supported Rust toolchain; neither was available in this session.
- Check nested interactive child queryables, exceptional `PrivacyLoss` failures, and unusual budget values against the formal odometer contract.
- Examine side-effect and timing-channel visibility separately; the observed return-value control flow does not address them.
- No new bug found in the declared properties under stated assumptions; no exclusive audit-task claim or issue was created.
