---
schema_version: 1
source: rust/src/measurements/make_user_measurement/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/make_user_measurement/mod.rs`

## Scope and assumptions

- **Scope:** The non-deprecated `honest-but-curious`-gated user-measurement constructor, its Rust FFI entrypoint `opendp_measurements__make_user_measurement`, callback ownership and error forwarding, and the documented obligation to supply a valid privacy map. Review the `CallbackFn` wrapper, refcount/destructor hooks and Python callback trampoline as supporting code.
- **Invariants:** Valid callback userdata remains live for every invocation while the returned measurement exists; callback failures propagate as errors rather than silently becoming private releases; the constructor does **not** purport to prove a user's self-supplied privacy map.
- **Assumptions:** The host registers the refcount callback before cloning/dropping extrinsic userdata, the callback uses the published FFI allocation/return convention, no callback unwinds across the C ABI, and user-provided function/map obeys the `honest-but-curious` proof contract. General malicious/corrupt foreign pointers are outside the safe-Rust guarantees.
- **Pinned code:** [User measurement constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_user_measurement/mod.rs), [`CallbackFn` and `wrap_func`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/ffi/any.rs), [`ExtrinsicObject` and `into_owned`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/ffi/util.rs), [Python dispatch](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/_convert.py) and [reference hook initialization](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/_lib.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::make_user_measurement::opendp_measurements__make_user_measurement` | privacy/honest-but-curious-contract | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Trust-boundary investigation](../../../../../investigations/user-measurement-ffi-callback-contract.md) |
| `measurements::make_user_measurement::opendp_measurements__make_user_measurement` | memory/callback-userdata-lifetime | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Reference-count ownership trace](#callback-ownership-and-lifetime) |
| `measurements::make_user_measurement::opendp_measurements__make_user_measurement` | correctness/callback-error-propagation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Error trace](#ffi-callback-result-and-errors) |

## Analysis

### Honest-but-curious contract

The bootstrap annotation explicitly enables the constructor under the `contrib` and `honest-but-curious` feature flags. Its documentation conditions measurement validity on the caller's proof that for all neighboring domain values, the supplied function's release distributions are bounded by `privacy_map`, and that both function and map obey the required purity/side-effect restrictions. No generic library algorithm can establish that obligation for arbitrary user callbacks.

The exported C entrypoint clones the type-erased input domain, metric and measure, then uses `Measurement::new` with `Function::new_fallible(wrap_func(...))` and `PrivacyMap::new_fallible(wrap_func(...))`. The type-erased `(AnyDomain, AnyMetric)::check_space` currently accepts every pairing; this is an **explicit additional assumption** carried by the trusted user-defined interface, not a proof of domain-metric validity. The constructor ignores its C generic `TO` text parameter after code generation; actual callback outputs are type-erased `AnyObject` values. This does not establish that a mismatched callback output type is safe for a later downcast; caller-side type agreement is necessary.

**Result:** There is no claim that OpenDP verifies arbitrary privacy maps. Accepting the caller's trusted proof is intentional for this feature; no new privacy under-accounting bug is established by the constructor alone.

### Callback ownership and lifetime

The exported entrypoint calls `try_as_ref!` on each FFI pointer, including both `CallbackFn` pointers, and clones both callbacks into Rust-owned closures. `CallbackFn::Clone` clones its `ExtrinsicObject` payload, which calls the host `REF_COUNT` hook to increase its reference count; `Drop` decrements it. Each `wrap_func` closure owns the cloned callback/userdata and obtains the raw pointer only while invoking the callback. Thus the original temporary host-side `CallbackFn` pointer need not remain valid after construction **if** host reference-count initialization and callback allocation are correct.

The Python host stores `(func, TO)` in an `ExtrinsicObject(ctypes.py_object(...))` and registers `_set_ref_count(_REF_COUNT)` during library initialization. The callback dispatcher and refcount delegate are module-level objects retained while the module is live. The Rust `REF_COUNT.get().unwrap()` calls depend on that registration and can panic if an external caller bypasses the host initialization; this source review does not establish a complete safe C API for arbitrary hosts or concurrency and therefore records the lifetime claim as `Partial`, not a native memory-safety proof.

### FFI callback result and errors

The Rust `wrap_func` invokes the stored C callback, feeds its returned `FfiResult` pointer into `into_owned`, and then converts that result into `Fallible<AnyObject>`. The `into_owned` helper rejects a null returned pointer with a fallible FFI error rather than immediately dereferencing it. A successful Python callback converts its result to an owned `AnyObject` allocation and packages it with `ffiresult_ok`; the Python dispatcher catches ordinary Python `Exception` values and packages them with `ffiresult_err`, preserving a traceback. Both the mechanism function and privacy-map callback use this same wrapper.

This is a source-level error propagation trace. It **does not** verify malformed success payloads, host registration failures, panics in foreign callbacks, exception classes not caught by Python `except Exception`, or concurrent runtime shutdown; therefore broader error/ABI robustness remains `Partial`.

## Findings

**Bounded negative result:** Under the explicit trusted-callback and initialized-host assumptions, the constructor captures refcounted userdata, forwards ordinary callback errors, and leaves the DP proof obligation with the caller as documented. No confirmed new OpenDP defect was found in these scoped properties.

**Boundary not proven:** The raw C ABI is not safe against arbitrary invalid callback pointers or missing host reference-count registration. The constructor's `honest-but-curious` feature flag and the Python host setup are material requirements. No native OpenDP FFI invocation, leak/refcount measurement, or Rust memory checker was executed.

## Next checks

- Execute native Python/R FFI integration tests constructing a user-defined measurement, dropping Python callback references immediately after construction, invoking the measurement/map repeatedly, and checking finalizers/refcounts after measurement drop.
- Test ordinary callback exceptions and null/error results, including serialization/type-erasure mismatches and callbacks invoked after interpreter shutdown.
- Separately review the foreign-host registration contract if direct C users are expected to invoke this entrypoint without Python/R initialization.
