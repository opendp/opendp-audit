---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Partial
---

# Temporary pointer-array lifetime across Python and Rust FFI

## Invariant and threat model

When converting vectors of opaque Rust objects into Python, every Rust-owned temporary allocation must have a release path after successful conversion and after exceptions. Borrowed element pointers must remain borrowed, while wrapper buffers must not accumulate across repeated invocations. This is a resource-exhaustion/availability property, not a differential-privacy guarantee.

## Affected symbols and source audits

- [`python/src/opendp/_convert.py` — `_slice_to_vector`](../source/python/src/opendp/_convert.py.md), [commit-pinned upstream](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/_convert.py).
- [`rust/src/data/ffi/mod.rs` — `opendp_data__ffislice_of_anyobjectptrs` and `opendp_data__slice_free`](../source/rust/src/data/ffi/mod.rs.md), [commit-pinned upstream](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/mod.rs).
- [`python/src/opendp/_lib.py` — `FfiSlicePtr.__del__`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/_lib.py): discards dependency references only.

## Reasoning and evidence

At upstream SHA `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`, the vector branch for `AnyObject`, `Expr`, or `Bound` invokes `ffislice_of_anyobjectptrs` and shadows the original `raw` pointer. Rust constructs a fresh pointer vector and calls `vec_any_ptrs.leak()`, then returns a new `FfiSlice` referencing that allocation. Python reads the array but has no `try/finally` or equivalent deallocator for the helper's new view. Its pointer destructor only removes keepalive entries. Moreover, the exported `slice_free` deliberately frees only the `FfiSlice` header, not its referent; thus adding a header-only free would not reclaim the leaked vector.

The outer `c_to_py` does call `slice_free(ffi_slice)` for the original `object_as_slice` view. That does **not** address the distinct helper-produced allocation. This leak occurs even if element conversion succeeds, and conversion exceptions do not improve the cleanup behavior. The Rust vector allocation grows with the number of converted elements. Exact retained byte counts and end-to-end reproduction remain unmeasured.

This is a **source-level finding**, not a native memory-profile reproduction. No upstream code was modified. The audit repository has no existing source reports or audit-task issues at the start of this run; no task issue or exclusive lease was created because issue creation is prohibited for this session.

## Findings

**Candidate, source-supported memory leak on current `main`; runtime verification outstanding.** No privacy guarantee failure is established. Upstream draft [PR #3179](https://github.com/opendp/opendp/pull/3179) specifically replaces legacy non-Polars output conversion with Rust-owned scratch views, removes the helper, and uses `slice_owner_free`. The PR is open/draft and is therefore a **pending fix**, not a fix on `main`. Upstream [issue #397](https://github.com/opendp/opendp/issues/397) documents historical Python-binding memory leaks but was closed in 2021; it should not be treated as proof that this precise path was resolved or as an active tracking ticket. No new GitHub issue was created.

## Unresolved questions

- Reproduce on current `main` with a repeated vector-conversion workload and a native memory checker; separate allocator growth from cache effects.
- Audit [PR #3179](https://github.com/opendp/opendp/pull/3179) after it is merged, including exception cleanup and ownership of all nested child buffers.
- Validate a regression test that fails on the reviewed commit and passes after the ownership redesign.
