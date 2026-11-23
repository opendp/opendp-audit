---
schema_version: 1
source: rust/src/data/ffi/mod.rs
updated: 2026-11-22
---

# `rust/src/data/ffi/mod.rs`

## Scope and assumptions

- **Audit scope:** `opendp_data__ffislice_of_anyobjectptrs` and the cleanup contract of `opendp_data__slice_free`, limited to temporary vector-pointer conversion.
- **Invariant:** A temporary vector and its FFI slice view must have a reachable owner or corresponding deallocation path; converting borrowed elements must not abandon Rust-owned allocations.
- **Assumptions:** The caller supplies a valid `FfiSlice` of contiguous `AnyObject` values; pointer validity and element-type correctness are outside scope.
- **Source:** [Rust FFI converter at reviewed commit](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/mod.rs), [FfiSlice layout](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/ffi/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `opendp_data__ffislice_of_anyobjectptrs` | memory/temporary-slice-ownership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file investigation](../../../../../investigations/ffi-vector-slice-lifetime.md) |
| `opendp_data__slice_free` | memory/temporary-slice-ownership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cleanup contract](../../../../../investigations/ffi-vector-slice-lifetime.md) |

## Analysis

### Native helper and cleanup — `memory/temporary-slice-ownership`

**Conclusion:** The helper calls `vec_any_ptrs.leak()` before returning a new `FfiSlice`, with no reclamation mechanism for the backing vector. `slice_free` only drops the `FfiSlice` header, not its referenced pointer-array allocation. The Python caller also omits cleanup of the helper's new header.

**Evidence:** The helper constructs `Vec<*const AnyObject>` with `.collect()`, converts it to leaked storage with `Vec::leak`, and returns a `FfiSlice::new` holding the resulting raw buffer pointer. `slice_free` explicitly documents that it does not free referenced allocations. The [investigation](../../../../../investigations/ffi-vector-slice-lifetime.md) traces the Python consumer.

**Limitations:** No native memory profiler was available; this conclusion is based on direct source inspection. Rust's object ownership for other FFI output types and the proposed replacement owner's implementation have not been fully audited.

**Related:** [Upstream draft PR #3179](https://github.com/opendp/opendp/pull/3179) removes the legacy helper in its pending replacement.

## Next checks

Check the eventual merged code and native regression tests for complete release of pointer-array storage under both success and error conditions.
