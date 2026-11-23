---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Audited
---

# Legacy FFI tuple and HashMap output scratch ownership

## Invariant and threat model

Every native allocation used only to expose a composite Rust output to R or Python must have a reachable owner and be released after the host language finishes copying the values, including on error paths. Tuple pointer arrays borrow their source tuple fields, while temporary HashMap key/value `AnyObject` values own cloned vectors. Those distinct resources must not be conflated with the enclosing `FfiSlice` descriptor. An unreleased scratch allocation can cause unbounded native-memory growth across repeated conversions; this review does not establish a differential-privacy soundness failure.

## Affected symbols and source audits

- [Rust tuple and HashMap conversion](../source/rust/src/data/ffi/mod.rs.md): `tuple2_to_raw`, `option_tuple2_to_raw`, `tuple3_l0Pinf_distance_to_raw`, and `hashmap_to_raw`; [pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/mod.rs#L505-L611).
- [R composite consumers](../source/R/opendp/src/convert.c.md): `slice_to_tuple` and `slice_to_hashmap`; [pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/R/opendp/src/convert.c#L563-L639).
- [Python composite consumers](../source/python/src/opendp/_convert.py.md): `_slice_to_tuple` and `_slice_to_hashmap`; [pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/_convert.py#L720-L821).
- [Rust raw allocation helper](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/ffi/util.rs#L458-L466) and [descriptor-only destructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/mod.rs#L936-L950) establish the ownership contract.

## Reasoning and evidence

1. Rust's ordinary tuple return helpers call `util::into_raw([field_pointer, ...])`, which boxes the two- or three-element pointer array and returns the raw pointer used as `FfiSlice.ptr`. No owner is stored. The `None` branch of `option_tuple2_to_raw` does not allocate an array and is not affected by this subfinding.
2. Rust's `hashmap_to_raw` clones the map's keys and values into new vector-bearing `AnyObject` wrappers, calls `util::into_raw` on each, then calls `util::into_raw(map)` on the vector containing the two object pointers. Neither the two children nor their pointer vector has a corresponding output cleanup path.
3. Rust's `opendp_data__slice_free` explicitly releases only the enclosing `FfiSlice`, not its `ptr` storage. Python's outer `c_to_py` invokes that destructor; R's original `anyobjectptr_to_sexp` does not even free that outer descriptor. Neither behavior reclaims the composite scratch allocations.
4. R's `slice_to_tuple` copies fields into an R list and `slice_to_hashmap` copies children into an R hash table. Python's `_slice_to_tuple` reads scalar values, while `_slice_to_hashmap` reads the child pointers as borrowed `ctypes.POINTER(AnyObject)` and reconstructs a dictionary. Copying values is not reclamation of Rust's raw boxed allocations.
5. This is distinct from [string-vector backing ownership](ffi-string-vector-backing-ownership.md), [temporary AnyObject pointer-array ownership](ffi-vector-slice-lifetime.md), and [the R outer descriptor leak](r-ffi-slice-descriptor-ownership.md). The maps' key/value vectors are genuinely owned scratch objects, whereas tuple element references are borrowed from the source `AnyObject`.

[Draft upstream PR #3179](https://github.com/opendp/opendp/pull/3179) introduces a typed `FfiSliceOwner` that stores tuple pointer vectors using `owner.pointers` and HashMap key/value `AnyObject` wrappers using `owner.keep`. The PR remains open and unmerged; the current upstream `main` still uses the legacy conversion functions.

**Executed:** Commit-pinned Rust, R, and Python source inspection; comparison with PR #3179's proposed owner implementation. No OpenDP native tests, allocation profiling, sanitizer runs, or simulated crash reproduction were performed.

## Findings

**Confirmed by static source-level allocation tracing:** The legacy tuple and HashMap return branches leave their scratch backing arrays without destructors. The HashMap branch additionally leaves two cloned key/value `AnyObject` wrappers allocated. The practical rate of memory growth and runtime failure behavior have not been measured. **Upstream disposition: pending draft PR #3179.** No duplicate candidate issue was opened.

## Unresolved questions

- Verify post-merge composite output conversions under Valgrind, ASan, or a native allocation tracker, including repeated tuple and HashMap conversions and exceptional host-language exits.
- Verify owner destruction reclaims the three distinct HashMap scratch resources and the tuple pointer arrays without freeing borrowed tuple fields.
- Independently audit special tuple variants, opaque escaping wrappers, and legacy input-side HashMap allocations; this review covers only the ordinary output scratch paths.
