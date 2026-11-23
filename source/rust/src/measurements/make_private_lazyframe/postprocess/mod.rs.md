---
schema_version: 1
source: rust/src/measurements/make_private_lazyframe/postprocess/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/make_private_lazyframe/postprocess/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated `match_postprocess`, the Select/HStack column-only gate and `validated_projection_options`; postprocessing of an existing private LazyFrame.
- **Invariant:** Renaming/selecting released columns may preserve the child's privacy map, but arbitrary raw-data expressions and noncanonical projection options must not silently enter this postprocessing path.
- **Assumptions:** Polars `is_column_selection(true)` correctly classifies column references/renames and the resulting postprocessor runs on the child plan **after** private rewriting. The Polars optimizer and native runtime were not executed.
- **Pinned code:** [LazyFrame postprocessing](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/postprocess/mod.rs), [option matcher](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/options.rs), [postprocessor chain](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/mod.rs), [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/postprocess/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::make_private_lazyframe::postprocess::match_postprocess` | privacy/private-plan-only-projection | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file investigation](../../../../../../investigations/polars-private-postprocess-composition.md) |
| `measurements::make_private_lazyframe::postprocess::validated_projection_options` | correctness/mandatory-shape-options | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Option validation](#source-analysis) |

## Source analysis

The matcher accepts only `DslPlan::Select` and `DslPlan::HStack` with **all** expressions passing `meta().is_column_selection(true)`. It recursively builds a private child `m_in`, then creates a projection whose input is the **rewritten private** plan returned by that child. `m_in >> post` uses `make_chain_pm` and preserves `m_in.privacy_map`; it does not charge a new release or directly re-expose columns of the raw input.

The shared `valid_projection_options` matcher requires `duplicate_check=true` and `should_broadcast=true`, leaving only `run_parallel` unconstrained. The [model test](../../../../../../tools/tests/test_polars_private_postprocess_model.py) checks all eight Boolean options and accepts exactly two. Upstream Rust tests cover a valid selection/rename, an unsupported `head(None)` expression, and rejection of disabled duplicate checking; they were read, **not executed**.

No defect was found in this source-level option gate or ordinary renamed-column projection. The privacy claim is `Partial` because the full semantics of Polars column selectors, wildcards and optimizer rewrites were not tested, and the result relies on the child's private-plan contract.

## Next checks

- Test nested selector/alias expansion and optimization of private plan outputs in compiled Polars.
- Verify that any future new projection options remain explicitly reviewed rather than silently enabled.
