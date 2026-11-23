---
schema_version: 1
source: rust/src/transformations/make_stable_lazyframe/source/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_lazyframe/source/mod.rs`

## Scope and assumptions

- **Audit scope:** `make_stable_source` handling of `DslPlan::DataFrameScan`, input/output domain and metric identity, and preservation of invocation-time private plan rather than constructor-time plan. Reviewed the caller `DslPlan::make_stable` and `make_stable_lazyframe`'s final adapter.
- **Invariants:** Reject a constructor-time plan that is not `DataFrameScan`; do not inspect the embedded private frame in a permitted source; return an identity transformation with cloned input/output domains and metrics, an identity function, and identity stability map. Invocation must use the supplied private argument, not the constructor-time plan.
- **Assumptions:** Rust `Clone::clone` on `DslPlan` preserves its logical-plan contents; the outer metric defines a valid `MetricSpace` for `DslPlanDomain`; no soundness of user-supplied `FrameDomain` descriptors is inferred from construction. This was a source-level review only, without a native Rust/OpenDP runtime regression.
- **Pinned source:** [source constructor](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/transformations/make_stable_lazyframe/source/mod.rs), [DSL dispatcher and LazyFrame adapter](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/transformations/make_stable_lazyframe/mod.rs), [FrameDomain and DslPlanDomain](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/domains/polars/frame/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `opendp::transformations::make_stable_lazyframe::source::make_stable_source` | privacy/source-identity-stability | Audited | `a010591f55b1713c926f8e355091471634480307` | [Identity map and private-plan handling](#identity-map-and-private-plan-handling). No counterexample in the scoped source-level invariant. |
| `opendp::transformations::make_stable_lazyframe::source::make_stable_source` | correctness/source-plan-validation | Audited | `a010591f55b1713c926f8e355091471634480307` | [DataFrameScan-only constructor check](#dataframescan-only-constructor-check). Non-DataFrameScan rejected before transformation construction. |
| `opendp::transformations::make_stable_lazyframe::make_stable_lazyframe` | privacy/source-adapter-preservation | Partial | `a010591f55b1713c926f8e355091471634480307` | [Caller/adapter boundary](#calleradapter-boundary). Argument plan passed to the source transformation; downstream query operators, optimizations and execution not separately tested. |

## Analysis

### Identity map and private-plan handling

The returned transformation has equal input/output domains and equal input/output metrics by construction: arguments are `input_domain.clone()`, `input_metric.clone()`, `input_domain`, and `input_metric`. The function is `Function::new(Clone::clone)`, so it returns a clone of the **invocation argument**. It does not capture `plan` and return a static constructor-time dataframe or refer to the private dataframe used to build the check. The stability map is `StabilityMap::new(Clone::clone)`; hence for any valid input distance `d`, the reported output distance is the same `d`. An identity transformation is 1-Lipschitz in the same metric by definition.

**Conclusion:** No violation of identity-function or identity-stability contracts identified in this scoped implementation.

**Limitations:** This is structural reasoning, not execution of the `DslPlan` or `LazyFrame` constructor and invoker in compiled OpenDP. It assumes other transformations validate the individual query steps and input domains. It does not establish dataset membership checking at the public FFI boundary (which may be disabled under `polars-ffi`).

### DataFrameScan-only constructor check

`let DslPlan::DataFrameScan { df: _, .. } = plan else { return fallible!(MakeTransformation, "Expected dataframe scan"); }` inspects only the variant and does not access the embedded `df`. A non-DataFrameScan plan is rejected before `Transformation::new`; accepting a DataFrameScan plan creates the same identity function regardless of the private values.

**Conclusion:** Source-level validation matches the documented restricted constructor scope.

**Limitations:** No compiled Rust tests of parser/plan-variant behavior were executed.

### Caller/adapter boundary

The `StableDslPlan<FrameDistance<M>, FrameDistance<M>>` dispatch in `make_stable_lazyframe/mod.rs` invokes `source::make_stable_source` for `DslPlan::DataFrameScan`. `make_stable_lazyframe` constructs the outer `Function::new_fallible` with `f_input.eval(&arg.logical_plan)?`, so it passes the invocation-time private input plan; the resulting `LazyFrame` preserves the argument's current optimization settings.

The dispatcher is separately responsible for other `DslPlan` cases and its trait dispatch; their stability maps are **outside** this bounded source audit. No inference about all Polars input-data operations or optimizer transformations is made.

## Findings and next checks

- **No new defect** within the source identity, constructor-plan validation, and basic caller wiring invariants. Searches of open and closed upstream/audit issues and upstream PRs for `make_stable_source` / DataFrameScan did not reveal prior reports of these invariants failing.
- **Native verification not run:** add a Rust test for DataFrameScan acceptance, non-DataFrameScan rejection, and invocation-time plan passthrough, if this constructor's behavior changes.
- **Related task:** [completed audit #146](https://github.com/opendp/opendp-audit/issues/146). No issue filed because no distinct defect was established.
