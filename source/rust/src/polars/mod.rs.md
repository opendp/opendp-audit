---
schema_version: 1
source: rust/src/polars/mod.rs
updated: 2026-11-22
---

# `rust/src/polars/mod.rs`

## Scope and assumptions

Reviewed the native Rust OnceFrame collection branch and `shuffle_dataframe`, focusing on a single-use plan and an output permutation that does not disclose original row ordering. Assumes a correctly implemented Polars `DataFrame::take`, a sound `SliceRandom::shuffle`, and functioning entropy. [Pinned Rust source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/mod.rs#L503).

This report covers only the declared properties at upstream commit `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. The cross-file argument and its limits are in [the OnceFrame investigation](../../../../investigations/onceframe-output-order.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `polars::shuffle_dataframe` | privacy/uniform-output-permutation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file evidence](../../../../investigations/onceframe-output-order.md) — One index of each row is shuffled before `DataFrame::take`. |
| `polars::OnceFrame::from(LazyFrame)` | correctness/single-consumption | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file evidence](../../../../investigations/onceframe-output-order.md) — `state.take()` occurs before collection and shuffle; failed collections still consume. |
| `polars::OnceFrame::collect` | correctness/single-consumption | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file evidence](../../../../investigations/onceframe-output-order.md) — Dispatches the external collect query; FFI builds reject Rust-side collection. |

## Analysis

The shuffler converts the height to `IdxSize`, reserves exactly enough indices, creates `0..n`, calls the OpenDP `Shuffle` trait, then takes the DataFrame at those indices. There is no replacement of indices or data-dependent sorting in this function. Index-width overflow and allocation failures are returned as errors. The non-FFI query branch takes and clears state before running Polars; internal `TakeLazyFrame` also consumes state. Internal `ExtractLazyFrame` clones state and is a separately documented honest-but-curious escape hatch. [Source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/mod.rs#L503) and [existing native row/schema test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/test.rs#L86).

**Execution status:** Code and upstream tests were inspected through GitHub; no Rust or Python test suite was executed in this audit session. Therefore coverage remains **Partial**.

## Next checks

Run feature-matrix Rust tests and verify Polars `take` behavior with chunked columns, nulls, and large index widths.
