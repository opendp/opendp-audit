---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# User-defined measurement FFI: callback lifetime and proof obligation

## Invariant and threat model

The non-deprecated `make_user_measurement` is intentionally marked `honest-but-curious`: users provide both a release function and an asserted privacy map. The audit asks whether the FFI constructor preserves the supplied callbacks and ordinary errors as expected, and whether its documentation correctly communicates that OpenDP **cannot derive or certify** a privacy guarantee for arbitrary user code. It does not attempt to prove malicious or incorrect callbacks private.

## Cross-file ownership and error chain

- [Constructor source audit](../source/rust/src/measurements/make_user_measurement/mod.rs.md) and [pinned exported entrypoint](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_user_measurement/mod.rs).
- [`CallbackFn` and `wrap_func`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/ffi/any.rs): cloned callback owns an `ExtrinsicObject` and calls a fallible wrapper.
- [`ExtrinsicObject`/`into_owned`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/ffi/util.rs): clone and drop delegate to host reference counting; null return pointers are rejected as FFI errors.
- [Python `_wrap_py_func`/`_invoke_py_callback`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/_convert.py): host userdata stores the callable and declared output type; exceptions are packed as FFI errors.
- [Python `_set_ref_count` registration](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/_lib.py): reference-count hooks are registered when the OpenDP shared library loads.

## Source trace

`opendp_measurements__make_user_measurement` checks the required FFI object pointers with `try_as_ref!`, clones both callback structs and constructs a type-erased measurement containing fallible function and privacy map. The `CallbackFn` structure includes a function pointer and an `ExtrinsicObject` userdata handle. Cloning its userdata increments a host-maintained reference count, and dropping it decrements that count. The callback closure therefore retains a handle to the Python callable after the temporary input pointer's lifetime ends, conditional on host registration and correct reference-count semantics.

For successful Python callbacks, `_invoke_py_callback` converts the incoming `AnyObject` to Python, calls the user's function, converts the result back to an owned `AnyObject` and packages it with `ffiresult_ok`. Ordinary Python exceptions are caught and returned with `ffiresult_err`. The Rust wrapper consumes the FFI result via `into_owned`; null `FfiResult` pointers become recoverable errors. No callback is invoked at measurement construction by the visible entrypoint. Both the measurement function and its privacy map are wrapped in the same way.

### Explicit assumptions and residual risks

- The user-supplied privacy map is **not validated** against the user's release distribution. The feature requires an external proof of the map and non-side-effectful callback behavior; arbitrary false user claims cannot be treated as an OpenDP privacy bug.
- `AnyDomain` currently accepts every `AnyMetric` at type-erased metric-space validation. This emphasizes the proof obligation rather than establishing compatibility of arbitrary domain/metric pairs.
- `ExtrinsicObject::Clone`/`Drop` call the host refcount hook through `OnceLock.get().unwrap()`. The supported Python loader initializes this hook. A foreign C host that does not initialize it has a potential panic/ABI failure; no concrete supported failing host or end-to-end trigger was established.
- The C callback pointer ABI depends on correct allocation and ownership by the foreign host. Unwind across the C callback boundary, malformed successful object pointers, shutdown races and concurrency are not covered by the source trace.
- `TO` is used for host-side Python result conversion but is not type-checked in the exported Rust type-erased constructor itself. Actual downstream type requirements may be enforced when data is consumed.

## Findings

**No confirmed defect** in the constructor's documented trusted-user privacy boundary, normal callback capture, and ordinary error forwarding under the stated host assumptions. **Partial** remains appropriate for ABI lifetime and error robustness because no compiled OpenDP library, interpreter callback, reference-count profiler or sanitizer was executed.

This review does **not** establish that an arbitrary user-defined measurement is differentially private or memory-safe under a malicious foreign caller. The documented honest-but-curious obligation is essential, not an implementation theorem.

## Next checks

- Native integration with Python callback lifetime and GC: create the measurement, release local closures, invoke function/privacy map, destroy the measurement, and check the callback userdata's finalizer runs once.
- Verify errors propagate for user callback exceptions and compare behavior with missing callback/refcount setup in a controlled process (not in-process if it could abort).
- Check typed return-object mismatches with actual FFI/Python/R bindings, under a separate reproducible contract if a concrete failure is found.
