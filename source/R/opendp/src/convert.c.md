---
schema_version: 1
source: R/opendp/src/convert.c
updated: 2026-11-22
---

# `R/opendp/src/convert.c`

## Scope and assumptions

- **Audit scope:** Heap ownership of the `FfiSlice *` returned by `opendp_data__object_as_slice` in `anyobjectptr_to_sexp`, for non-opaque Rust objects successfully converted to R values.
- **Invariant:** Each owned `FfiSlice` descriptor returned by the Rust API is released once after the R consumer finishes reading it, including when R evaluation exits nonlocally. Releasing the descriptor must not free the borrowed storage to which its `ptr` points.
- **Assumptions:** Upstream `main` at the commit below; `opendp_data__object_as_slice` uses its Rust `FfiResult<*mut FfiSlice>` return contract. This report distinguishes descriptor ownership from pointed-to buffer ownership.
- **Source links:** [R conversion function](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/R/opendp/src/convert.c#L792-L846), [Rust result allocation contract](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/ffi/mod.rs#L100-L125), [Rust slice destructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/mod.rs#L936-L950).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `anyobjectptr_to_sexp` | memory/ownership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Analysis](#analysis): returned `FfiSlice` descriptor is not freed on the successful non-opaque path; cleanup is proposed in upstream PR #3176 |

## Analysis

### `anyobjectptr_to_sexp` — `memory/ownership`

**Conclusion:** On upstream `main` at this SHA, the non-opaque conversion path leaks at least the owned `FfiSlice` descriptor whenever `opendp_data__object_as_slice` succeeds. This is a native-memory resource-management finding, not evidence of a differential-privacy soundness failure. The descriptor leak is a static ownership mismatch; no heap profiler or runtime leak test was executed.

**Evidence:** After the special cases for `PrivacyProfile`, `AnyOdometerQueryable`, and `AnyQueryable`, the function calls `opendp_data__object_as_slice(obj)`, stores `slice_result.ok` in `FfiSlice *slice`, calls `slice_to_sexp(slice, type_name)`, and returns. It has no call to `opendp_data__slice_free`, no registered finalizer, and no cleanup branch for a nonlocal R exit. Rust's `FfiResult<*mut TO>` conversion uses `util::into_raw` for the `TO` value, while `opendp_data__slice_free` reclaims the descriptor and explicitly leaves the referenced data alone. Thus converting the output does not transfer or relinquish descriptor ownership.

**Reachability:** The generated R wrapper code maps `AnyObject *` results through this function, and `R/opendp/src/udf.c` also calls it when converting callback/transition arguments. Both sites can reach the non-opaque branch. The size of the leak depends on the number of conversions; this record does not assert measured growth.

**Existing upstream work:** [PR #3176](https://github.com/opendp/opendp/pull/3176), currently open and unmerged, replaces this path with `anyobjectptr_to_sexp_impl` and registers `slice` for `opendp_data__slice_free` in a per-call `R_ExecWithCleanup` resource scope. This directly addresses the descriptor omission in the examined path. Its integration and behavior on error paths have not been validated in this audit.

**Limitations:** This audit does not establish cleanup of separately allocated `FfiSlice.ptr` backing buffers, of nested `AnyObject` elements, or of all paths through `slice_to_sexp`. It does not exercise the R runtime, confirm the PR's CI results, or establish whether future upstream commits fix the finding.

**Related:** [Cross-language ownership investigation](../../../../investigations/r-ffi-slice-descriptor-ownership.md), [upstream PR #3176](https://github.com/opendp/opendp/pull/3176). No issue was opened.

## Next checks

- After PR #3176 merges, inspect the merged SHA and test normal returns and nonlocal R error exits under a native leak checker.
- Separately audit backing-buffer ownership (particularly `Vec<String>`, tuples, and `Vec<AnyObject>`) rather than assuming `slice_free` releases all allocations.
