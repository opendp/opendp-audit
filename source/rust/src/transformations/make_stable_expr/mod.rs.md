---
schema_version: 1
source: rust/src/transformations/make_stable_expr/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/mod.rs`

## Scope and assumptions

- **Audit scope:** Non-deprecated `make_stable_expr` entrypoint, the `StableExpr` dispatcher for row-by-row `OuterMetric` expressions, the specialized aggregation `L01InfDistance → LpDistance<P, f64>` dispatcher, the specialized quantile scorer `L01InfDistance → L0InfDistance<LInfDistance<f64>>` dispatcher, and `infer_output_dtype`. Audit the routing/metric boundary only; do **not** re-prove each child transformation's stability/privacy properties or the Polars optimizer.
- **Invariants:** Supported expression variants must be sent to their matching constructor with the original input domain and metric; unsupported operators must fail, not receive an unproven identity stability map. Aggregates must not be reclassified as row-by-row expressions; discrete quantile scores must return the different score-vector norm. Output dtype must derive from the schema of the declared input domain.
- **Assumptions:** Child constructors apply their documented domain, metric, dtype and operation preconditions; Polars' `Expr::to_field` agrees with the pinned plan optimizer, and the caller supplies correct `WildExprDomain` metadata. A valid parent route alone does not guarantee a valid native function or private release.
- **Pinned code:** [Stable expression dispatcher](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/transformations/make_stable_expr/mod.rs), [FFI wrapper](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/transformations/make_stable_expr/ffi.rs), [aggregation cast](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/transformations/make_stable_expr/expr_cast_aggregation/mod.rs), [discrete quantile scorer](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/transformations/make_stable_expr/expr_discrete_quantile_score/mod.rs), [aggregation sum](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/transformations/make_stable_expr/expr_sum/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_stable_expr` | correctness/input-space-forwarding | Audited | `a010591f55b1713c926f8e355091471634480307` | [Entrypoint and stable dispatch](#analysis) |
| `infer_output_dtype` | correctness/input-domain-schema-resolution | Partial | `a010591f55b1713c926f8e355091471634480307` | [Field inference boundary](#field-inference-boundary); native optimizer not run |
| `StableExpr<M, M> for Expr::make_stable` | privacy/row-wise-stability-dispatch | Partial | `a010591f55b1713c926f8e355091471634480307` | [Row-by-row route classification](#row-by-row-route-classification), [existing child issues](#known-child-defects-and-limits) |
| `StableExpr<L01InfDistance<MI>, LpDistance<P, f64>> for Expr::make_stable` | privacy/aggregation-metric-routing | Audited | `a010591f55b1713c926f8e355091471634480307` | [Aggregation routes](#aggregation-routes) |
| `StableExpr<L01InfDistance<MI>, L0InfDistance<LInfDistance<f64>>> for Expr::make_stable` | privacy/quantile-score-metric-routing | Audited | `a010591f55b1713c926f8e355091471634480307` | [Quantile scoring route](#quantile-scoring-route) |

## Analysis

The root `make_stable_expr` forwards `expr.make_stable(input_domain, input_metric)` without changing the domain, metric or logical expression. Its generic trait bound requires the requested `StableExpr<MI,MO>` specialization to exist, and the input and output domain-metric pairs to be valid `MetricSpace` combinations. There is no special-case path that returns an uncharged/identity transformation on unsupported input.

### Row-by-row route classification

The `StableExpr<M,M>` implementation requires `M: OuterMetric` with microdata inner metric and propagates the same `M` type. It matches `fill_nan`'s generated ternary form before the general `Expr` variant match, routing to its specialized validator. The other explicitly recognized forms are:

| Expression shape | Constructor |
| --- | --- |
| Alias | `expr_alias::make_expr_alias` |
| Binary expression | `expr_binary::make_expr_binary` |
| Boolean function | `expr_boolean_function::make_expr_boolean_function` |
| Cast | `expr_cast::make_expr_cast` |
| Clip | `expr_clip::make_expr_clip` |
| DropNans / DropNulls | `expr_drop_nan_or_null::make_expr_drop_nan_or_null` |
| FillNull | `expr_fill_null::make_expr_fill_null` |
| Filter | `expr_filter::make_expr_filter` |
| Column | `expr_col::make_expr_col` |
| Cut | `expr_cut::make_expr_cut` |
| Literal | `expr_lit::make_expr_lit` |
| ToPhysical | `expr_to_physical::make_expr_to_physical` |
| Replace / ReplaceStrict | matching `expr_replace` / `expr_replace_strict` |
| Array, Temporal, String namespace functions | matching `namespace_arr`, `namespace_dt`, `namespace_str` |

No aggregate `AggExpr::Sum`, `Count`, `NUnique`, or `Expr::Len` appears in this row-by-row specialization, and its final arm returns `MakeTransformation` with the unrecognized expression and disabled-feature message. Thus the dispatcher does not silently certify a row-by-row/identity-stable aggregate merely because its AST is unrecognized. The array namespace is currently an explicit unsupported placeholder that always errors; this is not an identity fallback.

Each named child must still be reviewed separately. The dispatcher by itself does not certify the success/error behavior or actual data-independent execution of the child expression.

### Aggregation routes

The `StableExpr<L01InfDistance<MI>, LpDistance<P,f64>>` implementation matches only `AggExpr::Count` / `AggExpr::NUnique` / `FunctionExpr::NullCount` to `expr_count`, `AggExpr::Sum` to `expr_sum`, `Expr::Len` to `expr_len`, and an aggregation cast to `expr_cast_aggregation::<MI,P>`. Each selected constructor returns a transformation with the declared aggregate `LpDistance` metric; no branch directly imports row-wise `StabilityMap::new(Clone::clone)` as its aggregate map. The sum constructor explicitly rejects nullable/NaN-permitting inputs, uses bounds and per-group length to derive an `Lp` map, and rejects integer combinations that could overflow. The count constructor handles nullable and length-invariant cases, and the aggregation cast restricts itself to integer widening. These child checks were **traced**, not independently reproven.

The `P` parameter remains generic here, and supported powers `P=1` and `P=2` are ultimately enforced by called maps/metric space. The separate global [`LpDistance<0>` validation issue #37](https://github.com/opendp/opendp-audit/issues/37) remains open; this review does not claim the abstract metric-space implementation is sound for all const generic `P`.

### Quantile scoring route

The separate `StableExpr<L01InfDistance<MI>, L0InfDistance<LInfDistance<f64>>>` implementation first checks `match_discrete_quantile_score(&self)?`. Only a recognized `DiscreteQuantileScoreShim` is passed to `make_expr_discrete_quantile_score`; any other expression returns `MakeTransformation`. The chosen output metric carries a bound on changed partitions and the maximum score-array change, not an ordinary aggregation `LpDistance`. The child establishes the score sensitivity via `score_candidates_map` and validates public candidates. The already documented shared [candidate-validation issue #45](https://github.com/opendp/opendp-audit/issues/45) is **not** a novel dispatcher bug.

### Field inference boundary

The helper builds a Polars `Schema` from the `WildExprDomain.columns` series descriptors, calls `expr.to_field(&schema)?`, and returns the dtype. A Polars schema error is propagated as an error; it does not replace an unknown field with a guessed dtype. No independent mismatched field inference or unsafe cast was observed at this glue layer. Exact native Polars dtype inference and its dynamic-literal coercion rules remain untested, so this property is `Partial`.

### Known child defects and limits

This routing review does not duplicate or declare resolved upstream issues arising inside dispatched children, including [datetime-component validation #66](https://github.com/opendp/opendp-audit/issues/66), [Boolean `Not` dtype validation #103](https://github.com/opendp/opendp-audit/issues/103), and [NaN-permitting `LpDistance` input #57](https://github.com/opendp/opendp-audit/issues/57). Prior [aggregate `len()` max_groups issue #78](https://github.com/opendp/opendp-audit/issues/78) concerns a child output descriptor, not this dispatcher's routing. FFI exposure is narrower than the generic Rust `StableExpr` trait (the FFI wrapper monomorphizes only `FrameDistance<SymmetricDistance>` and `FrameDistance<SymmetricIdDistance>`); it is a separate interface-support limitation, not evidence of wrong Rust trait dispatch.

**Executed:** At pinned upstream SHA, 22 source-text assertions matched named expression variants to intended constructor symbols, and seven further checks confirmed fill-nan priority, error fallbacks, metric specialization, schema-dependent `infer_output_dtype`, and root argument forwarding. All **29 checks passed**. **Not executed:** compiled Rust, Polars query planning, actual DP releases, or end-to-end stability inequalities. No new regression test was added for a negative result based solely on source routing.

## Findings

**No new confirmed privacy/correctness defect in this bounded dispatcher review.** Expression routing is type-specialized and fail-closed at the top level under the stated child-constructor assumptions. Broader stability remains **Partial** due to known child issues, external Polars inference, unreviewed execution paths, and non-unit neighbor distances. [Coordination task #153](https://github.com/opendp/opendp-audit/issues/153).

## Next checks

Execute native Rust/Polars tests for every recognized AST branch and representative unsupported forms, checking that both construction and execution preserve the advertised domains and metric maps. Exercise dynamic literal coercions and aggregation namespace edge cases; confirm output schema before and after optimizer rewriting. Review upstream changes since this pinned revision before treating any route as freshly audited.
