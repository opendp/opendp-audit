---
schema_version: 1
source: rust/src/core/ffi/odometer.rs
updated: 2026-11-23
---

# `rust/src/core/ffi/odometer.rs`

## Scope and assumptions

- **Scope:** Non-deprecated odometer C ABI entry points for odometer invocation, opaque queryable invocation, privacy-loss queries, metadata introspection and odometer destruction. Includes the relevant `AnyObject` cloning and type-erased queryable adapter, but not a full audit of every supported language converter or the fully adaptive composition theorem.
- **Invariants:** Type introspection must not consume privacy budget. A supported invoke query must reach the same odometer accounting transition as the Rust API, with invalid query types rejected before private execution. Invalid opaque inputs should produce `FfiResult::Err` rather than unwind/abort across `extern "C"`. Ownership of pointers returned through `FfiResult` should be unambiguous.
- **Assumptions:** The Rust odometer constructor implements its privacy-map and sequentiality contracts, all input pointers originate from correctly allocated OpenDP objects, and legitimate queries carry expected FFI types. This audit focuses on type-dispatch/ABI correctness, not malicious pointer forgery or arbitrary callback behavior.
- **Pinned sources:** [odometer FFI](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/ffi/odometer.rs), [type-erased odometer adapter](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/ffi/any.rs), [opaque clone dispatcher](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/mod.rs#L1103-L1230), [core odometer query API](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs), [interactive queryable](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/interactive/mod.rs) and [FFI result ownership](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/ffi/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `opendp_core__odometer_invoke` | privacy/ffi-odometer-dispatch | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Invocation bridge](#invocation-and-accounting-bridge) |
| `opendp_core__odometer_queryable_invoke` | privacy/ffi-odometer-dispatch | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Normal path and wrong-type abort](#opaque-clone-before-type-validation) |
| `opendp_core__odometer_queryable_privacy_loss` | privacy/ffi-odometer-dispatch | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Loss query and wrong-type abort](#opaque-clone-before-type-validation) |
| `opendp_core__odometer_queryable_invoke_type` | privacy/ffi-odometer-dispatch | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Introspection trace](#internal-type-introspection) |
| `opendp_core__odometer_queryable_privacy_loss_type` | privacy/ffi-odometer-dispatch | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Introspection trace](#internal-type-introspection) |
| `opendp_core___odometer_free` | memory/ffi-queryable-ownership | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Pointer ownership limits](#pointer-and-ffi-boundaries) |
| `opendp_core__odometer_queryable_invoke` | correctness/ffi-panic-safety | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Candidate defect #104](https://github.com/opendp/opendp-audit/issues/104) |
| `opendp_core__odometer_queryable_privacy_loss` | correctness/ffi-panic-safety | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Candidate defect #104](https://github.com/opendp/opendp-audit/issues/104) |

## Analysis

### Invocation and accounting bridge

`opendp_core__odometer_invoke` borrows the pointer to an `AnyOdometer` and an input `AnyObject`, calls `Odometer::invoke`, then converts the returned `AnyOdometerQueryable` to an owned `AnyObject` or returns a fallible error. The core invocation evaluates the odometer's function to create its stateful queryable; it does not itself release a child measurement.

For a *supported* `AnyMeasurement` query, `opendp_core__odometer_queryable_invoke` sends `OdometerQuery::Invoke` to `Queryable::eval`. In the type-erased adapter in `rust/src/ffi/any.rs`, `Query::External(OdometerQuery::Invoke(meas))` downcasts the argument to `AnyMeasurement` and calls `inner_qbl.invoke(meas.clone())`. That invokes the same child-accounting transition as the Rust odometer; no alternative release path is evident in the inspected dispatch layer. `privacy_loss` sends `OdometerQuery::PrivacyLoss` through the corresponding inner query, rather than computing an unaudited budget independently.

The audited guarantee is the *dispatch equivalence conditional on the core odometer and measurement contracts*, not an independent proof that all measurements' declared privacy maps are correct. Prior fully adaptive composition investigation covers the bookkeeping itself.

### Internal type introspection

Both `opendp_core__odometer_queryable_invoke_type` and `opendp_core__odometer_queryable_privacy_loss_type` make `Queryable::eval_internal` calls with distinct marker types. The type-erased adapter recognizes those markers in its `Query::Internal` arm and returns `Type::of::<AnyMeasurement>()` and the saved input metric distance `QI`, respectively. For an unwrapped queryable, neither invokes a measurement nor enters the `OdometerQuery::Invoke` external branch, so neither consumes a privacy-budget entry. A surrounding interactive wrapper may enforce an existing permission policy even on these internal calls; this does not create a release.

Existing upstream `core/ffi/odometer.rs` unit tests verify normal `odometer_invoke` and wrong input-dataset type. They do not cover these introspections, malformed invoke query objects or malformed privacy-loss query objects. Native type-introspection and wrapper interactions remain unexecuted in this audit.

### Opaque clone before type validation

Both public query endpoints are `extern "C"` functions. After validating that the *queryable* itself is an `AnyOdometerQueryable`, they clone the *caller-provided query object*: `AnyOdometerQuery::Invoke(try_as_ref!(query).clone())` or `try_as_ref!(d_in).clone()`. This occurs **before** the adapter can downcast `Invoke` to `AnyMeasurement` or validate a distance type.

`AnyObject::clone` in [`rust/src/data/ffi/mod.rs` L1103–L1230](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/mod.rs#L1103-L1230) is a restricted runtime type dispatcher. Unsupported `TypeContents::PLAIN` values produce `Err` in `dispatch!`, which is unwrapped by `.expect("Clone is not implemented ...")`; unsupported arrays/slices invoke `unimplemented!`. For instance `AnyObject::new(())` is a well-formed opaque object but not a recognized cloneable payload. Passing that object as an invoke query or privacy-loss distance reaches a panic before the fallible downcast. A panic from an `extern "C"` boundary aborts the process on Rust's non-unwinding C ABI.

This is a concrete **source-level invalid-type process-termination defect**, reported in [audit candidate #104](https://github.com/opendp/opendp-audit/issues/104). It affects invalid FFI calls and may be a robustness/availability issue; there is **no shown secret-dependent crash, privacy-budget undercount, or DP violation**. An ordinary mismatched but clone-supported `i32` invokes the normal `FailedCast` path, so the bug is specifically the prevalidation clone.

The [dedicated Rust regression](https://github.com/opendp/opendp-audit/blob/main/tools/integration/odometer_ffi_clone_panic.rs) tests both C entrypoints in separate child processes and contrasts supported wrong-type behavior. [Native CI run 45112277828](https://github.com/opendp/opendp-audit/actions/runs/45112277828) compiled the pinned OpenDP revision `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` with `contrib,ffi` and **passed 2/2 tests**: an invalid but clone-supported `i32` invoke query returned `FfiResult::Err`, while both unsupported `()` query types triggered the expected process termination across `extern "C"` (observed from subprocesses). This is native confirmation of the malformed-input availability defect, not a claim about privacy loss.

### Pointer and FFI boundaries

The entrypoints use `try_as_ref!`/`try_as_mut_ref!` for null checking; opaque queryable downcasts are fallible. `opendp_core___odometer_free` consumes its pointer using `util::into_owned`, while successful queryables and outputs transfer an owned pointer through `FfiResult`. The Rust wrappers do not themselves show a double-free in this narrow path. Full `memory/ffi-queryable-ownership` coverage remains **Partial**: host-language pointer lifetimes, FFI callback retention, aliasing of mutable raw pointers, and panic/unwind cleanup have not been tested.

Upstream [PR #3277](https://github.com/opendp/opendp/pull/3277) addresses wrapper restoration under panics; [PR #3176](https://github.com/opendp/opendp/pull/3176) addresses R callback and resource lifetimes. Neither is treated as fixing this distinct invalid-query prevalidation clone path.

## Findings

- **New source-level defect, candidate #104:** Unsupported opaque invoke/distance query types can panic inside `AnyObject::clone` before the ordinary fallible query validation; both extern-C functions expose a potential process-abort boundary. Native regression confirmed by [pinned CI 45112277828](https://github.com/opendp/opendp-audit/actions/runs/45112277828) (two tests passed).
- **No additional accounting defect established:** Supported query types reach the existing stateful odometer transitions, and internal type introspection has an explicit type-only fast path. This is not a proof of arbitrary callbacks' validity or of all language bindings.
- **Deduplication:** [Cross-file investigation](../../../../../investigations/ffi-opaque-clone-before-validation.md) consolidates three additional constructors with the same prevalidation-clone pattern. Searches of upstream and audit issues/PRs found no existing report or pending correction of this exact odometer FFI clone failure. Scope does not overlap [non-adaptive composition task #96](https://github.com/opendp/opendp-audit/issues/96).

## Next checks

1. Extend the successful native witness to the three additional source-identified FFI constructors; keep #104 as the single root-cause candidate.
2. Introduce an upstream regression expecting **`FfiResult::Err`, not process abort**, for unsupported `AnyObject` query/distance payloads. Implement fallible cloning or validate the payload before copying, without bypassing the original stateful odometer transition.
3. Exercise both type-introspection calls and queryable pointer lifetime across R/Python bindings, including user-defined distance types and interposed recursive wrappers.
