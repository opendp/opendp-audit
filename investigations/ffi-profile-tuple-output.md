---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Audited
---

# Specialized PrivacyProfile tuple output: R dispatch and Python scratch ownership

## Invariant and threat model

An output typed `(PrivacyProfile, f64)` should roundtrip from the Rust privacy map through R and Python without unsupported-type errors. Any raw allocations created solely to bridge the FFI conversion should be reclaimed when no longer needed; only an independent escaped `PrivacyProfile` clone may remain owned by the host. The observed failures are a correctness/usability gap for R and unreclaimed native scratch memory for Python, not demonstrated differential-privacy soundness violations.

## Affected symbols and source audits

- [Rust `tuple_curve_f64_to_raw` and dispatch](../source/rust/src/data/ffi/mod.rs.md): [pinned source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/mod.rs). This is the `(PrivacyProfile, f64)` special case, not the ordinary tuple serializer.
- [R `anyobjectptr_to_sexp`, `slice_to_tuple`, `voidptr_to_sexp`](../source/R/opendp/src/convert.c.md): [pinned source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/R/opendp/src/convert.c). The outer type `Tuple` bypasses the top-level opaque `PrivacyProfile` branch.
- [Python `_slice_to_tuple` and `c_to_py`](../source/python/src/opendp/_convert.py.md): [pinned source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/_convert.py), [`AnyObjectPtr` destructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/_lib.py), [`PrivacyProfile` wrapper](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/mod.py).
- [`ConcentratedMeasure` for `Approximate<ZeroConcentratedDivergence>`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/measure_cast/zCDP_to_approxDP/mod.rs) constructs this specialized distance. [FFI `make_approximate`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/measure_cast/approximate/ffi.rs) and [FFI `make_zCDP_to_approxDP`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/measure_cast/zCDP_to_approxDP/ffi.rs) expose a reachable production path.

## Reasoning and evidence

1. `make_approximate` casts a `ZeroConcentratedDivergence` measurement to `Approximate<ZeroConcentratedDivergence>`. The `make_zCDP_to_approxDP` `ConcentratedMeasure` implementation then maps its distance to the two-member tuple `(PrivacyProfile, f64)`. This is a supported Rust/FFI output type.
2. When converting that `AnyObject`, `object_as_slice` invokes `tuple_curve_f64_to_raw`, which creates a heap-owned profile clone with `AnyObject::new_raw(curve.clone())`, a heap-owned scalar with `util::into_raw(*delta)`, and a heap-owned two-pointer array with `util::into_raw([..])`. `slice_free` releases only the outer `FfiSlice` descriptor.
3. R's output `anyobjectptr_to_sexp` detects `Tuple` and calls `slice_to_tuple`. For its first `PrivacyProfile` element, `slice_to_tuple` invokes `voidptr_to_sexp`. That function has no `PrivacyProfile` case and unconditionally reaches `error_unknown_type` for this input. The R `PrivacyProfile` wrapper function is available for top-level opaque outputs, but this member is not routed to it.
4. Python's specialized `_slice_to_tuple` receives the profile clone as an owning `AnyObjectPtr`. The returned `PrivacyProfile` keeps that pointer alive and `AnyObjectPtr.__del__` eventually frees it. The two *other* allocations, the boxed `f64` and pointer array, are only read and never reclaimed. Their leak is not repaired by `slice_free`.
5. [Draft PR #3179](https://github.com/opendp/opendp/pull/3179) changes the Rust special encoder to retain the profile clone in a scoped `FfiSliceOwner` and borrow the `f64` from the source. Its revised Python decoder calls `c_to_py` on a borrowed profile pointer, causing an independent clone to escape. This addresses the scratch ownership if properly integrated. However, the [PR's R converter](https://github.com/opendp/opendp/blob/bccc2aeb6e38ac5b2ad7894eae8fa441080d8119/R/opendp/src/convert.c) still calls `voidptr_to_sexp` on all tuple members and does not implement `PrivacyProfile` decoding. The R functional finding therefore remains unaddressed by the examined draft.

**Executed:** GitHub source tracing, type dispatch and allocation/destructor review, inspection of the unmerged PR implementation, and a compiler-backed C-shim dispatch witness. No genuine OpenDP R or Python runtime tests, Valgrind, AddressSanitizer, or dynamic privacy-map invocation were run.

### Executable C-shim dispatch witness

The [pinned C fixture](../tools/tests/r_ffi_nested_tuple_dispatch.c) embeds the unmodified bodies of `voidptr_to_sexp`, `slice_to_tuple`, and `slice_to_sexp` from the reviewed upstream commit, compiled against a minimal **test-only R API stub** by the [unittest driver](../tools/tests/test_r_ffi_nested_tuple_dispatch.py). It executes four inputs: a successful `(f64, f64)` control; `(PrivacyProfile, f64)` triggering `voidptr_to_sexp unknown type: PrivacyProfile`; nonempty `Option<(f64, AnyObject)>` triggering `voidptr_to_sexp unknown type: AnyObject`; and an empty Option returning the stub `R_NilValue`.

The C-shim unit-test step and repository validation passed in [GitHub Actions run 45099985874](https://github.com/opendp/opendp-audit/actions/runs/45099985874). **This is not an R runtime or OpenDP integration reproduction.** It isolates C dispatch with stand-in R types; the production type parsing, FFI constructor, memory lifetime, R's nonlocal exception handling, and user-facing error text remain unverified by this executable witness.

## Findings

- **R correctness finding — source-confirmed:** An output of `(PrivacyProfile, f64)` reaches an unsupported `PrivacyProfile` member type in `voidptr_to_sexp`. The user-facing route is `make_zCDP_to_approxDP(make_approximate(make_gaussian(...)))` followed by its `d_in` privacy map. Runtime reproduction remains outstanding. **Upstream disposition: unreported upstream; tracked in [audit candidate #7](https://github.com/opendp/opendp-audit/issues/7); draft PR #3179 does not change the decoder.**
- **Python native-resource finding — confirmed by allocation tracing:** The `AnyObject` profile clone is adopted and eventually freed by the Python wrapper, but the separately boxed delta and pointer array are not. **Upstream disposition: pending draft PR #3179.**

The R nested-profile decoding finding is tracked in [audit issue #7](https://github.com/opendp/opendp-audit/issues/7). No upstream issue or PR was created by this audit.

## Unresolved questions

- Execute an R regression of the approximate zCDP-to-approxDP conversion, asserting its privacy map returns an R privacy-profile wrapper and the original delta, rather than an unknown-type error.
- Execute repeated Python tuple conversions and destruction under Valgrind/ASan or equivalent, confirming no residual boxed scalar or pointer-array allocations after the upstream ownership redesign.
- If PR #3179 merges as currently written, update the coverage disposition for Python memory ownership separately from R tuple decoding and record the merged commit SHA. The specialized `(f64, ExtrinsicObject)` branch and function-handle output are out of scope.
