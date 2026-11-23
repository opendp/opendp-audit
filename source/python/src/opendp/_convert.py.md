---
schema_version: 1
source: python/src/opendp/_convert.py
updated: 2026-11-22
---

# `python/src/opendp/_convert.py`

## Scope and assumptions

- **Audit scope:** `_slice_to_vector` when decoding `Vec<AnyObject>`, `Vec<Expr>`, or `Vec<Bound>` from an `FfiSlicePtr`; cleanup of the temporary pointer-array conversion only.
- **Invariant:** Every Rust allocation created solely to convert a vector into Python is eventually released on success and on conversion exceptions; borrowed `AnyObject` elements are not individually freed.
- **Assumptions:** The input slice originates from a valid OpenDP FFI object; the generated `ffislice_of_anyobjectptrs` wrapper invokes the Rust export examined below.
- **Source:** [Python conversion at the reviewed commit](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/_convert.py), [Python pointer finalizer](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/_lib.py).

- **Additional audit scope:** Scalar `String` conversion in `_slice_to_string`, compared with the Rust `string_to_raw` producer. This is separate from the existing temporary-vector lifetime review.

- **Additional audit scope:** The Python `Vec<String>` result consumer: whether decoded `str` values close Rust-owned backing allocations. This is separate from the prior `Vec<AnyObject>` helper leak.

- **Additional audit scope:** Composite output conversion in `_slice_to_tuple` and `_slice_to_hashmap`: lifetime of the Rust scratch pointer arrays and temporary `HashMap` child `AnyObject` values, independent of the outer descriptor.

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `_slice_to_vector` | memory/temporary-slice-ownership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file investigation](../../../../investigations/ffi-vector-slice-lifetime.md) |
| `_slice_to_string` | correctness/ffi-scalar-string-layout | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Scalar String layout](#scalar-string-pointer-layout): dereferences `FfiSlice.ptr` as `char **` although the scalar Rust producer returns `char *` |
| `_slice_to_vector` | memory/string-vector-backing-ownership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Backing allocations](#vecstring-backing-ownership): decodes `Vec<String>` data but does not reclaim Rust-owned buffers |
| `_slice_to_tuple` | memory/composite-output-ownership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Composite ownership](#composite-output-backing-ownership) and [investigation](../../../../investigations/ffi-composite-output-ownership.md) |
| `_slice_to_hashmap` | memory/composite-output-ownership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Composite ownership](#composite-output-backing-ownership) and [investigation](../../../../investigations/ffi-composite-output-ownership.md) |
## Analysis

### `_slice_to_vector` — `memory/temporary-slice-ownership`

**Conclusion:** This path does not release the separate Rust slice and pointer vector produced by `ffislice_of_anyobjectptrs`. The native helper explicitly leaks the pointer-vector allocation. This is a resource-lifetime finding, not a demonstrated privacy-accounting error.

**Evidence:** For the three specified element types, `_slice_to_vector` assigns `raw = ffislice_of_anyobjectptrs(raw)` and then passes an array of borrowed pointers to `c_to_py`. It has no cleanup for the replacement slice on either normal or exceptional returns. The outer `c_to_py` finally block frees only the original `object_as_slice` result; `FfiSlicePtr.__del__` removes Python keepalive references, not a native slice. Rust's `slice_free` explicitly frees the header but not its referenced buffer. See the [investigation](../../../../investigations/ffi-vector-slice-lifetime.md).

**Limitations:** Source-level audit only. Native allocations, exceptional conversions, and memory growth were not tested under Valgrind or a running OpenDP Python installation. Other conversion cases and borrowed-element safety are outside this property.

**Related:** [Upstream draft PR #3179](https://github.com/opendp/opendp/pull/3179) replaces this path with Rust-owned output views but was unmerged at the reviewed commit.

### Scalar String pointer layout — `correctness/ffi-scalar-string-layout`

**Conclusion:** `_slice_to_string` interprets `raw.contents.ptr` as `ctypes.POINTER(ctypes.c_char_p)` and reads `.contents.value`. Rust's scalar `String` producer provides the underlying C-string bytes directly. Therefore the Python decoder interprets string bytes as an address, creating an invalid dereference risk. Python's `_string_to_slice` uses the correct `char **` input representation, which highlights the asymmetric output contract.

**Evidence:** [Python decoder](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/_convert.py), [Rust scalar string producer](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/mod.rs#L465-L472). `_slice_to_string` is called for `type_name == "String"` in `_slice_to_py`; `c_to_py` invokes `_slice_to_py` on `AnyObject` results after Rust's `object_as_slice`.

**Limitations:** No OpenDP Python runtime test or sanitizers were executed. This finding is limited to scalar string output and does not imply the `Vec<String>` pointer layout is wrong. [Draft PR #3179](https://github.com/opendp/opendp/pull/3179) returns a pointer array under the replacement owner, but remains unmerged.

**Related:** [Cross-language investigation](../../../../investigations/ffi-scalar-string-layout.md).

### Vec<String> backing ownership

**Conclusion:** Python's `Vec<String>` converter decodes each C string and copies it into Python-owned strings, but it never frees the independently Rust-owned C-string allocations or the Rust vector backing. The outer `c_to_py` cleanup releases the `FfiSlice` descriptor only.

**Evidence:** `_slice_to_vector` casts `raw.contents.ptr` to `POINTER(c_char_p)`, obtains its elements, and returns `list(map(lambda v: v.decode(), array))`. The outer `c_to_py` finally calls `slice_free(ffi_slice)`, whose Rust implementation explicitly does not free referenced data. The producer `vec_string_to_raw` uses `CString::into_raw` for strings and `util::into_raw(vec)` for its pointer array. A conversion exception does not repair these missing deallocations.

**Limitations:** Static ownership trace only; no compiled Python OpenDP test or native profiler was run. The `char **` array layout is correct for vectors, unlike the known scalar-string mismatch.

**Related:** [Cross-language investigation](../../../../investigations/ffi-string-vector-backing-ownership.md); [draft PR #3179](https://github.com/opendp/opendp/pull/3179).

### Composite output backing ownership

**Conclusion:** Python's tuple/map decoders copy values from Rust-owned composite scratch views without releasing their backing allocations. In particular, `_slice_to_hashmap` deliberately treats its nested key/value `AnyObject` pointers as borrowed, so their Rust-created wrappers remain unclaimed and unfreed on the legacy producer path.

**Evidence:** `_slice_to_tuple` interprets `raw.contents.ptr` as `POINTER(c_void_p)`, copies the addresses to a Python list, and reads the referenced scalar fields. `_slice_to_hashmap` casts the pointer array to `POINTER(POINTER(AnyObject))` and reads each via `c_to_py`. The `ctypes.POINTER(AnyObject)` values do not have the `AnyObjectPtr` destructor. The Rust producer allocated the tuple pointer array with `util::into_raw([..])`, and the map child wrappers and pointer vector with `util::into_raw`. The `c_to_py` `finally` block frees only the enclosing `FfiSlice` descriptor, whose destructor explicitly does not free the pointee.

**Negative findings and limits:** The Python code avoids prematurely freeing pointers that may originate from a Python-owned input slice; ownership cannot safely be inferred solely from the inner `ctypes` type. The defect is instead the legacy Rust output producer's absence of an owner for its detached scratch allocations. No dynamic OpenDP test or native allocation measurement was executed, and specialized tuple payloads were not audited.

**Related:** [Cross-language investigation](../../../../investigations/ffi-composite-output-ownership.md); [pending draft PR #3179](https://github.com/opendp/opendp/pull/3179).

## Next checks

Run a native conversion loop with allocation instrumentation, then verify that the eventual merged ownership implementation reclaims both the view header and pointer-array storage, including conversion errors.

- Follow the [Cross-language scalar string layout investigation](../../../../investigations/ffi-scalar-string-layout.md) and run scalar `String` outputs through a compiled, sanitizer-enabled binding before marking this pointer-layout concern resolved.

- Validate that the eventual merged `FfiSliceOwner` reclaims `Vec<String>` C strings and the pointer array after successful and exceptional conversions; add native-allocation regression measurements.

- Verify composite scratch-buffer cleanup under a native allocation checker after PR #3179 is merged; separately test normal conversions and failures.
