---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Fallible FFI queries and the non-fallible `AnyObject::clone` dispatcher

## Invariant and threat model

The C ABI entrypoints are expected to reject correctly allocated but wrongly typed opaque `AnyObject` parameters with a fallible error rather than aborting the process. This review excludes arbitrary raw-pointer forgery and relies on the caller passing a live `AnyObject` pointer. The relevant threat is robust handling of invalid types supplied through C, R or Python bindings, not a demonstrated secret-dependent exception or differential-privacy undercount.

A counterexample occurs when an `extern "C"` entrypoint clones an opaque query or metric distance **before** checking that the object has a supported type. The blanket `AnyObject::clone` implementation is partial and uses `.expect` and `unimplemented!` for unsupported runtime types; a panic inside the `extern "C"` call cannot unwind across the C ABI.

## Affected symbols and source audits

The following exact calls exist in pinned upstream `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`:

| Entry point | Argument cloned before validation | Further validation |
| --- | --- | --- |
| [`opendp_core__odometer_queryable_invoke`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/ffi/odometer.rs#L134-L145) | `query` (after queryable downcast) | `AnyMeasurement` downcast in type-erased adapter |
| [`opendp_core__odometer_queryable_privacy_loss`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/ffi/odometer.rs#L200-L208) | `d_in` (after queryable downcast) | Inner odometer `privacy_loss` transition |
| [`opendp_combinators__make_fully_adaptive_composition`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/fully_adaptive/ffi.rs) | Optional `d_in` via `as_ref(d_in).cloned()` | Constructor and privacy-distance checks |
| [`opendp_combinators__make_adaptive_composition`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/adaptive/ffi.rs) | Mandatory `d_in` | Constructor and privacy-distance checks |
| [`opendp_combinators__make_privacy_filter`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/privacy_filter/ffi.rs) | `d_in` and `d_out` | Privacy-filter constructor |

Their common dependency is [`AnyObject::clone`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/mod.rs#L1103-L1230). It recognizes a fixed set of runtime types, dispatches a failed clone for unsupported plain types and panics for certain other type categories.

Detailed scoped report: [odometer FFI source audit](../source/rust/src/core/ffi/odometer.rs.md). The three additional constructors were inspected **only** for argument-copy order, not their entire privacy proof or ownership model.

## Reasoning and evidence

1. The odometer queryable is downcast to `AnyOdometerQueryable`, but its supplied `query` or `d_in` is not downcast before cloning. For the invoke route, the correct type is `AnyMeasurement`, and the inner adapter does eventually perform that fallible downcast.
2. Passing `AnyObject::new(())` is a minimal validly allocated but unsupported opaque payload. The `()` type has no match in the `AnyObject::clone` dispatch table, so the clone's `.expect` panics. In contrast, an `i32` payload is cloneable but invalid as an invoke measurement, so it should reach the usual `FailedCast` return.
3. In each additional constructor, the clone operation occurs before the fallible constructor call. This is source evidence for the same structural hazard; no compiled witness for those three has been executed in this bounded review.
4. A [native pinned-revision Rust harness](../tools/integration/odometer_ffi_clone_panic.rs) and [GitHub Actions workflow](../.github/workflows/odometer-ffi-clone-panic.yml) reproduce the two odometer endpoints in child processes to prevent expected aborts from killing the test runner. The initial CI run compiled but the harness stopped early at a queryable-type downcast, because it omitted the FFI type-erasure adapter. The harness was corrected to convert the typed odometer into `AnyOdometer`. [Corrected pinned-native CI run 45112277828](https://github.com/opendp/opendp-audit/actions/runs/45112277828) **passed 2/2 tests**: a cloneable wrong-type invoke query returned `FfiResult::Err`, and both unsupported query types aborted in subprocesses as predicted.
5. Normal odometer query routing, type introspection and accounting are distinct from the clone failure. The source path does not show a free or unaccounted release; the finding is process termination on invalid opaque arguments.

## Findings

**Single deduplicated candidate:** [#104 — Opaque-distance cloning can abort multiple FFI entrypoints before validation](https://github.com/opendp/opendp-audit/issues/104). Do not create separate issues for the constructors until a genuinely independent failure mode is demonstrated. Related upstream [PR #3277](https://github.com/opendp/opendp/pull/3277) restores interactive wrappers during panic unwinding, not the checked-clone semantics of these public entrypoints.

## Unresolved questions

- Confirm the same-root prevalidation-clone behavior for all three additional FFI constructors with native subprocess tests; only the two odometer query endpoints have been reproduced against compiled OpenDP.
- Add targeted C ABI regression tests for the three additional constructors; specifically distinguish `FfiResult::Err` for invalid types from abnormal process termination.
- Prefer fallible cloning with explicit type validation and a returned `FailedCast` error; keep budget accounting in the existing inner queryable transition. Avoid trying to recover unwinds across `extern "C"`.
- Review other FFI sites that call `AnyObject::clone` on raw inputs, but do not infer they are reachable without tracing pointer and type preconditions.
