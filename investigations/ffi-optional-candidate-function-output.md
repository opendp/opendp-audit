---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Audited
---

# Optional private-candidate output and Function handle ownership

## Invariants and scope

A successful `Option<(f64, AnyObject)>` candidate release should decode to its score and candidate in both R and Python; `None` should remain an empty result. Scratch pointer arrays must be reclaimed without freeing the borrowed tuple fields. An independently cloned `Function<I,O>` handle must outlive the FFI descriptor and be freed by the receiving wrapper exactly once. This is a bounded output-conversion correctness and memory-ownership review, not a privacy-accounting proof.

## Affected source audits

- [Rust source audit](../source/rust/src/data/ffi/mod.rs.md): [`option_to_raw` and `function_to_raw`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/mod.rs); [`util::into_raw`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/ffi/util.rs); [`slice_free`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/mod.rs#L936-L950).
- [R source audit](../source/R/opendp/src/convert.c.md): [`slice_to_sexp`, `slice_to_tuple` and `voidptr_to_sexp`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/R/opendp/src/convert.c).
- [Python source audit](../source/python/src/opendp/_convert.py.md): [`_slice_to_option`, `_slice_to_tuple` and `_slice_to_function`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/_convert.py), with native [`Function` finalizer](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/mod.py).
- [Public Rust/FFI private-candidate constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/select_private_candidate/ffi.rs) and [generic implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/select_private_candidate/mod.rs).

## Source trace and findings

### Specialized optional private-candidate output

The generic Rust private-candidate combinator returns `Option<(f64, TO)>`. Its FFI wrapper erases the candidate to `AnyObject`, yielding `Option<(f64, AnyObject)>` and wrapping the release as an `AnyObject`. For `Some((score, candidate))`, Rust's specialized `option_to_raw` returns a heap-allocated two-pointer array through `util::into_raw`. Those pointers borrow the source tuple fields; only the array is separately allocated. `opendp_data__slice_free` explicitly drops the outer `FfiSlice` descriptor but not the scratch array. The `None` branch returns a null pointer and length zero and does not allocate such an array.

Python recognizes `[f64, AnyObject]` inside `_slice_to_tuple`, reads the score, and passes a borrowed `POINTER(AnyObject)` through `c_to_py`, avoiding ownership theft from the source tuple. The returned values can be copied, but neither Python's consumer nor the legacy Rust descriptor destructor releases the separate pointer array. This is a source-supported memory-leak finding with no measured growth.

R has a distinct *decoding* defect. It unwraps `Option` to `Tuple` in `slice_to_sexp` and forwards each tuple member from `slice_to_tuple` into `voidptr_to_sexp`. That function lacks an `AnyObject` case, so a nonempty candidate result reaches `error_unknown_type` instead of returning its candidate. `None` is handled as `R_NilValue`. The affected FFI constructor is present, but no compiled R reproduction or exact error-text check was performed.

### Function output ownership: limited negative finding

Rust's `function_to_raw` clones `Function<I,O>`, erases it to an owned `AnyFunction`, and returns its heap pointer directly as the `FfiSlice.ptr` value. Python `_slice_to_function` constructs a `Function` pointer to that address; its [native finalizer](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/mod.py) calls `_function_free`. The outer descriptor is a separate allocation and is not supposed to own the escaped function.

A standalone Python `ctypes` check with a zero-field opaque structure returned the same address after `POINTER(Opaque).contents` and `ctypes.pointer` wrapping. This supports the pointer-layout analysis but is not an OpenDP runtime test or proof that finalization occurs exactly once. No additional Rust-to-Python missing-ownership path was found within this scope.

R's generic `slice_to_sexp` has no `Function` case. Public reachability of a generic Function *inside* an `AnyObject` returned to R was **not established**. The generated direct `AnyFunction *` conversion uses a separate [`anyfunctionptr_to_sexp` wrapper](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/R/opendp/src/convert_elements.c), with a registered finalizer; this audit does not assert that path is defective.

### Existing upstream changes and validation limits

[Draft PR #3179](https://github.com/opendp/opendp/pull/3179) (reviewed at `bccc2aeb6e38ac5b2ad7894eae8fa441080d8119`) places optional tuple pointer arrays under a typed `FfiSliceOwner` and provides direct `opendp_data__clone_function` output for Python. The PR remains unmerged. Its [R tuple decoder](https://github.com/opendp/opendp/blob/bccc2aeb6e38ac5b2ad7894eae8fa441080d8119/R/opendp/src/convert.c) still delegates each member to `voidptr_to_sexp` without `AnyObject` support.

**Executed:** Pinned Rust/R/Python source review, draft PR comparison, one standalone opaque-pointer `ctypes` address check, and a compiler-backed C-shim dispatch witness. **Not executed:** genuine compiled OpenDP binding tests, native leak checking, sanitizer runs, or destructor-count instrumentation. The R decoder defect is tracked in [consolidated audit issue #7](https://github.com/opendp/opendp-audit/issues/7) (original [#8](https://github.com/opendp/opendp-audit/issues/8) closed as duplicate); no upstream issue or PR was created by this audit.

### Executable C-shim dispatch witness

The [pinned C fixture](../tools/tests/r_ffi_nested_tuple_dispatch.c) embeds the unmodified bodies of `voidptr_to_sexp`, `slice_to_tuple`, and `slice_to_sexp` from the reviewed upstream commit, compiled against a minimal **test-only R API stub** by the [unittest driver](../tools/tests/test_r_ffi_nested_tuple_dispatch.py). It executes four inputs: a successful `(f64, f64)` control; `(PrivacyProfile, f64)` triggering `voidptr_to_sexp unknown type: PrivacyProfile`; nonempty `Option<(f64, AnyObject)>` triggering `voidptr_to_sexp unknown type: AnyObject`; and an empty Option returning the stub `R_NilValue`.

The C-shim unit-test step and repository validation passed in [GitHub Actions run 45099985874](https://github.com/opendp/opendp-audit/actions/runs/45099985874). **This is not an R runtime or OpenDP integration reproduction.** It isolates C dispatch with stand-in R types; the production type parsing, FFI constructor, memory lifetime, R's nonlocal exception handling, and user-facing error text remain unverified by this executable witness.

## Findings

- **R correctness/usability:** `Option<(f64, AnyObject)>` with `Some` cannot decode its nested `AnyObject` through R's tuple converter. The source-confirmed mismatch is tracked in [consolidated audit candidate #7](https://github.com/opendp/opendp-audit/issues/7) ([#8](https://github.com/opendp/opendp-audit/issues/8) closed as duplicate) and not addressed by the inspected PR #3179.
- **Native resource ownership:** The legacy `Some` branch loses its boxed pointer array; pending PR #3179 supplies a scoped owner.
- **Function handle:** No additional missing-free defect was identified for successful Rust-to-Python Function output in this bounded review. R generic Function output remains partially assessed because a reachable producing API was not identified.

## Unresolved questions

- Compile and run a successful R private-candidate selection and assert its score/candidate, plus the `None` case.
- Profile repeated nonempty output conversions before and after the proposed `FfiSliceOwner` change.
- Exercise an independently returned Function through Python after the source AnyObject is destroyed, checking for exactly one native destruction and no lifetime violation. Establish whether a generic R Function output is publicly reachable before treating that R dispatch gap as a defect.
