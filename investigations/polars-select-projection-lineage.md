---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Polars select: record-local stability and grouping-certificate lineage

## Invariant, threat model, and sources

The non-deprecated `make_select` transformation certifies row-dependent Polars projections. Any successful row-local, row-count-preserving projection must be non-expansive for record multiset symmetric distance. A grouping margin or per-group contribution bound from the input may remain valid at the output only if every input column on which that certificate depends is unchanged, or a separately justified lineage rule applies. Incorrectly retaining a certificate after an expression overwrites or drops a grouping key could reduce noise calibration and cause a privacy-bound undercount.

- [Select constructor report](../source/rust/src/transformations/make_stable_lazyframe/select/mod.rs.md) and [pinned Rust source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/select/mod.rs).
- [Lineage helper report](../source/rust/src/transformations/make_stable_lazyframe/mod.rs.md) and [pinned helper source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/mod.rs).
- [ProjectionOptions guard](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/options.rs) and [native upstream unit tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/select/test.rs).
- [Reproducible standard-library Python model](../tools/tests/test_polars_select_projection_model.py). This runs independently of Rust/Polars; upstream Rust tests were inspected but not executed.

## Source reasoning

**Rowwise stability:** The constructor first stabilizes its prior `DslPlan`, then calls `make_stable` on every select expression with `Context::RowByRow`. It rejects a projection where **all** expressions have no root columns, to avoid Polars collapsing to one row. It calls `valid_projection_options`, accepting only options with duplicate output checks and scalar broadcasting enabled; these make it possible for mixed scalar/rowwise expressions to preserve record count. For a deterministic per-record map `f`, the count of output value `v` is the sum of input counts over `f^{-1}(v)`; the triangle inequality proves multiset-symmetric non-expansion. This requires `StableExpr` and the Polars optimizer to satisfy their independent contracts.

**Certificate lineage:** The constructor marks an output column as retained only when the full projection expression is a direct identity to that same output name, allowing trivial `Expr::Alias` wrappers. `changed_columns` includes every original or output name not retained. `unaffected` rejects certificates whose `root_names()` intersect changed columns. If some columns changed, any grouping expression with `has_multiple_outputs()` is discarded even if its explicit roots appear disjoint, because selector expansion could hide schema dependencies. `retain_margins` and `retain_bounds` filter existing metadata without modifying values.

**Identifier behavior:** `make_select` additionally rejects an output-name overlap with the root names of an identifier expression, *if* the intermediate metric carries an identifier. This review did not compile all `SymmetricIdDistance` and `ChangeOneIdDistance` combinations, so it does **not** certify the guard's completeness against renaming or higher-order identifier expressions.

## Executed finite reference tests

Executed locally: `python -m unittest -v /tmp/test_polars_select_projection_model.py`; four Python tests passed after correcting an *incorrect expected case count in the model itself* (not a Rust counterexample).

1. All ordered datasets of length zero through three over six two-column record values (`1+6+36+216=259` datasets), for six projections (drop, duplicate, derive, retain, broadcast) yielded **6 × 259² = 402,486** ordered-pair non-expansion checks; all passed.
2. Exhaustive small projection/certificate model over direct identities, overwritten columns, renamed columns, derived columns, literal additions, explicit-root certificates and selectors: **7,232** certificate scenarios tested, with no invalid retention under the modeled dependency contract.
3. Explicit witnesses show that dropping, overwriting or renaming a grouping column prevents its certificate from surviving; retaining that column unchanged permits it to survive.
4. Checks the source's literal-only-rejection and projection-options conditions.

**Boundary:** This model does not execute Rust, Polars, or actual `Expr::meta()` implementations. It cannot certify the full privacy theorem, nonstandard selector behavior, native numeric coercions, data-dependent errors, or the input/output metric's identifier semantics.

## Findings and disposition

No new defect in the finite model or scoped source branch. A conservative loss of metadata is acceptable: it can deny a query but cannot understate sensitivity from a *retained* certificate. Searches for related upstream selection/identifier issues and fixing PRs found no matching defect in this limited scope, and no candidate bug was confirmed. No separate defect issue was filed; [audit task #61](https://github.com/opendp/opendp-audit/issues/61) tracks work and remaining obligations.

Overall privacy coverage **Partial**.

## Next checks

- Run the pinned upstream `make_select` Rust/Polars integration tests, including nested aliases, selector expansion, noncanonical `ProjectionOptions`, and literal broadcasting.
- Investigate identifier-dependent metric paths under native `SymmetricIdDistance` and `ChangeOneIdDistance`, including identifiers wrapped by aliases/casts; do not infer soundness from output-name guards alone.
- Check Polars optimizer rewrites, special literal functions and data-dependent exceptions against row-by-row `StableExpr` contracts.
