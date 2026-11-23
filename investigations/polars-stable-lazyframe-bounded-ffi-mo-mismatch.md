---
schema_version: 1
upstream_commit: a010591f55b1713c926f8e355091471634480307
updated: 2026-11-23
status: Partial
---

# Bounded Polars stable-lazyframe FFI silently ignores explicit output metric

## Invariant

The Rust FFI constructor `opendp_transformations__make_stable_lazyframe` takes `MI` (the dynamic input metric type) and an `MO` string representing the requested output metric. An **explicit, valid** `MO` must either match the transformation's actual output metric or produce a construction error; the API must not silently return a transformation with a different metric. The documented default type token `MO="MI"` can be treated separately when a bounded metric is deliberately promoted to an unbounded framed metric.

This is a **correctness/API output-contract** property; a returned transformation that correctly advertises its actual output metric is not a demonstrated privacy vulnerability.

## Affected code and underlying types

- [`rust/src/transformations/make_stable_lazyframe/ffi.rs`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/transformations/make_stable_lazyframe/ffi.rs) parses `MO`, handles frame, unbounded and bounded input-metric branches. [Source audit](../source/rust/src/transformations/make_stable_lazyframe/ffi.rs.md).
- [`rust/src/transformations/cast_metric/traits.rs`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/transformations/cast_metric/traits.rs) declares the `BoundedMetric::UnboundedMetric` associated type for each bounded input metric.
- [`rust/src/transformations/make_stable_lazyframe/mod.rs`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/transformations/make_stable_lazyframe/mod.rs) instantiates `StableDslPlan<ChangeOneDistance,FrameDistance<MO>>` and its identifier counterpart; its public constructor returns the metric of the Rust monomorphization.
- [Standalone source-equivalent model](../tools/tests/test_stable_lazyframe_ffi_metric_routing_model.py) models the type dispatch table; it does not execute OpenDP native FFI.
- [Tracking defect #163](https://github.com/opendp/opendp-audit/issues/163), [coordination task #161](https://github.com/opendp/opendp-audit/issues/161).

## Root cause

The FFI entrypoint accepts `MO: *const c_char`, translating `"MI"` to the input-metric type or otherwise parsing with `Type::try_from(v)`. The first two dispatch branches **check the requested `MO`**:

1. `FrameDistance<M>` input: allow `MI == MO` or specifically `FrameDistance<SymmetricIdDistance> → FrameDistance<SymmetricDistance>`; otherwise reject.
2. `SymmetricDistance` or `SymmetricIdDistance` input: allow `MI == MO.get_atom()` or specifically `SymmetricIdDistance → FrameDistance<SymmetricDistance>`; otherwise reject.

The final `else` branch, for `MI=ChangeOneDistance` or `ChangeOneIdDistance`, only dispatches a `MI: BoundedMetric` and calls `make_stable_lazyframe` with the **inferred output metric** `FrameDistance<MI::UnboundedMetric>`. It does not reference the previously parsed `MO` after entering the branch. Thus any syntactically valid explicit `MO` gets the same constructed transformation as the default, even if incompatible.

The associated types are `ChangeOneDistance → SymmetricDistance` and `ChangeOneIdDistance → SymmetricIdDistance`.

## Source-equivalent witness

Assume an otherwise supported domain and `DslPlan::DataFrameScan` (which the unbounded source constructor accepts). Supply one of these **explicit** `MO` strings:

| Input metric `MI` | Requested `MO` | Actual returned `output_metric` | Correct handling |
| --- | --- | --- | --- |
| `ChangeOneDistance` | `FrameDistance<SymmetricIdDistance>` | `FrameDistance<SymmetricDistance>` | Reject mismatch |
| `ChangeOneIdDistance` | `FrameDistance<SymmetricDistance>` | `FrameDistance<SymmetricIdDistance>` | Reject mismatch |
| `ChangeOneDistance` | `SymmetricIdDistance` | `FrameDistance<SymmetricDistance>` | Reject mismatch |
| `ChangeOneIdDistance` | `SymmetricDistance` | `FrameDistance<SymmetricIdDistance>` | Reject mismatch |

The Rust source makes the mismatch independent of dataset values because `MO` is unused in that branch. Both frame-output type strings are recognized in earlier dispatch branches. For `MO="MI"` (the default), the automatic promotion to `FrameDistance<MI::UnboundedMetric>` may be intentional. The defect concerns **explicit incompatible output type requests**, not the default promotion.

The companion [standard-library reference test](../tools/tests/test_stable_lazyframe_ffi_metric_routing_model.py) checks four mismatched explicit requests, two default promotions, and both accepted/rejected routes in other branches. No Rust or Polars runtime was available for this test, so the model confirms the source decision logic, not full runtime constructibility under every particular domain.

## Impact and disposition

**Impact: Construction silently disregards a user-supplied metric type** in one FFI branch. The returned transformation's actual metric is determined by its Rust generic type; downstream chaining will operate on that actual metric. Applications assuming an explicit `MO` is enforced can see misleading success and later type incompatibility. The API is inconsistent with adjacent branches that reject incompatible `MO`.

**No privacy loss established:** A successfully constructed transformation still advertises its real output-metric type. This report does not claim that the requested type is mislabeled, that any stability map is too small, or that a DP mechanism is undercharged.

**Verification:** Reproduced from pinned FFI source and source-equivalent dispatch model; **no native FFI integration test**. **Upstream disposition:** Unreported following targeted upstream/audit issue and upstream PR searches; no equivalent fix observed on current main.

## Remediation and decisive native check

Require the bounded branch to compare an explicitly supplied `MO` to its effective output `FrameDistance<MI::UnboundedMetric>`, while retaining the `"MI"` default as an intentional automatic-promotion sentinel if desired. Alternatively tighten the public API to forbid arbitrary `MO` in bounded mode.

A native regression should instantiate both bounded input metrics with a supported no-op source plan, request the crossed frame metric shown above, and assert a construction-time error. A matched output or default request should succeed and report the correct `output_metric`. Check that the correction does not alter the existing `ChangeOne`-to-`Symmetric` stability factor of two.
