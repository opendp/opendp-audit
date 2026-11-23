---
schema_version: 1
upstream_commit: 7acfb2cdcee7d39fc26a6ade7edac15249c52f4b
updated: 2026-11-23
status: Partial
---

# R extrinsic ownership across the Rust FFI thread boundary

## Invariant and threat model

R-owned `SEXP` descriptors and callback contexts retained by Rust must not be concurrently retained, released, or evaluated unless the ownership protocol is safe for cross-thread use and the R runtime's thread-affinity requirements. A data race on a shared counter or R API calls from worker threads would violate this invariant. This review considers correctly-allocated R objects passed through the supported FFI bridge, not arbitrary malicious foreign pointers.

## Affected symbols and source audits

- [`ExtrinsicObject`, `Clone`, `Drop`, `Send`, `Sync`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/ffi/util.rs#L60-L106); [Rust source audit](../source/rust/src/ffi/util.rs.md).
- [`ref_count_callback`, `new_retained_sexp`, `new_callback_context`, `free_retained_sexp`, `free_callback_context`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/R/opendp/src/udf.c#L20-L200); [R source audit](../source/R/opendp/src/udf.c.md).
- [`total_cmp_callback` and R-side `compare_exec`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/R/opendp/src/udf.c#L198-L315): R interpreter callbacks using similar foreign state.
- The Rust hook is process-global `OnceLock<extern "C" fn(...)>`; R sets it in `init_udf_support`.

## Reasoning and evidence

1. Rust declares `unsafe impl Send for ExtrinsicObject` and `unsafe impl Sync for ExtrinsicObject` without a documented requirement restricting its methods to the R main thread.
2. Rust `ExtrinsicObject::clone` and `Drop::drop` invoke a process-global FFI refcount function without locking or thread checking. The return Boolean is ignored.
3. The R implementation `ref_count_callback` uses mutable C `int ref_count` fields in both `RetainedSexp` and `CallbackContext`. Each increment and decrement is a non-atomic read-modify-write; the zero transition frees memory.
4. A permitted concurrent clone/release of the same R-managed pointer would race. Lost increments can cause premature freeing while another Rust object still holds the pointer, or racing decrements can cause memory corruption. The callback also executes `R_ReleaseObject`, which requires an R-safe execution context. R comparison callbacks invoke `Rf_eval`, another thread-affinity-sensitive operation.
5. This identifies a **conditional source-level memory-safety hazard**, not a proven public exploit. No concurrency reproducer, ThreadSanitizer run, R integration test, or private-data disclosure was executed or observed. Source-level inspection cannot show that routine R usage schedules these operations from multiple threads.

The Python ctypes `_ref_count` callback is not evidence of the R counter race: it is a separate backend with different runtime synchronization behavior.

## Findings

- [Candidate defect #113](https://github.com/opendp/opendp-audit/issues/113): R extrinsic refcount callback races with Rust Send/Sync object cloning; **Verification: Candidate**; **Upstream: Unreported** at the reviewed revision.
- [Audit claim #111](https://github.com/opendp/opendp-audit/issues/111): the bounded review represented here.

## Unresolved questions

- Identify a concrete supported R entrypoint that can clone/drop one R-backed `ExtrinsicObject` on multiple Rust threads, rather than relying on a hypothetical Rust-level schedule.
- Check whether upstream APIs and features enforce main-thread execution globally, and whether other Rust containers inherit `Send`/`Sync` from `ExtrinsicObject`.
- Reproduce a race or establish unreachable code using an R/Rust integration harness and sanitizer as appropriate. Tests have **not** been executed here.
- A safe fix should reconcile Rust's unconditional `Send`/`Sync` with R thread affinity and ownership; making the C counter atomic alone does not make `Rf_eval` or `R_ReleaseObject` thread-safe.
