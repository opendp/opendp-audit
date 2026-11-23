---
schema_version: 1
source: rust/src/measurements/make_private_expr/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/make_private_expr/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated `make_private_expr` entrypoint and `PrivateExpr` implementations for concrete and approximate output measures; routing of all nine explicit DP query shims, the noise/noisy-max/index-candidates matchers, private alias/binary postprocessing, and public `Len`/`Literal` fallback. Separately, the **unit-distance only** `approximate_c_stability` probe. No attempt to re-prove child mechanisms, FFI bootstrap, or query optimizer.
- **Invariants:** Private expressions must not bypass a mechanism constructor/its privacy accounting. Constructor arguments and public scale parameters must be passed through consistently. The approximate-measure wrapper must retain the inner privacy loss. Unit-stability probing must reject a row-by-row context and use contribution bounds consistent with the public lengths invariant.
- **Assumptions:** Downstream constructors and their `PrivacyMap` satisfy their own stated preconditions; the query satisfies the documented `honest-but-curious` requirement of at most one execution. `Margin` metadata correctly describes the allowed input multiverse, and a valid `L01InfDistance` transformation's stability map is conservative at the queried input distance.
- **Source links:** [dispatcher](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/make_private_expr/mod.rs), [approximate cast](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/combinators/measure_cast/approximate/mod.rs), [margin contribution bounds](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/domains/polars/frame/mod.rs), [dispatcher tests](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/make_private_expr/test.rs), and [coordination task #149](https://github.com/opendp/opendp-audit/issues/149).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_private_expr` | privacy/delegation-no-bypass | Audited | `a010591f55b1713c926f8e355091471634480307` | [Dispatch source trace](#dispatcher-mechanism-routing): delegates directly to `Expr::make_private`; no separate uncharged fallback |
| `PrivateExpr<L01InfDistance<MI>, MO> for Expr::make_private` | privacy/plugin-routing-coverage | Partial | `a010591f55b1713c926f8e355091471634480307` | [Dispatch source trace](#dispatcher-mechanism-routing); nine shim/arity routes and additional branches checked, but child mechanisms and Polars runtime not re-proven |
| `PrivateExpr<L01InfDistance<MI>, Approximate<MO>> for Expr::make_private` | privacy/approximate-map-preservation | Audited | `a010591f55b1713c926f8e355091471634480307` | [Approximate measure conversion](#approximate-measure-conversion) |
| `approximate_c_stability` | privacy/unit-neighbor-stability-probe | Partial | `a010591f55b1713c926f8e355091471634480307` | [Unit-neighbor c-stability probe](#unit-neighbor-c-stability-probe); caller must not extrapolate result to arbitrary distances |

## Analysis

### Dispatcher mechanism routing

`make_private_expr` itself calls `expr.make_private(input_domain, input_metric, output_measure, global_scale)`; it has no branch returning an uncharged measurement. The concrete `PrivateExpr` implementation recognizes these plugin shims using `match_shim::<Plugin,N>` and forwards every recognized one to the dedicated constructor with **the original** domain, metric, output measure, expression and `global_scale`:

| Shim | Arity | Destination |
| --- | ---: | --- |
| `DPFrameLenShim` | 2 | `expr_dp_frame_len::make_expr_dp_frame_len` |
| `DPLenShim` | 3 | `expr_dp_counting_query::make_expr_dp_len` |
| `DPCountShim` | 3 | `expr_dp_counting_query::make_expr_dp_count` |
| `DPNullCountShim` | 3 | `expr_dp_counting_query::make_expr_dp_null_count` |
| `DPNUniqueShim` | 3 | `expr_dp_counting_query::make_expr_dp_n_unique` |
| `DPSumShim` | 4 | `expr_dp_sum::make_expr_dp_sum` |
| `DPMedianShim` | 3 | `expr_dp_median::make_expr_dp_median` |
| `DPQuantileShim` | 4 | `expr_dp_quantile::make_expr_dp_quantile` |
| `DPMeanShim` | 4 | `expr_dp_mean::make_expr_dp_mean` |

Additional matchers dispatch noise to `expr_noise::make_expr_noise`, noisy max to `expr_noisy_max::make_expr_noisy_max`, candidate indexing to `expr_index_candidates::make_expr_index_candidates`, and alias/binary composition through `expr_postprocess::match_postprocess`. The noise and noisy-max constructors derive noise scale or use the explicitly supplied scale and retain their respective mechanism privacy maps; candidate indexing chains a deterministic postprocessor to an already-private measurement; alias/binary composition charges the operands. These are **dependencies**, not new standalone proofs.

The only fallback branches are exact `Expr::Len`, routed to the [public-length guarded constructor](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/make_private_expr/expr_len/mod.rs), and `Expr::Literal(_)`, routed to the data-independent constant measurement. Other expression forms return `MakeMeasurement` errors. In particular, unsupported expressions do not fall through to a zero privacy-cost measurement.

**Executed:** Source-text preflight checking all **nine** explicit plugin names, arities and constructor destinations and the eleven additional routing/helper symbols; all checks passed at pinned SHA. **Not executed:** Native Rust/Polars compilation or expression evaluation. The previous scoped [postprocessing source audit](../make_private_expr/expr_postprocess/mod.rs.md) and [public-length source audit](../make_private_expr/expr_len/mod.rs.md) cover child-specific properties. Consequently the dispatcher glue is reviewed, but whole-query privacy remains `Partial`.

### Approximate measure conversion

The specialization for `Approximate<MO>` invokes the same `Expr::make_private` on the **inner** measure and then calls `make_approximate`. The latter clones the original `privacy_map`, retains the same input function and metric through `with_map`, and maps each successful inner `d_out` to the pair `(d_out, 0.0)`. It therefore does **not** silently zero epsilon/rho or invent a nonzero delta. This conclusion is conditional on the inner measurement's validity. The source formula is sufficient for the local map-preservation property; no native execution was performed.

### Unit-neighbor c-stability probe

`approximate_c_stability` refuses a `Context::RowByRow` input with `MakeTransformation`. Under an aggregation margin it chooses the input `l1` distance `d_in=2` if `margin.invariant == Some(Invariant::Lengths)`, because a fixed-length neighbor is one substitution rather than one addition/deletion; otherwise it chooses `d_in=1`. It asks `trans.map(&(margin.l_0(d_in), d_in, margin.l_inf(d_in)))`, where `Margin::l_0(l1)=min(max_groups.unwrap_or(l1),l1)` and `Margin::l_inf(l1)=min(max_length.unwrap_or(l1),l1)`. Both components are nonnegative and at most `d_in`, and obey finite public caps.

**Executed:** A source-equivalent finite JS model enumerated 891 triples of queried `l1 ∈ [0,10]` and optional `max_groups,max_length∈{None,0,1,2,3,4,5,10,999}`. All generated `l0` and `linf` obeyed `0 ≤ l0,linf ≤ l1`; there was no arithmetic or type discrepancy in the inspected Rust branch. Upstream Rust unit tests have separate positive assertions for unbounded (`c=2`) and bounded (`c=3`) sums; inspected, **not run**.

**Limitation:** The helper explicitly **approximates c at the unit neighbor distance**, not a global Lipschitz bound valid for arbitrary `d_in`. A mechanism that consumes this result must still charge via its full stability and privacy maps. Validity also relies on the margin/invariant semantics in the caller; this review did not verify every Polars aggregation or every `StableExpr` implementation. No new concrete DP leak was established in the dispatcher.

## Findings

**No new confirmed defect in this bounded scope** at upstream `a010591f55b1713c926f8e355091471634480307`. The dispatchers do not bypass child measurement constructors, the approximate specialization retains the inner privacy map with `delta=0`, and the unit-neighbor c probe uses the intended public length invariant and contribution caps. **Overall privacy coverage remains Partial**, because individual child mechanisms, full native Polars query execution and assumptions about multiverse margins are outside this audit.

## Next checks

Run compiled OpenDP/Polars tests for each shim and for nested alias/binary operations under `Approximate<MaxDivergence>` and `Approximate<ZeroConcentratedDivergence>`; confirm the actual callback and native query optimizer path. Independently verify mechanism privacy maps for all non-unit `d_in` values before using a unit c probe as a calibration default. Check for overlapping upstream refactors after the pinned main revision changes.
