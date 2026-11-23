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

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `_slice_to_vector` | memory/temporary-slice-ownership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file investigation](../../../../investigations/ffi-vector-slice-lifetime.md) |

| `_slice_to_string` | correctness/ffi-scalar-string-layout | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Scalar String layout](#scalar-string-pointer-layout): dereferences `FfiSlice.ptr` as `char **` although the scalar Rust producer returns `char *` |

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

## Next checks

Run a native conversion loop with allocation instrumentation, then verify that the eventual merged ownership implementation reclaims both the view header and pointer-array storage, including conversion errors.

- Follow the [Cross-language scalar string layout investigation](../../../../investigations/ffi-scalar-string-layout.md) and run scalar `String` outputs through a compiled, sanitizer-enabled binding before marking this pointer-layout concern resolved.
