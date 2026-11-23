---
schema_version: 1
source: rust/src/data/ffi/polars.rs
updated: 2026-11-22
---

# `rust/src/data/ffi/polars.rs`

## Scope and assumptions

Reviewed only the Polars DataFrame shuffling FFI entrypoint used by Python `OnceFrame.collect`. Assumes pointer validity and ownership rules of the generated Python bindings. [Pinned source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/polars.rs#L101).

This report covers only the declared properties at upstream commit `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. The cross-file argument and its limits are in [the OnceFrame investigation](../../../../../investigations/onceframe-output-order.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `data::ffi::polars::opendp_data___shuffle_dataframe` | correctness/row-permutation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file evidence](../../../../../investigations/onceframe-output-order.md) — Downcasts the DataFrame, clones it, delegates to Rust shuffler, and propagates errors. |

## Analysis

The FFI function borrows and downcasts its argument, clones the DataFrame, and calls `shuffle_dataframe` before wrapping the result. This does not introduce a separate noncryptographic shuffle path. It is not a proof of general FFI pointer or allocation safety, which remain outside scope. [Source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/polars.rs#L101).

**Execution status:** Code and upstream tests were inspected through GitHub; no Rust or Python test suite was executed in this audit session. Therefore coverage remains **Partial**.

## Next checks

Run Python/Polars FFI tests, including shuffle failure propagation and object-lifetime instrumentation.
