---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Audited
---

# Scalar String pointer layout across Rust, R, and Python FFI

## Invariant and threat model

A scalar Rust `String` converted into a host-language string must use the pointer shape the receiving binding expects. R and Python interpret `FfiSlice.ptr` as `char **`: an address containing a `char *` pointing to a NUL-terminated C string. A direct `char *` pointing at the bytes is not interchangeable with `char **`. Treating bytes as an address can cause invalid memory access and process termination. This finding concerns correctness and memory safety, not differential-privacy accounting.

## Affected symbols and source audits

- [Rust `opendp_data__object_as_slice::string_to_raw`](../source/rust/src/data/ffi/mod.rs.md) emits a direct `char *` for scalar `String`; [pinned source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/mod.rs#L465-L472).
- [R `slice_to_scalar` and `voidptr_to_sexp`](../source/R/opendp/src/convert.c.md) read a `char **` when converting `String`; [pinned source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/R/opendp/src/convert.c#L278-L293).
- [Python `_slice_to_string`](../source/python/src/opendp/_convert.py.md) casts to `POINTER(c_char_p)` before dereferencing; [pinned source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/_convert.py).
- The [R scalar identity test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/R/opendp/tests/testthat/test-data.R) includes a `String` case. The generated [R wrapper converter](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/opendp_tooling/src/codegen/r/c.rs) routes `AnyObject *` through `anyobjectptr_to_sexp`.

## Reasoning and evidence

1. Rust's `string_to_raw` gets a C string from `util::into_c_char_p(string.clone())`, then passes that pointer **directly** to `FfiSlice::new(..., 1)`. It does not build a one-element pointer array. In contrast, the `Vec<String>` branch builds a `Vec<*mut c_char>` and passes `vec.as_ptr()`, which is an array.
2. R passes `FfiSlice.ptr` to `voidptr_to_sexp` and reads `((char **)input)[0]` for a scalar string. Python's `_slice_to_string` reads `ctypes.cast(raw.contents.ptr, POINTER(c_char_p)).contents.value`. Both dereference the location holding the *bytes* as if it held a `char *`.
3. A minimal layout illustration with Python `ctypes` allocated eight bytes `b'A\\0\\0\\0\\0\\0\\0\\0'` and read them once through `POINTER(c_void_p)`. The resulting value was `65` (`0x41`), rather than the buffer's actual address. This exercise demonstrates the pointer-layout confusion but is **not** an execution of OpenDP.
4. [Draft upstream PR #3179](https://github.com/opendp/opendp/pull/3179) addresses this: its `FfiSliceOwner::from_object` scalar `String` branch uses `owner.string(...)` followed by `owner.pointers(vec![ptr])`, producing a `char **` view with owned scratch storage. The PR was open, draft, and unmerged at review time. [PR #3176](https://github.com/opendp/opendp/pull/3176) handles R resource lifetimes but does not alone change the legacy Rust scalar layout.

**Executed:** GitHub source and PR patch inspection, plus a standalone `ctypes` pointer-layout illustration. No OpenDP R/Python execution, debugger, native memory checker, or sanitizer. No upstream source was modified.

## Findings

**Static source-supported pointer-layout mismatch on pinned `main`.** A plain scalar `String` output is encoded as `char *` where both R and Python decode it as `char **`, implying invalid dereference risk. This is distinct from the already documented FFI descriptor and backing-buffer leaks. **Upstream disposition: Pending draft PR #3179**, not fixed on `main`. There is no new audit issue because the upstream patch already targets the mismatch, and the session does not authorize creating issues.

## Unresolved questions

- Run a compiled OpenDP regression on scalar `String` output in both R and Python, ideally under AddressSanitizer/Valgrind, to characterize the runtime failure and verify the repaired view layout.
- After PR #3179 merges, inspect the merged implementation and verify correct lifetime of its scalar C string and pointer-array owner, including exception paths.
- Audit the separately owned `Vec<String>` backing buffers for complete cleanup; this report only establishes that their pointer-array **shape** matches the decoders.
