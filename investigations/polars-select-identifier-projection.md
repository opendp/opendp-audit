---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Audited
---

# Identifier-preserving Polars select is rejected before metric validation

## Invariant and threat model

A row-wise projection that carries the identifier column unchanged does not alter the identifier sets, the rows for shared identifiers, or their identifier-based distance. It is therefore stable at factor one under `FrameDistance<SymmetricIdDistance>` and should remain constructible when the output domain contains the identifier column. A projection that drops or replaces the identifier may no longer satisfy the same metric's space requirements and should be rejected. This is a **constructor correctness/usability** review; no data-dependent privacy bound understatement was observed.

## Affected symbols and source audits

- [`make_select` source audit](../source/rust/src/transformations/make_stable_lazyframe/select/mod.rs.md) and [pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/select/mod.rs).
- [The source scan and `make_stable_lazyframe` dispatcher](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/mod.rs), [source identity](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/source/mod.rs), and [FFI accepted metric types](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/ffi.rs).
- [Output `FrameDomain` metric-space check](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/frame/mod.rs) and [identifier metric definition](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/polars/mod.rs).
- [Comparison with `make_h_stack` source coverage](https://github.com/opendp/opendp-audit/blob/main/source/rust/src/transformations/make_stable_lazyframe/h_stack/mod.rs.md), [executed reference-model tests](../tools/tests/test_polars_select_identifier_model.py), and [audit candidate #64](https://github.com/opendp/opendp-audit/issues/64).

## Reasoning and evidence

1. The public and FFI surfaces allow `make_stable_lazyframe` with the input and output metric both `FrameDistance<SymmetricIdDistance>`. The initial `DataFrameScan` creates an identity transformation that preserves the identifier metric. `Expr::Column("ID")` is supported by the row-by-row stable-expression implementation; its output column is still named `ID`.
2. For the projection `select([col("ID"), col("x")])`, `make_select` sets `names = {"ID", "x"}` and computes `identifier.meta().root_names() = {"ID"}`. Since the sets intersect, the guard returns `MakeTransformation("identifiers (...) may not be modified")`. It checks names of **all** output columns, not names of transformed identifiers. This is a source-confirmed false rejection of an identity projection.
3. Removing `ID` avoids the first guard, but `Transformation::new` checks the output `FrameDomain` against the original metric. `FrameDomain::check_space` requires all identifier roots to exist in that output. The missing identifier then causes a rejection. Thus an unchanged identifier cannot be carried, while a missing identifier cannot be omitted, in the same-metric path.
4. The existing `is_identity` and `changed_columns` logic in `make_select` correctly distinguishes `col("ID")`/`col("ID").alias("ID")` from a computed or replaced column. The guard runs **before** this distinction. The comparable guard in `make_h_stack` is intentionally stricter, because every newly emitted column is a write to the frame: overwriting `ID` must be rejected.
5. The failure is not vacuous: consider two frames `[(ID=1,x=4),(ID=2,x=5)]` and `[(ID=2,x=5),(ID=3,x=6)]`. They have symmetric identifier distance two, and retaining the unchanged `ID` and `x` yields the identical output distance. A valid 1-stability map is available.

**Executed:** The five Python 3 standard-library tests in `tools/tests/test_polars_select_identifier_model.py` reproduced the set-intersection and output-space logic; tested unchanged, dropped, renamed and overwritten identifiers; enumerated a two-column projection model; and checked the non-vacuous identifier-distance example. These tests **model exactly the reviewed control-flow predicates**, not compiled Rust, Polars, optimizers, or FFI. No native reproduction or end-to-end privacy test was run.

## Findings

**Source-confirmed constructor rejection of a valid identifier-preserving projection.** Verification: **Candidate pending native Rust/FFI execution**, tracked as [audit issue #64](https://github.com/opendp/opendp-audit/issues/64). Upstream disposition **Unreported** following upstream/audit issue and PR searches; historical upstream PR #2318 introduces identifier metrics but is not a corrective fix. The observable impact is needless query rejection and inability to project identified microdata under the same frame metric. No privacy guarantee violation was demonstrated.

## Unresolved questions

- Compile and execute the example in Rust and the FFI, including a `ChangeOneIdDistance` input that is cast into `SymmetricIdDistance` before selection.
- Move identifier-modification validation after calculating `changed_columns`, rejecting only actual changes to identifier roots while still requiring those roots in the output metric-space check. Add tests for unchanged ID, direct alias to same name, overwrite, removal, renaming and derived IDs.
- Separately inspect selectors, complex identifier expressions and optimizer behavior; the reference model only covers direct output columns.
