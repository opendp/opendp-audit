---
schema_version: 1
source: rust/src/domains/polars/expr/mod.rs
updated: 2026-11-23
---

# `rust/src/domains/polars/expr/mod.rs`

## Scope and assumptions

- **Scope:** `MetricSpace for (ExprDomain, LpDistance<P, Q>)` and its NaN-permission precondition, compared with the equivalent vector `LpDistance` metric-space check and the type/domain checks in Polars noise expressions. The separate issue of invalid exponent `P=0` is outside scope and tracked in [audit #37](https://github.com/opendp/opendp-audit/issues/37).
- **Invariant:** A space with `LpDistance<1,Q>` or `LpDistance<2,Q>` over a floating-point value domain must exclude NaNs, because coordinate-wise numeric differences are undefined for NaN values. The corresponding Rust vector metric space already enforces this condition.
- **Assumptions:** `SeriesDomain::new` preserves the `AtomDomain`'s NaN permission; `AtomDomain::<f32/f64>::default()` includes NaN because `CheckNull::NULLABLE=true`. We do not posit finite distances between NaN-containing expressions or establish a DP attack.
- **Pinned source:** [Polars ExprDomain and metric checks](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/expr/mod.rs), [float SeriesDomain](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/series/mod.rs), [AtomDomain](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/mod.rs), [vector metric-space check](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/mod.rs), [CheckNull](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/operations/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `domains::polars::expr::MetricSpace_for_ExprDomain_LpDistance::check_space` | correctness/nan-permitting-lp-domain | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Confirmed construction-precondition discrepancy](../../../../../../investigations/polars-noise-lp-nan-domain.md), [issue #57](https://github.com/opendp/opendp-audit/issues/57) |
| `domains::polars::expr::MetricSpace_for_ExprDomain_LpDistance::check_space` | privacy/metric-space-precondition | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Downstream noise-map implications](../../../../../../investigations/polars-noise-lp-nan-domain.md); no proven finite-distance NaN witness |

## Analysis

### Accepted NaN-permitting float domain

The `LpDistance<P,Q>` implementation for `ExprDomain` checks (i) `P` is 1 or 2; (ii) the `SeriesDomain.nullable` bit is false; and (iii) the type is primitive numeric. It then returns success. It **does not** check the underlying `AtomDomain::<f32/f64>::nan()` property.

These are independent properties: `SeriesDomain::new("x", AtomDomain::<f64>::default())` is non-nullable at the *Polars validity-bitmap* level but its atom domain still **permits IEEE NaN values**. The default atom domain uses `nan: T::NULLABLE`, and `f32/f64` implement `CheckNull` with `NULLABLE=true`. Consequently this expression domain passes `L1Distance<f64>` and `L2Distance<f64>` checks although the corresponding `VectorDomain::new(AtomDomain::<f64>::default())` metric-space check explicitly returns an error, "LpDistance requires non-nan elements".

This is a **confirmed validation inconsistency** rather than a constructed neighboring pair whose distributions violate a privacy inequality. See the [cross-file investigation](../../../../../../investigations/polars-noise-lp-nan-domain.md) for the minimal source-equivalent Rust witness. The [independent truth-table model](../../../../../../tools/tests/test_polars_expr_lp_nan_model.py) tests the actual documented branch conditions but does not execute OpenDP.

### Distinction from ordinary nulls

A Polars null has its own validity bitmap and is checked by `SeriesDomain.nullable`; an IEEE NaN is a non-null floating-point payload and is tracked by `AtomDomain.nan()`. The first check cannot substitute for the second. `ExprDomain::member` delegates to `SeriesDomain::member` for actual materialized values, which in turn consults the atom domain. Thus the broad domain may genuinely include expressions evaluating to NaN; it is not only a flag that can never affect membership.

### Relationship to the noise expression

`make_expr_noise` accepts a non-null numeric `middle_domain` and constructs its privacy map with a fresh, non-NaN `VectorDomain<AtomDomain<T>>`, but it retains the original `ExprDomain` for the Polars measurement. Since the expression metric-space check omits the NaN property, successful metric validation does not itself establish the precondition used by the scalar/vector noise mechanism. Float sums from `make_expr_sum` illustrate the difference: its *inputs* must be non-NaN, but its declared float output domain is built with `AtomDomain::<TI::Sum>::default()`, which permits NaN as a type-domain descriptor.

This is a source-level proof-precondition gap. We did **not** prove that a valid sum's actual output can be NaN, nor did we construct a private input pair of finite `L1`/`L2` distance producing a violated privacy bound.

## Next checks

- Add a compiled upstream test of `MetricSpace::check_space` for `f32` and `f64` expression versus vector domains, with `L1Distance` and `L2Distance` and explicit non-NaN positive controls.
- Require non-NaN element domains in the Polars `ExprDomain` Lp check or document a mathematically valid distance extension for NaN cases. Reconcile the float sum's broad output domain so ordinary non-NaN aggregations are not unnecessarily rejected.
- Run full Polars `make_expr_noise` integration tests that distinguish a valid non-NaN aggregation from a genuinely NaN-producing expression; the reported gap alone is **not** a demonstrated DP undercount.
