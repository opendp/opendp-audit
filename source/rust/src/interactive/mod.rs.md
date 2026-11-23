---
schema_version: 1
source: rust/src/interactive/mod.rs
updated: 2026-11-23
---

# `rust/src/interactive/mod.rs`

## Scope and assumptions

- **Audit scope:** `Queryable::eval_query`, `wrap`, `Wrapper::new_recursive_pre_hook`, `Queryable::new`, and the typed/polymorphic queryable bridges. Trace current use by the adaptive compositor, fully adaptive odometer, privacy filter, and `ffi/any.rs`. Review unwind versus ordinary error propagation.
- **Invariants:** A queryable prevents overlapping mutable state transitions; thread-local wrappers should apply recursively to child queryables and be restored when a wrapping scope terminates, including Rust unwinding if the caller catches the panic. Ordinary fallible errors must not leave stale policy. Converting a typed queryable to/from `PolyQueryable` should preserve internal/external query distinctions.
- **Threat model:** Normal OpenDP-compliant child measurements and ordinary Rust execution. Catching a panic in a Rust caller is explicitly considered. The privacy of an arbitrary malicious callback, timing, stdout side effects, FFI abort semantics, and thread safety of non-Send queryables are outside scope. No native OpenDP integration run was performed.
- **Pinned source:** [implementation on OpenDP `main`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/interactive/mod.rs), [FFI type-erasure consumer](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/ffi/any.rs), [adaptive compositor](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/combinators/sequential_composition/adaptive/mod.rs), [privacy-filter review](https://github.com/opendp/opendp-audit/blob/main/investigations/privacy-filter-failure-accounting.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `interactive::Queryable::eval_query` | correctness/reentrant-query-exclusion | Audited | `a010591f55b1713c926f8e355091471634480307` | Uses `try_borrow_mut` on the shared `Rc<RefCell<dyn FnMut>>`, returning `FailedFunction` for overlapping queries rather than panicking on `borrow_mut`. |
| `interactive::wrap` | correctness/thread-local-wrapper-restoration | Audited | `a010591f55b1713c926f8e355091471634480307` | Restores prior wrapper on normal return and returned `Err`, but **not when the closure panics**. Existing [upstream PR #3277](https://github.com/opendp/opendp/pull/3277) directly fixes the unwind case; no duplicate issue. |
| `interactive::Wrapper::new_recursive_pre_hook` | privacy/recursive-child-permission-hooks | Partial | `a010591f55b1713c926f8e355091471634480307` | Calls cloned pre-hook on every wrapped query, then recursively wraps any newly created child queryables while evaluating its inner query. Source-level policy forwarding correct; native nested-queryable execution not rerun. |
| `interactive::Queryable::new` | privacy/queryable-wrapper-attachment | Audited | `a010591f55b1713c926f8e355091471634480307` | Reads current thread-local wrapper, applies it to the newly created queryable through `IntoPolyQueryable` / `FromPolyQueryable`. Raw constructors deliberately do not attach it. |
| `interactive::IntoPolyQueryable::into_poly` and `FromPolyQueryable::from_poly` | correctness/external-internal-query-type-preservation | Audited | `a010591f55b1713c926f8e355091471634480307` | External requests and responses require matching Rust type downcasts; internal requests forward `Answer::Internal` and reject incorrectly typed answer variants. |
| `interactive::Queryable::new_raw_external` | correctness/explicit-wrapper-bypass | Partial | `a010591f55b1713c926f8e355091471634480307` | Used in `post_alp_state_to_queryable` after the ALP DP state is already generated; unlimited key queries are postprocessing of sanitized state and thus need not consume incremental privacy budget. Other potential callers not proven. |

## Analysis

### Queryable reentrancy, type erasure, and error propagation

`Queryable` holds a shared `Rc<RefCell<dyn FnMut>>`, so clones share mutation state. `eval_query` obtains an exclusive mutable borrow with `try_borrow_mut`, returning a fallible `FailedFunction` error for simultaneous or reentrant use of the *same* queryable, rather than an unhandled `RefCell` borrow panic.

`eval` accepts only `Answer::External`, and `eval_internal` only `Answer::Internal`. Both typed-to-polymorphic bridges delegate to their respective wrapped queryable and preserve the external/internal variant split; type mismatches become `FailedCast` errors. The bridges are not privacy accountants themselves, but this behavior preserves the authorization interface used by the compositors.

### Recursive child policy

`Wrapper::new_recursive_pre_hook` attaches `hook()` to every call on a wrapped queryable. During evaluation it invokes `wrap(recursive_wrapper.to_wrapper(), || inner_qbl.eval_query(query))`, so any `Queryable::new` created by that inner query inherits the same recursive wrapper. Hooks are cloned once per wrapped queryable, and the compositor's concrete hooks capture shared `Rc<RefCell<_>>` state and a parent queryable reference. Whether those concrete hooks correctly retire previous children is reviewed separately in [adaptive composition](https://github.com/opendp/opendp-audit/blob/main/investigations/adaptive-composition-reservation-and-retirement.md) and [privacy filter failure accounting](https://github.com/opendp/opendp-audit/blob/main/investigations/privacy-filter-failure-accounting.md).

No new source-level child-policy bypass is established by this bounded review.

### Wrapper TLS unwind restoration: existing pending fix

At upstream `a010591f55b1713c926f8e355091471634480307`, `wrap` saves `WRAPPER` in `prev_wrapper`, installs the combined wrapper, calls `f()`, then restores the previous value **after** the call returns. Because restoration is not guarded by `Drop`, a panic inside `f()` skips the restoration. If a Rust caller catches that unwind and reuses the thread, later unrelated `Queryable::new` calls may inherit the stale recursive policy and be spuriously rejected. This is state/policy isolation failure, not an established differential-privacy output leak.

Returning `Err` from `f()` does **not** trigger this problem: `wrap` is generic in its return type, so an ordinary fallible return reaches the restoration statement. The same unwind weakness applies to the manually suspended/restored wrapper in `ffi/any.rs`.

The existing [open upstream PR #3277](https://github.com/opendp/opendp/pull/3277) is directly responsive: it adds a `WrapperGuard` with `Drop` restoration, a `without_wrapper` helper for the FFI type-erasure boundary, and a `catch_unwind` regression for nested and suspended wrappers. Its patch was inspected in this audit; it is **not yet merged into `main`**. Prior [privacy-filter investigation](https://github.com/opendp/opendp-audit/blob/main/investigations/privacy-filter-failure-accounting.md) also noted this overlap. Under the existing-upstream-fix deduplication rule, **no new candidate issue is needed**.

### Explicit raw constructor

`Queryable::new_raw_external` intentionally bypasses `WRAPPER` and is used in the ALP `post_alp_state_to_queryable` postprocessor. That queryable answers from an already randomized `AlpState<K>`; querying it is postprocessing of the DP projection and does not by itself invoke the raw private data. This use is not a counterexample to the compositor privacy map. The function remains marked `dead_code`-allowed and crate-private.

## Findings and next checks

- **No novel defect established** for reentrancy, typed/polymorphic forwarding, and intended recursive hooks.
- **Known correctness weakness:** Panic-unwind restoration of `WRAPPER` is incomplete on reviewed `main`; [open PR #3277](https://github.com/opendp/opendp/pull/3277) supplies the matching fix. A caught panic could contaminate later queryable policy. No distinct issue filed.
- **Execution:** Source reasoning and inspection of upstream PR patch only. No compiled Rust tests executed in this session. Repository schema/tests may validate this audit record but do not establish the interactive runtime invariants.
- **Related tracking:** [Audit task #151](https://github.com/opendp/opendp-audit/issues/151). Verify PR #3277's native tests and post-merge state; consider future nested reentrancy tests across both `new` and `new_raw`.
