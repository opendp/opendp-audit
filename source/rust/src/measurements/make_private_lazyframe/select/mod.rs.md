---
schema_version: 1
source: rust/src/measurements/make_private_lazyframe/select/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/make_private_lazyframe/select/mod.rs`

## Scope and assumptions

- **Audit scope:** Non-deprecated internal `make_private_select`, specifically the global-group distance map `(l0, l1, l∞)`, private-expression composition and function/map linkage, the projection-options gate, and empty-expression rejection. Read `make_composition`, `Bounds::get_bound`, the public LazyFrame dispatch, and upstream native select tests to trace dependencies. The full privacy proofs for each `PrivateExpr` mechanism and all Polars optimizer paths are outside scope.
- **Invariant:** An aggregate select has at most one output group. Its `L0PInfDistance` map must bound the number of affected groups, total contribution count, and maximum per-group changes. All private selected expressions must be charged by privacy-map composition, with no silent zero-release case or invalid Polars projection options.
- **Assumptions:** `Bounds` correctly represent neighboring-frame row contributions; the `t_prior` stability map is sound; each `PrivateExpr` constructor implements its stated privacy map and emits a legal scalar aggregation expression; `CompositionMeasure::compose` is conservative; and Polars respects its standard `Select` expression/output rules.
- **Pinned sources:** [`make_private_select`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/select/mod.rs), [dispatcher](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/mod.rs), [`Bounds::get_bound`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/polars/mod.rs), [`make_composition`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/non_adaptive/mod.rs), [upstream native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/select/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_private_select` | privacy/select-aggregate-composition | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Global-group map and composition trace](#global-group-map-and-expression-composition); [finite source model](../../../../../../tools/tests/test_private_select_group_model.py) |
| `make_private_select` | correctness/projection-options | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Projection preconditions](#projection-options-and-empty-aggregate-guard) |
| `make_private_select` | correctness/empty-aggregate-rejection | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Composition precondition](#projection-options-and-empty-aggregate-guard) |

## Analysis

### Global-group map and expression composition

**Source trace:** The public `PrivateDslPlan` dispatcher routes a `DslPlan::Select` to `make_private_select` when the contributed `contrib` feature is enabled. The constructor first validates projection options, then stabilizes the input plan as `t_prior`. It obtains the empty-key `Margin`, wraps the resulting frame as a `WildExprDomain` in `Context::Aggregation`, and converts the frame metric to an `L0PInfDistance` using a `Transformation` with the identity `Function`.

Its map obtains `l1 = d_in.get_bound(empty).per_group`; if that is absent it returns `FailedMap`. Otherwise it returns **`(1, l1, l1)`**. Because there is only one aggregate group, even when the data are reordered or one record changes, at most one group output differs. The maximum total and within-group row contributions are bounded by the same global row bound. Returning `l0=1` even at zero input distance is conservative, if sometimes loose.

Each selected expression is separately constructed with the same aggregation domain, `L0PInfDistance` metric, output measure, and global scale. `make_composition(m_exprs)` requires compatible domains, metrics, and output measures and **composes every constituent privacy map**. The result is chained after `t_group_by` and its `privacy_map` cloned into `m_select`. On invocation, `m_select` constructs a `DslPlan::Select` using the rewritten private expressions emitted by the composed function, with its original validated projection options. Finally `t_prior >> m_select` composes the earlier plan's stability map with the select measurement. No second private invocation or drop of an expression map is visible in this source path.

**Executed reference model:** The committed [standard-library Python test](../../../../../../tools/tests/test_private_select_group_model.py) checks 14,641 exhaustive ordered pairs of small multisets (0–4 rows, 3 values) and 10,000 seeded randomized pairs. It independently computes symmetric row differences, verifies the one-group `(1, l1, l1)` bound, and checks an abstract additive composition of synthetic nonnegative privacy maps. All cases passed. **This is an algebraic source model, not compiled OpenDP Rust, not a proof for arbitrary child mechanisms, and not a Polars runtime test.**

**Status: Partial.** The constructor's wiring is consistent with the intended property under the named assumptions, but every child `PrivateExpr` mechanism, composition-measure implementation, Polars evaluation of broadcasts, and any data-dependent execution errors remain outside the review. No privacy-underestimate counterexample was found within the modeled property.

### Projection options and empty aggregate guard

**Projection gate:** Before stabilizing or constructing private expressions, `make_private_select` checks `valid_projection_options(options)`; this permits arbitrary `run_parallel` but requires both `duplicate_check=true` and `should_broadcast=true`. Unsupported options produce `MakeMeasurement`. The upstream Rust test `test_private_select_rejects_noncanonical_projection_options` covers `should_broadcast=false`; this test was **inspected, not executed** in this review.

**Empty selection:** With zero expressions, `m_exprs` is empty, but `make_composition` directly rejects an empty vector with `MakeMeasurement` before indexing `measurements[0]`. Thus an empty private-select expression set cannot construct a bogus zero-cost measurement through the reviewed path. `make_composition` also verifies domain, metric, and measure compatibility for nonempty children before creating a composite.

**Executed model:** The same reference tests check all eight Boolean combinations of the three projection options, empty-composition failure, missing global `per_group` failure, and compatible nonempty composition; no discrepancy found.

## Findings and limitations

**No defect found for these scoped source-level invariants.** An arbitrary row-valued select, child-mechanism privacy proof, the precise Polars optimizer behavior, and the separate `make_private_lazyframe/postprocess` selection/renaming path were **not** certified. [Audit task #82](https://github.com/opendp/opendp-audit/issues/82) tracks this bounded review. Targeted searches of audit/upstream issues and PRs found no equivalent open defect or overlapping active claim; no candidate issue is warranted.

## Next checks

Run native OpenDP integration with multiple distinct private select expressions and zero/one input rows; verify `m_select.privacy_map` against independently computed composed child privacy maps, particularly at zero input distance. Test projection-options rejection in both `run_parallel` modes and ensure Polars optimizer rewrites do not duplicate or share random noise releases. The separate private LazyFrame CSE audit already traces common-subexpression-elimination protections.
