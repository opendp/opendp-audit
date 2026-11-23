---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Polars nullable/NaN fill and drop: domain flags, stability and margins

## Scope and invariant

Reviewed non-deprecated `make_expr_fill_null`, `make_expr_fill_nan`, and `make_expr_drop_nan_or_null` at pinned OpenDP SHA `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. These operations are intended to be deterministic record-local substitution or deletion operators. Under multiset symmetric distance, such operations cannot increase distance, provided each accepted expression is evaluated successfully and only from the current record and public literals. The output domain must conservatively track nullable/NaN capabilities, and filling a previously filtered aggregation must not restore a public-length invariant. This is a **conditional source-level** analysis; the compiled Rust/Polars runtime was not executed.

- [`fill_null` source audit](../source/rust/src/transformations/make_stable_expr/expr_fill_null/mod.rs.md); [upstream Rust](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_fill_null/mod.rs) and [tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_fill_null/test.rs).
- [`fill_nan` source audit](../source/rust/src/transformations/make_stable_expr/expr_fill_nan/mod.rs.md); [upstream Rust](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_fill_nan/mod.rs) and [tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_fill_nan/test.rs).
- [`drop_nulls`/`drop_nans` source audit](../source/rust/src/transformations/make_stable_expr/expr_drop_nan_or_null/mod.rs.md); [upstream Rust](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_drop_nan_or_null/mod.rs) and [tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_drop_nan_or_null/test.rs).
- [Independent Python model](../tools/tests/test_polars_fill_drop_model.py), executed locally with 4 passing `unittest` tests.

## Correctness and source-level privacy reasoning

### Record-local non-expansiveness

For a multiset `X`, let `n_X(r)` be the number of occurrences of record `r`. Any **same deterministic record-local function** `f` sends each record to an output record or suppresses it. For any output `v`, `n_{f(X)}(v)=Σ_{r:f(r)=v} n_X(r)`. By the triangle inequality,

`Σ_v |n_{f(X)}(v)-n_{f(Y)}(v)| ≤ Σ_r |n_X(r)-n_Y(r)|`.

Therefore deterministic `fill_null` and `fill_nan` substitutions and `drop_nulls`/`drop_nans` deletions are non-expansive for symmetric multiset distance. With a fixed grouping key, the same inequality applies within each group. This reasoning applies only if `f` does not inspect other private records, or raise data-dependent failures.

Both fill constructors require a scalar literal or a filler expression referencing columns; the latter forces both operands into `Context::RowByRow`, rejects unsupported nested aggregation-only operations, and requires equal output metrics. The drop constructor works within an aggregation and composes a deterministic deletion with identity stability map.

### NaN and null output flags

`fill_null` requires a non-nullable filler and sets `output.nullable=false`. Its NaN flag is `data.nan || (data.nullable && fill.nan)`. It therefore records a NaN only if it was permitted in the original data or an actually selected filler can introduce one. `fill_nan` requires a non-nullable, non-NaN numeric filler, sets a fresh non-NaN floating atom domain (conservatively forgetting previous numerical bounds), and retains the data column's nullable flag. It leaves nulls in place. `DropNulls` removes nullability while retaining possible NaNs; `DropNans` removes NaN allowance while retaining nullability.

These source branches are consistent with the independent [model](../tools/tests/test_polars_fill_drop_model.py) and specific upstream Rust tests, which were **inspected but not run** in this session.

### Length and key invariants

The two fill constructors take `data_domain.context` from the *stabilized* data expression when the filler is a scalar literal. An earlier aggregation-level `Expr::Filter` or drop operation may have downgraded `Invariant::Lengths` to `Invariant::Keys`, and the subsequent fill must preserve that downgrade rather than reset to the original input-domain invariant. For column fills, the original context is copied **only after** forcing row-by-row stabilization; an aggregation filter cannot be nested successfully there. The drop constructor explicitly maps `Some(Lengths)` or `Some(Keys)` to `Some(Keys)`, leaving `None` unchanged. A group may retain its key even when all values in that group's expression are dropped, but cannot retain a guaranteed number of values.

This checks the source-level preconditions of previously reported [privacy issue #3039](https://github.com/opendp/opendp/issues/3039), which is closed on the pinned source. NaN-domain propagation corresponds to closed [privacy issue #2936](https://github.com/opendp/opendp/issues/2936). Neither is a newly discovered defect, and no duplicate audit issue was filed. The formerly open [PR #3027](https://github.com/opendp/opendp/pull/3027) was closed without merge; its proposed regression cases appear in the pinned source tests. This review does not infer a fix was merged via that exact PR.

## Executed independent finite reference model

The standard-library [test](../tools/tests/test_polars_fill_drop_model.py) was run locally as `python -m unittest -v /mnt/data/test_polars_fill_drop_model.py` and **four tests passed**. An eight-record alphabet pairs `{NULL, NaN, -1, 2}` with a public or same-row non-null/non-NaN fallback `{0,3}`. All datasets of length 0–3 yield `1+8+64+512=585` ordered tuples. The model checks all 585² ordered dataset pairs independently under each of the four operations, totaling **1,368,900 multiset-distance inequalities**, all passing. Additional tests check 16 null/NaN domain-flag combinations, expected difference between null-filling and NaN-filling, and key/length margin witnesses after drop.

The model is not compiled OpenDP. In particular, it cannot verify Polars numeric coercion, actual optimizer semantics, null bitmaps, data-dependent warnings/errors, or all `StableExpr` subexpressions. Its comparisons support the **mathematical record-local claim only**, not the complete end-to-end privacy theorem.

## Findings and disposition

No new defect identified in the reviewed source branches or reference model. The closed upstream privacy issues #2936 and #3039 are relevant precedents but do not warrant reopening without a fresh counterexample. No new candidate-defect issue or upstream PR was opened; [audit task #53](https://github.com/opendp/opendp-audit/issues/53) records the bounded review.

Overall privacy verification is **Partial**, conditional on row-locality and successful native execution.

## Next checks

- Run actual upstream Rust/Polars integration tests and FFI tests for typed mixed-numeric fillers, `f32/f64` extrema, NaN/NULL values, and optimizer rewrites.
- Reproduce the historical #3039 query against the current revision under different group-margin invariants to ensure budget accounting is conservative.
- Check execution exceptions and warnings, particularly unsupported casts or pathological input types, for data-dependent disclosures.
