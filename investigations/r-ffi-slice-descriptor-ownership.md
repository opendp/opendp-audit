---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Audited
---

# R FFI object-to-slice descriptor ownership

## Invariant and threat model

After `opendp_data__object_as_slice` returns a successful owned `FfiSlice *`, an R caller must release the descriptor exactly once, whether conversion finishes normally or R performs a nonlocal exit. The `FfiSlice.ptr` data is a separate ownership concern. Failure manifests as unreclaimed native allocations during repeated conversions; it does not by itself demonstrate a privacy-budget or soundness violation.

## Affected symbols and source audits

- [R `anyobjectptr_to_sexp`](../source/R/opendp/src/convert.c.md): consumes the returned descriptor without releasing it on upstream `main`.
- [Rust `opendp_data__object_as_slice` and `opendp_data__slice_free`](../source/rust/src/data/ffi/mod.rs.md): allocate and deallocate the descriptor, respectively.
- [Pinned R source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/R/opendp/src/convert.c#L792-L846), [pinned Rust source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/mod.rs#L439-L950), and [FFI result implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/ffi/mod.rs#L95-L117).

## Reasoning and evidence

1. `opendp_data__object_as_slice` uses `.into()` on `Fallible<FfiSlice>`. The Rust `FfiResult<*mut TO>` conversion places the successful value behind `util::into_raw`, giving the caller an owned descriptor.
2. `opendp_data__slice_free` is explicitly documented for cleaning up this descriptor, without freeing the backing data.
3. On pinned `main`, R's `anyobjectptr_to_sexp` receives `slice_result.ok`, converts it with `slice_to_sexp`, and returns without `slice_free` or another cleanup mechanism. Generated R wrappers and the R callback/transition glue can invoke this function.
4. Python's `c_to_py` releases the same resource in a `finally` block, supporting the contract as implemented in another binding.
5. [Open, unmerged PR #3176](https://github.com/opendp/opendp/pull/3176) adds `slice_cleanup` and registers the resource under an `R_ExecWithCleanup` scope. The patch was inspected; the change is not present in the pinned `main`.

**Executed:** Source and PR patch inspection only. No R/Rust execution, allocation profiling, or sanitizer run. A minimally reproducible dynamic check is to repeatedly convert non-opaque `AnyObject` outputs through the R binding and compare outstanding native allocations before and after applying PR #3176.

## Findings

**Confirmed by static ownership tracing, current at pinned SHA:** An unreleased `FfiSlice` descriptor in the R conversion path. Impact: native memory growth on repeated conversions; no demonstrated privacy guarantee violation. **Upstream disposition: Pending PR #3176** (open, unmerged). No duplicate candidate issue was opened in this audit repository.

## Unresolved questions

- Verify PR #3176 after merge, including normal and exceptional R exits and nested callback reentrancy.
- Independently assess ownership of backing allocations returned through `FfiSlice.ptr`, especially tuples and string/object vectors; the descriptor destructor intentionally does not release these buffers.
- Confirm the magnitude and practical observability of the leak with a native allocation profiler or sanitizer.
