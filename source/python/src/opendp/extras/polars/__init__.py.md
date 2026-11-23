---
schema_version: 1
source: python/src/opendp/extras/polars/__init__.py
updated: 2026-11-22
---

# `python/src/opendp/extras/polars/__init__.py`

## Scope and assumptions

Reviewed the public Python `OnceFrame.collect` path, specifically single-use plan extraction and final output shuffling. [Pinned source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/extras/polars/__init__.py#L608).

This report covers only the declared properties at upstream commit `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. The cross-file argument and its limits are in [the OnceFrame investigation](../../../../../../investigations/onceframe-output-order.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `opendp.extras.polars.OnceFrame.collect` | privacy/uniform-output-permutation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file evidence](../../../../../../investigations/onceframe-output-order.md) — Consumes the plan, collects with common-subexpression elimination disabled, then calls Rust FFI shuffle. |

## Analysis

The first operation evaluates `_take_lazy()`, which delegates to Rust's consuming `TakeLazyFrame` internal query. The resulting LazyFrame is collected with `comm_subexpr_elim=False`, and the materialized DataFrame is passed to `_shuffle_dataframe`. Existing upstream tests cover failure exhaustion, heights 0/1/10, and Enum dtype preservation; they were reviewed, not executed. [Python implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/extras/polars/__init__.py#L627), [tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/test/test_polars.py#L415). The separate `lazy()` API permits bypassing collection protections under documented honest-but-curious obligations.

**Execution status:** Code and upstream tests were inspected through GitHub; no Rust or Python test suite was executed in this audit session. Therefore coverage remains **Partial**.

## Next checks

Execute Python tests and confirm the generated binding resolves to `opendp_data___shuffle_dataframe` for supported distributions.
