---
schema_version: 1
source: rust/src/polars/mod.rs
updated: 2026-11-22
---

# `rust/src/polars/mod.rs`

## Scope and assumptions

Reviewed the native Rust OnceFrame collection branch and `shuffle_dataframe`, focusing on a single-use plan and an output permutation that does not disclose original row ordering. Assumes a correctly implemented Polars `DataFrame::take`, a sound `SliceRandom::shuffle`, and functioning entropy. [Pinned Rust source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/mod.rs#L503).

**Additional scope, reviewed at a010591f55b1713c926f8e355091471634480307:** the Polars FFI native-plugin trust predicate in `match_plugin` and `match_trusted_plugin`, whether `apply_plugin` preserves the caller's executable library, and the trusted versus untrusted serialization preflight boundaries. [Cross-file investigation](../../../../investigations/polars-ffi-plugin-library-identity.md). This property is independent of the earlier `OnceFrame` row-order audit.

This report covers only the declared properties at upstream commit `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. The cross-file argument and its limits are in [the OnceFrame investigation](../../../../investigations/onceframe-output-order.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `polars::shuffle_dataframe` | privacy/uniform-output-permutation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file evidence](../../../../investigations/onceframe-output-order.md) — One index of each row is shuffled before `DataFrame::take`. |
| `polars::OnceFrame::from(LazyFrame)` | correctness/single-consumption | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file evidence](../../../../investigations/onceframe-output-order.md) — `state.take()` occurs before collection and shuffle; failed collections still consume. |
| `polars::OnceFrame::collect` | correctness/single-consumption | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file evidence](../../../../investigations/onceframe-output-order.md) — Dispatches the external collect query; FFI builds reject Rust-side collection. |

| `polars::match_plugin` | privacy/ffi-plugin-library-identity | Partial | `a010591f55b1713c926f8e355091471634480307` | [Plugin identity trust boundary](#ffi-plugin-identity-trust-boundary); [defect #159](https://github.com/opendp/opendp-audit/issues/159) |
| `polars::match_trusted_plugin` | privacy/ffi-plugin-library-identity | Partial | `a010591f55b1713c926f8e355091471634480307` | [Trusted plugin identity](#ffi-plugin-identity-trust-boundary); distinct preflight semantics |
| `polars::apply_plugin` | privacy/ffi-executable-library-retention | Audited | `a010591f55b1713c926f8e355091471634480307` | [Executable library retention](#ffi-plugin-identity-trust-boundary), [source-equivalent regression](../../../../tools/tests/test_polars_ffi_plugin_identity_model.py) |

## Analysis

The shuffler converts the height to `IdxSize`, reserves exactly enough indices, creates `0..n`, calls the OpenDP `Shuffle` trait, then takes the DataFrame at those indices. There is no replacement of indices or data-dependent sorting in this function. Index-width overflow and allocation failures are returned as errors. The non-FFI query branch takes and clears state before running Polars; internal `TakeLazyFrame` also consumes state. Internal `ExtractLazyFrame` clones state and is a separately documented honest-but-curious escape hatch. [Source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/mod.rs#L503) and [existing native row/schema test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/test.rs#L86).

**Execution status:** Code and upstream tests were inspected through GitHub; no Rust or Python test suite was executed in this audit session. Therefore coverage remains **Partial**.

### FFI plugin identity trust boundary

At pinned [OpenDP `a010591f55b1713c926f8e355091471634480307`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/polars/mod.rs), both `match_plugin::<KW>` (for recognized FFI shims) and `match_trusted_plugin::<KW>` (for post-rewrite plugin arguments) accept any `FfiPlugin.lib` string containing the substring `"opendp"`, provided the plugin symbol matches `KW::NAME`. This is **not an exact canonical-library identity test**.

On recognizing an FFI shim, the private-expression constructor (e.g., [`make_expr_noise`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/make_private_expr/expr_noise/mod.rs)) builds a privacy map for **OpenDP's** mechanism. When `apply_plugin` replaces the shim with its executable variant (`noise_plugin` in that example), it forwards the **original `lib` value unchanged**. A third-party plugin library with a path containing `opendp` can therefore be *accepted as an OpenDP shim* and retained as the *executable plugin library* while its privacy map assumes OpenDP's noise law. This is a source-level **implementation-identity mismatch**; no external native library was compiled or executed.

The separate, current [preflight sanitizer](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/polars/preflight/mod.rs) **does protect the default untrusted serialized-plan path** by rebinding allowed DP shim symbols to the locally loaded canonical OpenDP library **before** Polars deserialization. For `trusted=True`, it deliberately preserves third-party plugin paths unless the basename looks exactly like the canonical OpenDP library; an unrelated filename containing `opendp` is preserved in this case and still satisfies `match_plugin`'s weaker substring predicate. This distinction is documented in the [cross-file investigation](../../../../investigations/polars-ffi-plugin-library-identity.md) and [issue #159](https://github.com/opendp/opendp-audit/issues/159).

**Verification:** Standalone Python source-model tests of the exact string predicates, plugin-library-field retention and trusted versus untrusted rebinding; no compiled Polars/OpenDP runtime. The conditional security concern applies only to locally authored or *explicitly trusted* plans with third-party native libraries. It is **not a demonstrated remote-untrusted serialization bypass**, and allowing arbitrary native code is already a privileged capability. The matcher and trusted-matcher privacy properties remain `Partial`; exact retention by `apply_plugin` is audited at the specified source level.

## Next checks

Run feature-matrix Rust tests and verify Polars `take` behavior with chunked columns, nulls, and large index widths.
