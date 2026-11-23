---
schema_version: 1
source: rust/src/transformations/make_stable_lazyframe/select/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_lazyframe/select/mod.rs`

## Scope and assumptions

- **Scope:** The non-deprecated Polars `make_select` transformation, especially its row-dependence and projection-option guards, identity/alias lineage, output-column domain mapping, and contribution-bound/margin preservation. Helper functions are covered separately in the [`make_stable_lazyframe` helper report](../mod.rs.md).
- **Invariant:** For a fixed deterministic per-record projection with row count preserved, multiset symmetric distance cannot increase. An output certificate referencing column roots may be retained only if those original columns still exist with unchanged values, or if a conservative selector rule establishes no changed columns.
- **Assumptions:** The upstream `StableExpr` implementation enforces row-by-row semantics and correct output domains; Polars `should_broadcast=true` broadcasts public scalar expressions without reducing row counts; `duplicate_check=true` prevents colliding output names. Actual Rust/Polars runtime, optimizer and exceptional behavior were **not executed**.
- **Pinned source:** [`make_select`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/select/mod.rs), [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/select/test.rs), [projection options](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/options.rs); revision `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`.
- **Evidence:** [Cross-file investigation](../../../../../../investigations/polars-select-projection-lineage.md) and [independent Python model](../../../../../../tools/tests/test_polars_select_projection_model.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_select` | privacy/row-local-projection-stability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Stability reasoning](#stability-reasoning), [independent model](../../../../../../tools/tests/test_polars_select_projection_model.py) |
| `make_select` | correctness/projection-shape-options | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Guards and schemas](#guards-and-schemas) |
| `make_select` | privacy/grouping-lineage-and-bounds | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Contribution bounds](#contribution-bounds) |

## Analysis

### Stability reasoning

The constructor first stabilizes the prior plan, then stabilizes every selected expression under `Context::RowByRow` and the prior output metric. The resulting projection keeps the middle metric with an identity stability map except that it applies `retain_bounds` to discard certificates referring to modified or omitted columns. For a deterministic record-local mapping `f`, every input row produces one output row. Summing absolute count differences over all output values shows that a record projection, even when different input rows collide, cannot increase multiset symmetric distance.

The [reference model](../../../../../../tools/tests/test_polars_select_projection_model.py) checks six deterministic row-local projections over 259 ordered input datasets of length at most three; **402,486** ordered dataset-pair comparisons passed. This checks a mathematical model, **not** compiled OpenDP, every stable expression, or data-dependent errors. The end-to-end privacy claim is therefore **Partial**.

### Guards and schemas

The source rejects `exprs` if **all** have no root column names: scalar-only selection could collapse a multirow frame into one row. It accepts mixed public scalar and row-dependent expressions only after validating `valid_projection_options(options)`, which requires `duplicate_check=true` and `should_broadcast=true` (parallel execution may vary). Output `series_domains` are drawn from each stabilized expression; any identifier-output-name intersection with the original identifier expression's root names is rejected when the intermediate metric has an identifier. These are source-level checks; this audit does **not** prove the identifier-specific mapping is correct for every nontrivial alias or truncation path.

### Contribution bounds

The constructor computes `retained_columns` from expressions syntactically identical to their output-named columns. It marks every other original or output column as `changed_columns`, then passes this set to `retain_margins` and `retain_bounds`. This discards any certificate dependent on a changed column. A selector/grouping expression with multiple outputs is dropped whenever **any** column changes, to avoid relying on unknown selector expansion. Literal-only and duplicate-output projections are excluded by construction guards.

The [independent test](../../../../../../tools/tests/test_polars_select_projection_model.py) enumerated **7,232** projection/certificate scenarios using three input columns, direct identities, overwrites, renamed columns, derived columns, constants, grouping certificates, and selectors. In the model, every retained explicit-root certificate refers only to unchanged columns; selectors are retained only if no changes occur. Existing native tests explicitly check plain, casted and selector-derived grouping keys, but were inspected rather than executed in this audit.

**Result:** No certificate-retention counterexample in the finite model and source-level lineage trace. Native Polars schema, selector expansion, and identifier-metric semantics remain **Partial**.

## Next checks

- Run native Rust/Polars selection tests for nested aliases, column selectors, duplicate names, root-free expressions mixed with data columns, and public-literal broadcasting.
- Check identity/identifier logic with actual `FrameDistance<SymmetricIdDistance>`/truncation compositions, including identifier aliases.
- Review all accepted `StableExpr` branches for data-dependent errors and row-shape changes; the finite model cannot certify the optimizer.
