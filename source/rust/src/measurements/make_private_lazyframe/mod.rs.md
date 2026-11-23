---
schema_version: 1
source: rust/src/measurements/make_private_lazyframe/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/make_private_lazyframe/mod.rs`

## Scope and assumptions

- **Scope:** Rust `make_private_lazyframe` execution-function construction, specifically preservation of caller optimization flags followed by disabling common-subexpression elimination (CSE) before a Polars plan containing random noise plugins executes.
- **Invariant:** Independent noise evaluations in a private release must not be deduplicated by CSE; ordinary Python `OnceFrame.collect` must also disable it at collection.
- **Assumptions:** `LazyFrame::with_comm_subexpr_elim(false)` and Python `QueryOptFlags(comm_subexpr_elim=False)` have the documented semantics in supported Polars. No claim is made about CSE-like behavior in other optimizer passes, explicitly bypassed honest-but-curious collection, or arbitrary user-defined plugins.
- **Pinned source:** [constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/mod.rs#L121), [Python collection](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/extras/polars/__init__.py#L628), [regression test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/test/test_polars_noise_cse.py#L1).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::make_private_lazyframe` | correctness/optimizer-cse-disabled | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Static call order](#analysis): Rust disables CSE after applying caller optimization settings. |
| `measurements::make_private_lazyframe` | privacy/noise-draw-independence | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file investigation](../../../../../investigations/private-lazyframe-cse.md) traces ordinary collection and examines the upstream regression test. Polars execution not independently tested. |

## Analysis

The constructor first compiles the DP plan into `m_lp` and clones its function `f_lp`. Its release closure evaluates `f_lp` against the input's logical plan, wraps the result in a new `LazyFrame`, applies caller optimization flags via `with_optimizations(arg.get_current_optimizations())`, and **then** calls `with_comm_subexpr_elim(false)`. This final call is significant: user-supplied CSE settings are overridden before wrapping the plan in `OnceFrame`. No plan is collected in this closure. [Pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/mod.rs#L138).

The normal Python release path extracts the plan once and calls `collect(optimizations=pl.QueryOptFlags(comm_subexpr_elim=False))`, applying an additional collection-time guard. [Pinned Python source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/extras/polars/__init__.py#L626). Native Rust `OnceFrame` collection uses the stored plan and its Rust-side optimization setting, as described in the [prior OnceFrame audit](../../polars/mod.rs.md).

The [upstream regression test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/test/test_polars_noise_cse.py#L1) checks imputed public-key aggregates where independent private draws might otherwise be shared. Its `onceframe` and `lazy_without_cse` variants require distinct sampled outputs, while `lazy_with_cse` is a strict expected failure that exercises the explicitly honest-but-curious escape hatch. That test was inspected, **not executed** in this session.

Historical [upstream issue #3238](https://github.com/opendp/opendp/issues/3238) is closed by [merged PR #3233](https://github.com/opendp/opendp/pull/3233), which introduced the guards and regression test. The fix exists on reviewed upstream `main`.

**Conclusion:** The exact code-level guard ordering was audited; no missing CSE override was found on the ordinary paths. The broader independent-noise privacy property remains **Partial** because this audit did not execute the Polars runtime, verify every optimizer pass, or attempt a formal proof. See [cross-file reasoning](../../../../../investigations/private-lazyframe-cse.md).

## Next checks

- Run upstream `python/test/test_polars_noise_cse.py` with supported Polars/FFI builds, including an optimizations-enabled input LazyFrame.
- Independently verify Polars `with_comm_subexpr_elim(false)` and `QueryOptFlags` behavior and whether any other optimizer can share randomized plugin outputs.
- Keep `OnceFrame.lazy()` honest-but-curious requirements explicit; bypassing the guard is not covered by the normal release guarantee.
