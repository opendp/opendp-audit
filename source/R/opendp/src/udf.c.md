---
schema_version: 1
source: R/opendp/src/udf.c
updated: 2026-11-23
---

# `R/opendp/src/udf.c`

## Scope and assumptions

- **Audit scope:** Reference ownership of R-backed `RetainedSexp` and `CallbackContext` passed into Rust; concurrency safety of callback operations. Not a full audit of R callback error handling.
- **Invariant:** Each retained R object must remain live until the final reference is released, and R runtime APIs must run in a safe execution context.
- **Assumptions:** Rust `ExtrinsicObject` may call the retain/release callback, and declares itself `Send`/`Sync`; concrete concurrency reachability has not been proven.
- **Source links:** [Pinned R implementation](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/R/opendp/src/udf.c#L100-L201); [Rust bridge](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/ffi/util.rs#L60-L106).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `ref_count_callback` | memory/thread-safety | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Plain `int` read-modify-write and free-on-zero; [analysis](#analysis) |
| `new_retained_sexp` | memory/ownership | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Preserves R object with initial count 1; [analysis](#analysis) |
| `free_retained_sexp` | memory/thread-safety | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Calls `R_ReleaseObject`; [analysis](#analysis) |
| `new_callback_context` | memory/ownership | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Preserves R closure with initial count 1; [analysis](#analysis) |
| `free_callback_context` | memory/thread-safety | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Releases R closure and frees state; [analysis](#analysis) |

## Analysis

`ref_count_callback` updates two foreign-owned refcount variants using C `int` fields with `+= increment ? 1 : -1`. A zero count triggers `free_retained_sexp` or `free_callback_context`, which call `R_ReleaseObject`. There is no mutex, atomic operation, thread scheduling, or assertion restricting callback invocations to the R main thread. Because the Rust wrapper declares `Send`/`Sync`, these assumptions cannot be established at the Rust type boundary alone.

This is a **source-level concurrency candidate**, not a reproduced use-after-free. No test, sanitizer, or R end-to-end execution was performed.

**Related:** [Cross-file investigation](../../../../investigations/r-extrinsic-refcount-cross-thread-ownership.md), [candidate #113](https://github.com/opendp/opendp-audit/issues/113).

## Next checks

Establish whether OpenDP/R can cause the callback to run on multiple threads or whether the backend's execution discipline makes the unsafe trait implementations safe under documented constraints.
