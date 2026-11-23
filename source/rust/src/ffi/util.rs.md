---
schema_version: 1
source: rust/src/ffi/util.rs
updated: 2026-11-23
---

# `rust/src/ffi/util.rs`

## Scope and assumptions

- **Audit scope:** The `ExtrinsicObject` wrapper's cross-thread ownership and foreign callback calls. Not a full audit of scalar FFI conversion or the dispatch table.
- **Invariant:** Thread-safe type declarations must be justified by the foreign backend's retain/release and comparison contracts.
- **Assumptions:** The R backend initializes `REF_COUNT`/`TOTAL_CMP` and may pass R-owned pointers in `ExtrinsicObject`; no assumption that an R public method actually launches a concurrent clone/drop.
- **Source links:** [Pinned implementation](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/ffi/util.rs#L60-L106); [R backend](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/R/opendp/src/udf.c#L167-L198).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `ExtrinsicObject::clone` | memory/thread-safety | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Unsynchronized global callback; [analysis](#analysis) |
| `ExtrinsicObject::drop` | memory/ownership | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Unsynchronized release callback; [analysis](#analysis) |
| `ExtrinsicObject::total_cmp` | memory/thread-safety | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Invokes backend comparison on current thread; [analysis](#analysis) |
| `ExtrinsicObject::Send` | memory/thread-safety | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Unconditional unsafe trait impl; [analysis](#analysis) |
| `ExtrinsicObject::Sync` | memory/thread-safety | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Unconditional unsafe trait impl; [analysis](#analysis) |

## Analysis

The `unsafe impl Send` and `unsafe impl Sync` bypass compiler-generated thread-safety checks on foreign pointers. Both cloning and dropping invoke `REF_COUNT` directly with no scheduling or synchronization guard. The R callback behind that function increments/decrements a plain `int` and frees the wrapper on zero. If cloned or dropped concurrently, that protocol would not uphold the Rust marker-trait safety contract.

`ProductOrd::total_cmp` similarly calls a backend callback; R implementation evaluates expressions using the R interpreter, which is thread-affinity sensitive.

**Conclusion:** A conditional cross-thread ownership hazard is present at source level. Reachability and a concrete race were not established. **No claim of a confirmed exploitable vulnerability or privacy leakage.**

**Related:** [Cross-file investigation](../../../../investigations/r-extrinsic-refcount-cross-thread-ownership.md), [candidate #113](https://github.com/opendp/opendp-audit/issues/113).

## Next checks

Trace all R-backed `ExtrinsicObject` storage sites through any parallel Rust execution before elevating candidate verification. Run a sanitizer-backed integration test if a supported concurrent path exists.
