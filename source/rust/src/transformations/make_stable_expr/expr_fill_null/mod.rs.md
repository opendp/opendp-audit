---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_fill_null/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_fill_null/mod.rs`

## Scope and assumptions

Reviewed the **non-deprecated** `make_expr_fill_null` constructor at upstream SHA `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`, its output null/NaN domain flags, dtype coercion checks, and aggregation-margin handling. The review assumes successful deterministic row-by-row expression evaluation and sound Polars type inference; it does **not** execute native OpenDP/Polars code.

- **Invariants:** Replacing null with a public literal or a same-row non-null column is a deterministic record-local mapping and cannot increase multiset symmetric distance. On success the output is non-null; output NaN allowance must include NaNs in the original data or in an actually selectable filler. A post-filter weakened key/length invariant must not be restored.
- **Pinned source:** [implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_fill_null/mod.rs), [native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_fill_null/test.rs); [cross-file investigation](../../../../../../investigations/polars-fill-drop-domain-stability.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `transformations::make_stable_expr::expr_fill_null::make_expr_fill_null` | correctness/null-and-nan-domain-propagation | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Output-domain checks](#output-domain-checks), [reference model](../../../../../../tools/tests/test_polars_fill_drop_model.py) |
| `transformations::make_stable_expr::expr_fill_null::make_expr_fill_null` | privacy/aggregation-invariant-preservation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Context and stability](#context-and-stability) |

## Analysis

### Output-domain checks

The constructor rejects nullable filler expressions. Its output domain is marked `nullable=false`. It computes `output_nan = data_nan || (data_nullable && filler_nan)`: a possibly NaN filler matters **only** if the original data can be null and actually select that filler; an originally NaN-able data column remains NaN-able even after filling null. A numeric dtype change is accepted only through `is_numeric_coercion`, with actual output dtype obtained from `infer_output_dtype`; unsupported mixed nonnumeric types and categorical input are rejected. If `output_nan=false` for a floating output, `set_non_nan` records that constraint. These checks address the NaN-domain underestimation described in closed upstream [issue #2936](https://github.com/opendp/opendp/issues/2936).

The independent [Python model](../../../../../../tools/tests/test_polars_fill_drop_model.py) verified the null/NaN flag formula on 16 source/filler combinations. It is a logical model of flags and finite values, **not a verification of native type coercion, exceptional casts, or Arrow null behavior**. Existing Rust tests cover NaN literals, mixed numeric dtypes, non-null data, and optimized Polars output; inspected, not executed here.

### Context and stability

The source treats a fill referencing a column differently from a public scalar literal. Column-referencing fills force both `data` and `fill` to be stabilized in `input_domain.as_row_by_row()`; thus aggregation-only filters or drops cannot be nested in that branch. For public scalar literals, `t_data` is stabilized in the existing input domain, and the output **copies `data_domain.context`**, retaining any earlier downgrade from `Invariant::Lengths` to `Invariant::Keys`. For column fills it copies the original input context only after enforcing row-by-row evaluation. The old incorrect unconditional restoration of length invariants was reported in closed upstream [issue #3039](https://github.com/opendp/opendp/issues/3039).

Under deterministic per-record semantics, mapping each input record `r` to `f(r)` is nonexpansive in multiset symmetric distance. The [reference test](../../../../../../tools/tests/test_polars_fill_drop_model.py) checked this invariant for all ordered pairs of datasets of length up to three over an eight-record alphabet; no violation. The result is **Partial** because compiled Polars row-local semantics, optimizer rewrites, and data-dependent runtime errors were not independently verified.

## Findings and next checks

No new defect identified within this source/model scope. Two prior privacy-related issues (#2936, #3039) are already closed upstream, so no duplicate issue was filed. Execute native Rust and Polars tests for null/NaN propagation, numeric coercion near extrema, and invariants after aggregation filtering. [Investigation](../../../../../../investigations/polars-fill-drop-domain-stability.md); [audit task #53](https://github.com/opendp/opendp-audit/issues/53).
