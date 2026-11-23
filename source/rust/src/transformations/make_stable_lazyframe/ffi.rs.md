---
schema_version: 1
source: rust/src/transformations/make_stable_lazyframe/ffi.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_lazyframe/ffi.rs`

## Scope and assumptions

- **Scope:** The FFI `opendp_transformations__make_stable_lazyframe` entrypoint: dynamic `MI/MO` type parsing and dispatch for frame, unbounded and bounded input metrics, especially whether an explicitly requested output metric `MO` is honored or rejected. Inspect `BoundedMetric` associated types and the Rust generic `make_stable_lazyframe` result, but do not re-prove Polars transform stability.
- **Invariant:** An explicitly requested `MO` that conflicts with the returned `output_metric` must fail at FFI construction rather than succeeding silently. The generated default token `MO="MI"` may signal automatic promotion for bounded metrics; its intended semantics are not contested in this review.
- **Assumptions:** The `Type::try_from` parser recognizes the two frame-distance strings already used by earlier FFI dispatch branches. For a supported domain and source plan, the Rust `StableDslPlan` implementations construct the declared output metric. Actual native Rust/Polars execution is untested.
- **Pinned sources:** [FFI dispatcher](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/transformations/make_stable_lazyframe/ffi.rs), [Rust constructor](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/transformations/make_stable_lazyframe/mod.rs), [`BoundedMetric` associated types](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/transformations/cast_metric/traits.rs), and [source-equivalent reference model](../../../../../tools/tests/test_stable_lazyframe_ffi_metric_routing_model.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `opendp_transformations__make_stable_lazyframe` | correctness/explicit-output-metric-honored | Audited | `a010591f55b1713c926f8e355091471634480307` | [Bounded-MI FFI ignores explicit requested MO](#bounded-mi-ffi-ignores-explicit-requested-mo); [defect #163](https://github.com/opendp/opendp-audit/issues/163) |
| `opendp_transformations__make_stable_lazyframe` | correctness/unbounded-output-metric-routing | Audited | `a010591f55b1713c926f8e355091471634480307` | [Frame and unbounded MI checks](#frame-and-unbounded-mi-checks); type-dispatch branches only |
| `opendp_transformations__make_stable_lazyframe` | privacy/bounded-metric-stability-conversion | Partial | `a010591f55b1713c926f8e355091471634480307` | [Downstream Rust conversion](#downstream-rust-conversion); correct output type selection is distinct from unproved whole-query stability |

## Analysis

### Frame and unbounded MI checks

The entrypoint parses the requested output type `MO` from a C string, translating the default `"MI"` token to the input type or invoking `Type::try_from` on an explicit output metric. For `MI=FrameDistance<SymmetricDistance>` or `FrameDistance<SymmetricIdDistance>`, `MO` is compared with `MI` or the one allowed identifier-to-symmetric conversion. Unsupported output types are rejected with an FFI error. Similarly, for unbounded `MI=SymmetricDistance` or `SymmetricIdDistance`, the dispatch checks `MO.get_atom()` and an explicit identifier-to-symmetric exception.

**Verified:** Both branches have explicit incompatible-`MO` rejection rather than a generic fallback. The ordinary source branch treats `MO` as an API contract.

### Bounded MI FFI ignores explicit requested MO

The final `else` branch matches `MI` against `ChangeOneDistance` and `ChangeOneIdDistance`. It defines a monomorphized `MI: BoundedMetric` helper that unconditionally invokes `make_stable_lazyframe(input_domain, input_metric, lazyframe)` with output metric `FrameDistance<MI::UnboundedMetric>`. **The previously parsed `MO` is never read inside this branch**. Accordingly, the following explicit requests are syntactically valid but not honored:

- `MI=ChangeOneDistance`, explicit `MO=FrameDistance<SymmetricIdDistance>` results in `FrameDistance<SymmetricDistance>` if construction succeeds.
- `MI=ChangeOneIdDistance`, explicit `MO=FrameDistance<SymmetricDistance>` results in `FrameDistance<SymmetricIdDistance>` if construction succeeds.

These are not merely two spellings of the same metric: one measures record symmetric difference and the other identifier symmetric difference. Yet a caller receives neither the requested output type nor an incompatible-type error. The [cross-file investigation](../../../../../investigations/polars-stable-lazyframe-bounded-ffi-mo-mismatch.md) documents two additional mismatched types and the type-dispatch table. [Issue #163](https://github.com/opendp/opendp-audit/issues/163) tracks the correctness contract violation; **no privacy label** is appropriate for this issue without an underlying stability underbound.

### Downstream Rust conversion

[The generic Rust implementation](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/transformations/make_stable_lazyframe/mod.rs) defines `StableDslPlan<ChangeOneDistance,FrameDistance<MO>>` and `StableDslPlan<ChangeOneIdDistance,FrameDistance<MO>>` using a stable `ChangeOne→Symmetric` conversion with factor-two stability. The associated `MI::UnboundedMetric` types come from [`cast_metric/traits.rs`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/transformations/cast_metric/traits.rs). Thus the actual transformation returned by the FFI has a well-typed output metric dictated by its Rust generic parameters; the function does **not** claim to return the incompatible requested type. The bug is the silent ignoring of `MO`, not a demonstrated incorrect stability map. Full domain and distance bounds remain `Partial` for this audit.

### Execution status and findings

**Executed:** Standalone Python standard-library model of the three FFI dispatch branches; it covers four explicit bounded type mismatches, both automatic bounded default promotions, compatible routes, and incompatibility errors in the two branches that check `MO`. The [reference test](../../../../../tools/tests/test_stable_lazyframe_ffi_metric_routing_model.py) is in the audit repository.

**Not executed:** Compiled OpenDP FFI, native Polars expression planner, `Type::try_from` parsing, or `Transformation.output_metric` introspection. The exact output type of the bounded branch follows the Rust generic signatures; native execution should confirm that the simple source plan is constructible for both metrics.

**Conclusion:** New correctness/API type-request mismatch in the bounded input branch, tracked as [candidate issue #163](https://github.com/opendp/opendp-audit/issues/163). No new independently supported privacy violation.

## Next checks

Add native FFI regression cases for `MI=ChangeOneDistance` with an explicit `MO=FrameDistance<SymmetricIdDistance>` and `MI=ChangeOneIdDistance` with `MO=FrameDistance<SymmetricDistance>`. Reject these explicit conflicts while preserving `MO="MI"` automatic promotion, and assert the normal output type and factor-two stability map.
