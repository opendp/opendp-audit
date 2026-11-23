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

- **Additional audit scope:** Scalar Rust `String` output, tracing `anyobjectptr_to_sexp` through `slice_to_sexp`, `slice_to_scalar`, and `voidptr_to_sexp`, focusing on the C pointer representation consumed by `mkChar`.

- **Additional audit scope:** The R `Vec<String>` result consumer: whether copying C strings into R closes Rust-owned backing allocations. This does not assess correctness of UTF-8 encoding or scalar-string pointer layout.

- **Additional audit scope:** Composite output conversion in `slice_to_tuple` and `slice_to_hashmap`: whether reading borrowed fields frees Rust-created scratch pointer arrays and `HashMap` key/value wrappers.

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `anyobjectptr_to_sexp` | memory/ownership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Analysis](#analysis): returned `FfiSlice` descriptor is not freed on the successful non-opaque path; cleanup is proposed in upstream PR #3176 |
| `voidptr_to_sexp` | correctness/ffi-scalar-string-layout | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Scalar String layout](#scalar-string-pointer-layout): treats `FfiSlice.ptr` as `char **` even when Rust supplies `char *` |
| `slice_to_scalar` | correctness/ffi-scalar-string-layout | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Scalar String layout](#scalar-string-pointer-layout): forwards the unadjusted pointer for `String` values |
| `voidptr_to_sexp` | memory/string-vector-backing-ownership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Backing allocations](#vecstring-backing-ownership): reads and copies `char **` data, but does not release Rust-owned buffers |
| `slice_to_tuple` | memory/composite-output-ownership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Composite ownership](#composite-output-backing-ownership) and [investigation](../../../../investigations/ffi-composite-output-ownership.md) |
| `slice_to_hashmap` | memory/composite-output-ownership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Composite ownership](#composite-output-backing-ownership) and [investigation](../../../../investigations/ffi-composite-output-ownership.md) |
## Analysis

### `anyobjectptr_to_sexp` — `memory/ownership`

**Conclusion:** On upstream `main` at this SHA, the non-opaque conversion path leaks at least the owned `FfiSlice` descriptor whenever `opendp_data__object_as_slice` succeeds. This is a native-memory resource-management finding, not evidence of a differential-privacy soundness failure. The descriptor leak is a static ownership mismatch; no heap profiler or runtime leak test was executed.

**Evidence:** After the special cases for `PrivacyProfile`, `AnyOdometerQueryable`, and `AnyQueryable`, the function calls `opendp_data__object_as_slice(obj)`, stores `slice_result.ok` in `FfiSlice *slice`, calls `slice_to_sexp(slice, type_name)`, and returns. It has no call to `opendp_data__slice_free`, no registered finalizer, and no cleanup branch for a nonlocal R exit. Rust's `FfiResult<*mut TO>` conversion uses `util::into_raw` for the `TO` value, while `opendp_data__slice_free` reclaims the descriptor and explicitly leaves the referenced data alone. Thus converting the output does not transfer or relinquish descriptor ownership.

**Reachability:** The generated R wrapper code maps `AnyObject *` results through this function, and `R/opendp/src/udf.c` also calls it when converting callback/transition arguments. Both sites can reach the non-opaque branch. The size of the leak depends on the number of conversions; this record does not assert measured growth.

**Existing upstream work:** [PR #3176](https://github.com/opendp/opendp/pull/3176), currently open and unmerged, replaces this path with `anyobjectptr_to_sexp_impl` and registers `slice` for `opendp_data__slice_free` in a per-call `R_ExecWithCleanup` resource scope. This directly addresses the descriptor omission in the examined path. Its integration and behavior on error paths have not been validated in this audit.

**Limitations:** This audit does not establish cleanup of separately allocated `FfiSlice.ptr` backing buffers, of nested `AnyObject` elements, or of all paths through `slice_to_sexp`. It does not exercise the R runtime, confirm the PR's CI results, or establish whether future upstream commits fix the finding.

**Related:** [Cross-language ownership investigation](../../../../investigations/r-ffi-slice-descriptor-ownership.md), [upstream PR #3176](https://github.com/opendp/opendp/pull/3176). No issue was opened.

### Scalar String pointer layout — `correctness/ffi-scalar-string-layout`

**Conclusion:** The R output converter's scalar `String` branch expects the address of a C-string pointer, whereas the Rust scalar producer supplies the address of the string bytes themselves. Passing a scalar `String` through `anyobjectptr_to_sexp` can cause an invalid read or crash. This is independent of the FFI descriptor leak noted above.

**Evidence:** `slice_to_sexp` routes atomic `String` through `slice_to_scalar` into `voidptr_to_sexp(raw->ptr, type_name, raw->len)`; `voidptr_to_sexp` calls `mkChar(((char **)input)[i])`. The Rust producer `string_to_raw` sets `raw->ptr` to a direct `char *`. The existing [scalar string identity test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/R/opendp/tests/testthat/test-data.R) expresses an intended user-facing roundtrip, but its success was not checked in this audit.

**Negative finding:** For `Vec<String>`, Rust returns a pointer to an array of `char *` elements, matching this R decoder's expected shape; this finding is specific to scalar `String` output.

**Limitations:** Source inspection and a standalone pointer-layout illustration only; no R package installation, R test execution, or sanitizer run. [Draft PR #3179](https://github.com/opendp/opendp/pull/3179) changes the Rust producer to return an owned `char **` view, not yet merged on upstream `main`.

**Related:** [Cross-language investigation](../../../../investigations/ffi-scalar-string-layout.md).

### Vec<String> backing ownership

**Conclusion:** R's `Vec<String>` output reader copies C-string contents into R-managed strings, but it cannot reclaim the separately allocated Rust C strings or the Rust pointer array. Its already-documented failure to release the outer `FfiSlice` is a distinct leak.

**Evidence:** `slice_to_sexp` delegates `Vec<String>` to `slice_to_vector`, then `slice_to_scalar`, then `voidptr_to_sexp`. That function uses `mkChar(((char **)input)[i])` for each element, copying bytes into R. The Rust producer `vec_string_to_raw` used `CString::into_raw` per string and `util::into_raw(vec)` for its pointer-array vector. No matching Rust destructor is invoked by the R `Vec<String>` read path. A [source-level test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/R/opendp/tests/testthat/test-data.R) describes a vector-of-strings identity roundtrip; this audit did not execute it.

**Limitations:** Static trace only. R's correct pointer-array interpretation does not establish allocation cleanup. Even adopting the descriptor-only cleanup from PR #3176 would not free `FfiSlice.ptr` children; the pending typed ownership redesign in [PR #3179](https://github.com/opendp/opendp/pull/3179) is relevant.

**Related:** [Cross-language investigation](../../../../investigations/ffi-string-vector-backing-ownership.md).

### Composite output backing ownership

**Conclusion:** `slice_to_tuple` copies values from a Rust-owned pointer-array view into an R list, and `slice_to_hashmap` reconstructs an R hash table from two Rust-created `AnyObject` vectors. Neither function claims or releases the Rust scratch allocations that hold those pointers. This is separate from the previously documented missing release of the outer `FfiSlice` descriptor in `anyobjectptr_to_sexp`.

**Evidence:** `slice_to_tuple` loops over `((void **)raw->ptr)[i]` and calls `voidptr_to_sexp`, while `slice_to_hashmap` reads `backing[0]` and `backing[1]` and calls `anyobjectptr_to_sexp` before constructing an R table. The Rust tuple producer used `util::into_raw([..])`; the Rust map producer used `util::into_raw` for both child `AnyObject`s and their pointer vector. Neither R function invokes `opendp_data__object_free` for the map's temporary children or a destructor for the pointer arrays. Even fixing the outer descriptor leak in [PR #3176](https://github.com/opendp/opendp/pull/3176) is insufficient to reclaim the pointer arrays, because `slice_free` explicitly excludes referenced storage.

**Limitations:** Static source inspection only; no R runtime test, native profiler, or sanitizer was executed. This report assesses scratch allocation cleanup, not all field types, R serialization correctness, or borrowed lifetime of opaque objects.

**Related:** [Cross-language investigation](../../../../investigations/ffi-composite-output-ownership.md); [pending draft PR #3179](https://github.com/opendp/opendp/pull/3179).

## Next checks

- After PR #3176 merges, inspect the merged SHA and test normal returns and nonlocal R error exits under a native leak checker.
- Separately audit backing-buffer ownership (particularly `Vec<String>`, tuples, and `Vec<AnyObject>`) rather than assuming `slice_free` releases all allocations.

- Follow the [Cross-language scalar string layout investigation](../../../../investigations/ffi-scalar-string-layout.md) and run scalar `String` outputs through a compiled, sanitizer-enabled binding before marking this pointer-layout concern resolved.

- Validate that the eventual merged `FfiSliceOwner` reclaims `Vec<String>` C strings and the pointer array after successful and exceptional conversions; add native-allocation regression measurements.

- Verify composite scratch-buffer cleanup under a native allocation checker after PR #3179 is merged; separately test normal conversions and failures.
