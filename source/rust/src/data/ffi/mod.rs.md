---
schema_version: 1
source: rust/src/data/ffi/mod.rs
updated: 2026-11-22
---

# `rust/src/data/ffi/mod.rs`

## Scope and assumptions

- **Audit scope:** `opendp_data__ffislice_of_anyobjectptrs` and the cleanup contract of `opendp_data__slice_free`, limited to temporary vector-pointer conversion.
- **Additional audit scope:** Descriptor allocation by `opendp_data__object_as_slice` and the corresponding `slice_free` cleanup contract. This property is separate from temporary pointer-array ownership and does not cover backing-buffer lifetime.
- **Invariant:** A temporary vector and its FFI slice view must have a reachable owner or corresponding deallocation path; converting borrowed elements must not abandon Rust-owned allocations.
- **Assumptions:** The caller supplies a valid `FfiSlice` of contiguous `AnyObject` values; pointer validity and element-type correctness are outside scope.
- **Source:** [Rust FFI converter at reviewed commit](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/mod.rs), [FfiSlice layout](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/ffi/mod.rs).

- **Additional audit scope:** The pointer representation of a scalar `String` returned by `opendp_data__object_as_slice::string_to_raw`, compared with R and Python readers. Its separate allocation leak is not the property assessed here.

- **Additional audit scope:** Legacy `object_as_slice` handling of `Vec<String>`, including ownership of each exported C string and the pointer-array backing. It is distinct from the separately audited scalar-string pointer shape and the outer descriptor.

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `opendp_data__ffislice_of_anyobjectptrs` | memory/temporary-slice-ownership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file investigation](../../../../../investigations/ffi-vector-slice-lifetime.md) |
| `opendp_data__slice_free` | memory/temporary-slice-ownership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cleanup contract](../../../../../investigations/ffi-vector-slice-lifetime.md) |
| `opendp_data__object_as_slice` | memory/ownership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Descriptor analysis](#opendp_data__object_as_slice-and-opendp_data__slice_free--memoryownership): successful result transfers an owned descriptor to the caller |
| `opendp_data__slice_free` | memory/ownership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Descriptor analysis](#opendp_data__object_as_slice-and-opendp_data__slice_free--memoryownership): frees the outer descriptor only |

| `opendp_data__object_as_slice::string_to_raw` | correctness/ffi-scalar-string-layout | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Scalar String layout](#scalar-string-pointer-layout): returns a direct `char *` where both binding readers expect `char **` |

| `opendp_data__object_as_slice::vec_string_to_raw` | memory/string-vector-backing-ownership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Backing allocations](#vecstring-backing-ownership): exported CString buffers and pointer array lack a release path |

## Analysis

### Native helper and cleanup — `memory/temporary-slice-ownership`

**Conclusion:** The helper calls `vec_any_ptrs.leak()` before returning a new `FfiSlice`, with no reclamation mechanism for the backing vector. `slice_free` only drops the `FfiSlice` header, not its referenced pointer-array allocation. The Python caller also omits cleanup of the helper's new header.

**Evidence:** The helper constructs `Vec<*const AnyObject>` with `.collect()`, converts it to leaked storage with `Vec::leak`, and returns a `FfiSlice::new` holding the resulting raw buffer pointer. `slice_free` explicitly documents that it does not free referenced allocations. The [investigation](../../../../../investigations/ffi-vector-slice-lifetime.md) traces the Python consumer.

**Limitations:** No native memory profiler was available; this conclusion is based on direct source inspection. Rust's object ownership for other FFI output types and the proposed replacement owner's implementation have not been fully audited.

**Related:** [Upstream draft PR #3179](https://github.com/opendp/opendp/pull/3179) removes the legacy helper in its pending replacement.


### `opendp_data__object_as_slice` and `opendp_data__slice_free` — `memory/ownership`

**Conclusion:** The Rust FFI exposes an owned outer descriptor and a matching destructor. That ownership contract is not satisfied by the examined R consumer on `main`; the mismatch is recorded in the [R source report](../../../../../source/R/opendp/src/convert.c.md).

**Evidence:** `opendp_data__object_as_slice` builds a `Fallible<FfiSlice>` (from a borrowed primitive/vector or, for some variants, newly allocated backing data) and returns `.into()`. The generic conversion from `Fallible<TI>` to `FfiResult<*mut TO>` calls `util::into_raw(TO::from(v))`, transferring the descriptor into a raw owned pointer. `opendp_data__slice_free` calls `util::into_owned(this)` to reclaim the descriptor. Its documented purpose is cleanup after `object_as_slice` and its comment states it does *not* free referenced storage. Python's `c_to_py` uses a `finally: slice_free(ffi_slice)` block, independently corroborating the expected caller cleanup.

**Limitations:** Only the descriptor contract was assessed. Allocation paths such as `string_to_raw`, `vec_string_to_raw`, `tuple2_to_raw`, and `ffislice_of_anyobjectptrs` may create separate backing allocations that are not handled by `slice_free`; no conclusion about their ownership or complete cleanup is made. No Rust or R tests were executed for this audit.

**Related:** [Cross-language ownership investigation](../../../../../investigations/r-ffi-slice-descriptor-ownership.md), [upstream PR #3176](https://github.com/opendp/opendp/pull/3176).

### Scalar String pointer layout — `correctness/ffi-scalar-string-layout`

**Conclusion:** The scalar `String` branch of `object_as_slice` publishes an `FfiSlice.ptr` that is a C-string byte pointer (`char *`), not the address of a C-string pointer (`char **`). Both bindings read this as a pointer array and can dereference a nonsensical address. This is a distinct issue from the leaked C-string allocation documented in the Rust `FIXME` and from outer `FfiSlice` ownership.

**Evidence:** `string_to_raw` passes `util::into_c_char_p(string.clone())` directly to `FfiSlice::new`. In contrast, `vec_string_to_raw` passes `vec.as_ptr()`, where `vec` is a `Vec<*mut c_char>`. The latter has the expected `char **` layout. The R scalar path uses `((char **)input)[i]` and Python's `_slice_to_string` casts to `POINTER(c_char_p)` and reads `.contents.value`. For a valid one-byte string `"A"`, interpreting the first bytes of the string as a machine pointer yields an invalid pointer value rather than the address of the string.

**Limitations:** No compiled OpenDP runtime or sanitizers were run. The static type/representation mismatch is direct; platform-specific failure mode (crash, invalid memory access, or other undefined behavior) was not measured. Only scalar `String` output was assessed; the `Vec<String>` pointer-array shape matches the readers and is not asserted defective on this property.

**Related:** [Cross-language investigation](../../../../../investigations/ffi-scalar-string-layout.md). [Upstream draft PR #3179](https://github.com/opendp/opendp/pull/3179) constructs the scalar string pointer array under `FfiSliceOwner`, but is open and unmerged at review time.

### Vec<String> backing ownership

**Conclusion:** The legacy `Vec<String>` return path loses ownership of the C-string payloads and the pointer-array backing. A successful conversion leaks at least one C-string allocation per string and the exported vector backing allocation. An error after one or more successful string conversions leaks those already allocated C strings before an `FfiSlice` can even be produced. This is a native-memory resource-exhaustion concern rather than a differential-privacy soundness result.

**Evidence:** `vec_string_to_raw` maps each cloned `String` through `util::into_c_char_p`, which calls `CString::into_raw` ([pinned definition](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/ffi/util.rs#L476-L486)). Each pointer is stored in a `Vec<*mut c_char>`. The vector's buffer becomes `FfiSlice.ptr`, and the `Vec` value itself is passed to `util::into_raw(vec)`, which calls `Box::into_raw(Box::new(...))` ([pinned definition](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/ffi/util.rs#L458-L465)). Neither the boxed vector nor its individual C strings has a matching consumer-side destructor. `opendp_data__slice_free` calls `util::into_owned` on only the *outer* `FfiSlice`, and explicitly documents that it does not free referenced buffers. Error-path `collect::<Fallible<Vec<*mut c_char>>>()?` drops the raw-pointer vector on failure but not the previously detached `CString` allocations.

**Limitations:** Static ownership proof at the pinned upstream SHA only; no R/Python runtime leak measurements, sanitizer runs, or profiler counts. The pointer-array *layout* for `Vec<String>` matches the binding readers (unlike the separately audited plain scalar `String`). This review does not audit `HashMap`, tuple, or Polars backing allocations.

**Related:** [Cross-language investigation](../../../../../investigations/ffi-string-vector-backing-ownership.md); [draft PR #3179](https://github.com/opendp/opendp/pull/3179) introduces `FfiSliceOwner` with owned strings and a kept-alive pointer vector, but remains unmerged.

## Next checks

- Check the eventual merged code and native regression tests for complete release of pointer-array storage under both success and error conditions.
- Independently audit the backing-buffer lifetime of the `object_as_slice` descriptor, and verify cleanup through the R consumer after PR #3176 merges.

- Follow the [Cross-language scalar string layout investigation](../../../../../investigations/ffi-scalar-string-layout.md) and run scalar `String` outputs through a compiled, sanitizer-enabled binding before marking this pointer-layout concern resolved.

- Validate that the eventual merged `FfiSliceOwner` reclaims `Vec<String>` C strings and the pointer array after successful and exceptional conversions; add native-allocation regression measurements.
