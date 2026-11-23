---
schema_version: 1
source: rust/src/transformations/make_stable_expr/namespace_dt/expr_datetime_component/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/namespace_dt/expr_datetime_component/mod.rs`

## Scope and assumptions

- **Audit scope:** Non-deprecated `make_expr_datetime_component`, its `match_datetime_component` dtype mapping, and the compatibility of calendar/time-of-day operations with `DataType::Date`, `DataType::Time`, and `DataType::Datetime(Nanoseconds, _)`. The issue concerns successful construction of a stable expression that cannot execute, not privacy-map calibration.
- **Invariants:** A `Transformation` constructor should not accept an expression whose execution fails for every value of the public input dtype. Accepted temporal component functions must have Polars kernels for the admitted dtype. `Datetime` in milliseconds/microseconds is intentionally excluded due to possible out-of-range physical timestamps.
- **Assumptions:** Source uses OpenDP upstream commit `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` and the locally patched Polars `py-1.36.1` tag from `rust/Cargo.toml`. The test model represents the specified dtype match arms; no compiled Rust/Polars execution was performed.
- **Pinned references:** [OpenDP constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/namespace_dt/expr_datetime_component/mod.rs), [existing Rust tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/namespace_dt/expr_datetime_component/test.rs), [Polars Series `TemporalMethods`](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-time/src/series/mod.rs), [Polars DSL](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-plan/src/dsl/dt.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_expr_datetime_component` | correctness/dtype-function-compatibility | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-product guard mismatch](#cross-product-guard-mismatch) |
| `make_expr_datetime_component` | correctness/temporal-range-validation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Timestamp range restriction](#timestamp-range-restriction) |
| `match_datetime_component` | correctness/output-dtype-contract | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Output schema and tested subsets](#output-schema-and-tested-subsets) |

## Analysis

### Cross-product guard mismatch

The constructor checks `match_datetime_component(&temporal_function)` first, recognizing `Year`, `Month`, `Hour`, `Minute`, and other calendar/time components. It then **independently** accepts any `in_dtype` of `Time`, `Date`, or `Datetime(Nanoseconds, _)`. The two checks allow **every recognized operation** for every permitted dtype.

Pinned Polars `TemporalMethods::year` matches `Date` or `Datetime(_,_)`, returning `polars_bail!(opq = year, dt)` otherwise. In particular, **`Time → Year` fails**. Conversely, `TemporalMethods::hour` matches `Time` or `Datetime(_,_)`, returning `polars_bail!(opq = hour, dt)` otherwise. In particular, **`Date → Hour` fails**. The OpenDP constructor creates a row-wise `Function::then_expr` and identity stability map for both, but the resulting expression is not executable for any valid member of the given public dtype. These are public-schema-dependent failures, not evidence of a DP violation.

Concrete proposed native regressions:

```rust
// DataFrame with a valid `Time` column "t":
// make_stable_lazyframe(..., lf.clone().select([col("t").dt().year()])) should Err.
// DataFrame with a valid `Date` column "d":
// make_stable_lazyframe(..., lf.clone().select([col("d").dt().hour()])) should Err.
```

Six standard-library Python model tests checked the source predicate and the pinned Polars `year`/`hour` family match arms. The model established the two false acceptances, valid positive cases, and independent millisecond/microsecond restrictions. **These tests are not native Rust/Polars executions.** [Investigation](https://github.com/opendp/opendp-audit/blob/main/investigations/polars-temporal-component-dtype-compatibility.md); [candidate issue #66](https://github.com/opendp/opendp-audit/issues/66).

### Timestamp range restriction

OpenDP deliberately rejects `Datetime(Milliseconds,_)` and `Datetime(Microseconds,_)` because physical `i64` timestamp values may lie outside Chrono's representable calendar range, but accepts `Datetime(Nanoseconds,_)`. Its existing Rust test uses `i64::MAX` to check the branch. This audit inspected the check and the test without executing the native implementation, so status remains **Partial**.

### Output schema and tested subsets

`match_datetime_component` assigns `Int32` for `Year`, `Int8` for `Hour`, etc., and marks the output `SeriesDomain` nullable. Existing upstream Rust schema tests cover calendar components on `Date` and time-of-day components on `Time`, but do **not** test the incompatible cross-product. The audit did not independently prove output dtype accuracy for every supported temporal function or time zone; status **Partial**.

## Next checks

- Add an operation/dtype compatibility guard at construction, preserving valid `Date→Year`, `Time→Hour`, and `Datetime(ns)→{Year,Hour}` cases. At minimum, separate calendar-only and time-only component subsets, or consult pinned Polars schema inference if its errors are reliably surfaced before constructing the transformation.
- Run compiled OpenDP Rust/Polars and FFI tests on both false-acceptance witnesses and positive cases, and validate that unsupported calls return a structured constructor error without executing private data.
- Track as [audit issue #66](https://github.com/opendp/opendp-audit/issues/66). **Upstream disposition: Unreported**, after searching for a matching issue or corrective PR. No upstream repository changes were made.
