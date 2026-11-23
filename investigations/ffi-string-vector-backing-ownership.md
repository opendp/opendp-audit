---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Audited
---

# Legacy Vec<String> FFI backing-buffer ownership

## Invariant and threat model

Every native allocation made solely to expose a Rust `Vec<String>` to R or Python must have an owner and a corresponding destructor on normal returns and conversion failures. The Rust strings and temporary pointer array are not owned by the host's copied strings. Missing cleanup accumulates allocations on repeated conversions, potentially exhausting memory. This is an availability and memory-management property, not evidence of a differential-privacy privacy-budget violation.

## Affected symbols and source audits

- [Rust `opendp_data__object_as_slice::vec_string_to_raw`](../source/rust/src/data/ffi/mod.rs.md) allocates and exposes temporary strings and their pointer array; [pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/mod.rs#L473-L484).
- [Rust `util::into_c_char_p` and `util::into_raw`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/ffi/util.rs#L458-L486) transfer ownership to raw pointers without automatic destructor registration.
- [Rust `opendp_data__slice_free`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/mod.rs#L936-L950) frees the *descriptor* but expressly not the pointee.
- [R `voidptr_to_sexp`](../source/R/opendp/src/convert.c.md) copies `char **` string elements using `mkChar`; [pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/R/opendp/src/convert.c#L278-L295).
- [Python `_slice_to_vector`](../source/python/src/opendp/_convert.py.md) copies each vector string by decoding the C pointer's bytes; [pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/_convert.py#L595-L629).

## Reasoning and evidence

1. In `vec_string_to_raw`, `map(util::into_c_char_p)` invokes `CString::into_raw` for every successfully converted element. Rust obtains raw C pointers, not RAII-managed `CString` values.
2. `vec.as_ptr()` is exposed as the returned `FfiSlice.ptr`; `util::into_raw(vec)` then boxes the vector value and leaks that owner. No stored owner of the C strings is retained for cleanup, and no pointer-array cleanup is registered.
3. `opendp_data__slice_free` reclaims the top-level `FfiSlice` only. The R `mkChar` loop and the Python `.decode()` loop merely copy data and do not call `CString::from_raw`, `opendp_data__str_free`, or an equivalent pointer-array finalizer.
4. On a conversion error caused by a later embedded NUL, the fallible `collect()` returns early. Dropping a `Vec<*mut c_char>` of previously successful elements does not reclaim the already detached `CString` allocations. Thus cleanup is incomplete even when no output `FfiSlice` is returned.
5. This differs from the [scalar-string pointer-layout finding](ffi-scalar-string-layout.md): the `Vec<String>` pointer-array layout is appropriate for R and Python, but its owned storage is not reclaimed. It also differs from the [R descriptor leak](r-ffi-slice-descriptor-ownership.md) and [temporary AnyObject pointer-array leak](ffi-vector-slice-lifetime.md).

[Draft PR #3179](https://github.com/opendp/opendp/pull/3179) implements `FfiSliceOwner::string` using a kept-alive `CString` and `FfiSliceOwner::pointers` using a kept-alive vector. The change is open/unmerged and is not present on the pinned upstream `main`.

**Executed:** Commit-pinned code inspection of Rust allocation/destructor contracts, R and Python output readers, and draft PR #3179. No dynamic OpenDP workload, allocation counter, sanitizer, or binding integration test was executed.

## Findings

**Confirmed by static source-level ownership tracing:** The legacy `Vec<String>` FFI output path leaks backing storage during successful conversions and leaks earlier C strings after partial conversion failure. Native runtime growth and severity have not been measured. **Upstream disposition: pending draft PR #3179.** No duplicate issue or PR was created.

## Unresolved questions

- Execute repeated `Vec<String>` output roundtrips and embedded-NUL failures under Valgrind/ASan or another native-allocation profiler. Distinguish normal allocator caching from unreclaimed allocations.
- Verify after PR #3179 merges that normal returns and exceptional host-language exits release all `FfiSliceOwner` keepalives, including if a string conversion fails halfway through.
- Separately audit ownership of leaked tuple, `HashMap`, and Polars backing allocations; these are outside the bounded `Vec<String>` review.
