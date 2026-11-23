---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Polars Lp metric validation admits NaN-containing expression domains

## Invariant and threat model

OpenDP's `LpDistance<1,Q>` and `LpDistance<2,Q>` describe sums/norms of coordinatewise numeric differences. An IEEE NaN does not have an ordered, finite difference from a real value, and the vector metric-space implementation rejects NaN-permitting element domains. The same invariant must be considered when using `ExprDomain` in a private Polars noise expression. This is a **metric-space proof precondition** review, not an attempt to infer a differential-privacy violation from undefined distances.

## Sources and scoped cross-file chain

- [Polars `ExprDomain::check_space` source audit](../source/rust/src/domains/polars/expr/mod.rs.md): `LpDistance<P,Q>` checks `P∈{1,2}`, no bitmap nulls, and primitive numeric dtype, but omits the atom-domain NaN permission.
- [Polars `make_expr_noise` source audit](../source/rust/src/measurements/make_private_expr/expr_noise/mod.rs.md): validates only `nullable` before using a separate non-NaN vector noise mechanism to construct its privacy map.
- [Float `AtomDomain::default`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/mod.rs) and [`CheckNull` for floats](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/operations/mod.rs): default float atoms permit IEEE NaNs.
- [`SeriesDomain`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/series/mod.rs): non-nullability is not the same as prohibition of NaN payloads.
- [Vector `LpDistance` metric-space check](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/mod.rs): rejects atom domains where `nan()` is true.
- [`make_expr_sum`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_sum/mod.rs): rejects NaN-permitting **input** domains but describes the floating sum's **output** using `AtomDomain::<TI::Sum>::default()`.
- [Audit defect #57](https://github.com/opendp/opendp-audit/issues/57) (privacy-relevant correctness issue). The distinct invalid exponent case is [#37](https://github.com/opendp/opendp-audit/issues/37).

## Exact source-level witness

Construct a nonnullable `SeriesDomain::new("x", AtomDomain::<f64>::default())`. This is legal; the series validity bitmap is non-nullable while the atom domain allows NaN. The `ExprDomain` carrying it has primitive numeric `Float64` dtype and can be placed in any valid expression context, including `Context::RowByRow`. `MetricSpace::check_space` for `(ExprDomain, L1Distance<f64>)` therefore accepts the space because all three implemented checks pass. The same happens for `L2Distance<f64>` and `f32`.

For the analogous `VectorDomain::new(AtomDomain::<f64>::default())` under `L1Distance`, the checker examines `element_domain.nan()` and returns a metric-space error. Replacing the float atom domain in either carrier with `AtomDomain::new_non_nan()` resolves the precondition and makes both checkers accept the domain.

Minimal *upstream Rust regression to execute*, presented as source-equivalent pseudocode and **not a compiled OpenDP test**:

```rust
let atom = AtomDomain::<f64>::default();
assert!(atom.nan());
let series = SeriesDomain::new("x", atom.clone());
assert!(!series.nullable);

let expression = ExprDomain { column: series, context: Context::RowByRow };
assert!((expression, L1Distance::<f64>::default()).check_space().is_ok());
assert!((VectorDomain::new(atom), L1Distance::<f64>::default())
        .check_space().is_err());
```

The independent [Python contract-table test](../tools/tests/test_polars_expr_lp_nan_model.py) implements the pinned branches and checks 16 float `P∈{1,2}`/NaN/nullability configurations, including four mismatches for nonnullable, NaN-permitting float domains. This is a **source-semantics model**; it cannot establish an actual OpenDP Rust return value beyond the direct source-control-flow inference.

## Privacy interpretation and scope boundary

`map_function` builds the map from `VectorDomain::new(AtomDomain::<T>::new_non_nan())` and the correct underlying measure and metric. Its execution plugin selects the same per-type Laplace/Gaussian mechanism with the same scale. These paired dispatches are not the problem. Instead, the accepted `ExprDomain` may describe a larger set of values than the non-NaN vector domain for which that privacy map is justified.

This is a **confirmed precondition validation mismatch**. It does *not* follow that a NaN-valued expression is a finite-distance neighbor of a non-NaN expression, or that a valid input to a specific `make_expr_sum` can produce NaN. A valid floating sum may be constrained to non-NaN actual values despite an overbroad declared output domain. No concrete privacy loss, sampling exploit, or data-dependent failure was shown.

## Findings

**Unreported metric-space contract defect:** Polars's `ExprDomain` Lp validator omits a NaN-domain guard present for vector Lp, and the private noise expression's map uses a stricter non-NaN vector domain. Filed [issue #57](https://github.com/opendp/opendp-audit/issues/57) with `privacy` and `correctness` labels. Targeted upstream/audit issue and PR searches did not identify an equivalent defect or corrective PR. Broader privacy conclusions remain **Partial**.

**Separate bounded negative result:** Both pure-DP Laplace/L1 and zCDP Gaussian/L2 branches dispatch the **same** scale, metric, noise type, and supported dtypes in privacy-map construction and runtime plugin execution. There is no dispatch mismatch in this source review; sampler law and entropy were not independently retested.

## Unresolved questions

- Add native upstream tests of the four NaN-permission cases (f32/f64 × L1/L2), plus non-NaN controls; establish whether current Polars construction accepts the proposed witness in a real measurement.
- Reconcile a stricter `ExprDomain` check with output domain descriptors of existing stable aggregations, particularly floating-point sums. Any fix should preserve construction for provably non-NaN aggregate outputs.
- Independently audit end-to-end privacy behavior only after a valid finite-distance NaN pair or concrete reachable invalid output is established; **no such pair is claimed**.
