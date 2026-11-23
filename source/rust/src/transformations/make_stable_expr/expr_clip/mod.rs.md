---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_clip/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_clip/mod.rs`

## Scope and assumptions

- **Audit scope:** The non-deprecated Polars `make_expr_clip` transformation, including local helpers `extract_bound` and `extract_bounds`. Properties: constructor argument validation, public typed bounds, preservation of output domain descriptors, and row-wise mathematical nonexpansiveness. The compiled Polars optimizer and FFI are outside this review.
- **Invariants:** A successful clip has a supported numeric input column, two scalar literal bounds of the column's type, ordered and non-NaN endpoints, and output-domain closed bounds while preserving nullability and the atom domain's NaN allowance. A mathematical clamp with fixed public bounds is nonexpansive and does not change row counts or other rows. Invalid shapes and bounds should fail at construction independent of private data.
- **Assumptions:** The runtime Polars `Expr::clip` implements the mathematical clamp for admitted non-null numeric values and has no data-dependent errors; null and NaN handling may need further runtime checks. `SeriesDomain::set_element_domain` preserves the separate nullable flag. Source-level evidence does not establish compiled runtime behavior.
- **Pinned upstream:** `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. [Clip implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_clip/mod.rs), [upstream clip test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_clip/test.rs), [Bounds validation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/mod.rs), [float CheckNull](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/operations/mod.rs). Coordination: [audit task #52](https://github.com/opendp/opendp-audit/issues/52).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `transformations::make_stable_expr::expr_clip::make_expr_clip` | correctness/constructor-guards | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Constructor guards](#constructor-guards) |
| `transformations::make_stable_expr::expr_clip::extract_bound` | correctness/public-literal-bounds | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Domain and bound validation](#domain-and-bound-validation) |
| `transformations::make_stable_expr::expr_clip::extract_bounds` | correctness/output-domain-bounds | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Domain and bound validation](#domain-and-bound-validation) |
| `transformations::make_stable_expr::expr_clip::make_expr_clip` | privacy/rowwise-stability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Mathematical reference test](#mathematical-reference-test) |

## Analysis

### Constructor guards

The constructor requires an `Expr::Function` with `FunctionExpr::Clip` and both `has_min` and `has_max` set, then destructures exactly three arguments. It first constructs a stable transformation for the input expression and reads its output column dtype. It accepts `UInt32`, `UInt64`, `Int8`, `Int16`, `Int32`, `Int64`, `Float32` and `Float64`. It rejects `UInt8` and `UInt16` explicitly and all other dtypes (including categorical and strings) by default. This is intentional scope restriction rather than a demonstrated defect.

The local helper `extract_bound<T>` only accepts `Expr::Literal`, requests the literal's `AnyValue` and performs a typed extraction `try_extract::<T>()`. Neither data-derived bound expressions nor unsupported typed public literals pass these checks. Successful construction therefore does not evaluate the bounds using private data.

### Domain and bound validation

`extract_bounds<T>` extracts both values and invokes `Bounds::new_closed((lower, upper))` to construct an inclusive interval. The underlying `Bounds::new` rejects `lower > upper` and calls `CheckNull::is_null` on both endpoints. For `f32` and `f64`, `is_null` is implemented as `is_nan`, so NaN bounds are rejected, including when ordinary ordering comparisons with NaN would be unordered. Equal bounds remain valid.

The code clones the prior atom domain before setting its `bounds` field, retaining the atom's existing NaN allowance; `SeriesDomain::set_element_domain` changes that atom descriptor without resetting the independent `nullable` field. The output type and row-level null permissiveness thus remain consistent with the source descriptors. Finally, the output expression calls `expr.clip(lower.clone(), upper.clone())` on public typed bounds, and its stability map clones the input distance.

These checks establish the audited constructor and literal-bound **source control flow**. The native upstream `test_make_expr_clip` inspects the reconstructed output expression and a Float64 closed-bound output-domain descriptor, but does not exercise every boundary, verify collected Polars results against the domain, or establish that the Polars optimizer never raises data-dependent errors. Runtime output-domain preservation remains `Partial`.

### Mathematical reference test

For ordered real values and public `L <= U`, the clamp `c(x)=min(max(x,L),U)` is 1-Lipschitz: `|c(x)-c(y)| <= |x-y|`. Rowwise application is nonexpansive under appropriate event-level metrics and preserves row count, conditional on runtime equivalence to this mathematical operation and admissible null/NaN behavior. This supports, but does not completely certify, the identity stability-map construction.

[Independent standard-library Python model tests](../../../../../../../tools/tests/test_polars_clip_bound_contract_model.py) passed **4 unit tests**, including **300 deterministic integer pairs** and **300 deterministic finite binary64 pairs** checked for nonexpansiveness and idempotence. Other cases cover reversed/NaN bounds and null/NaN inputs under the reference model. They do **not** execute OpenDP or Polars and must not be used to assert Polars' handling of NaN or any private-data-dependent runtime failure.

**Disposition:** No new defect was established within the reviewed source-level guards and mathematical model. No duplicate defect issue was created.

## Next checks

- Add native OpenDP/Polars tests for nullable inputs, NaNs, signed zeros, infinities, Float32 versus Float64 literal extraction, and exact equality to each public bound; assert that the collected result inhabits the declared output `SeriesDomain`.
- Verify that an admitted pair of public bounds cannot cause data-dependent runtime failures in Polars' expression optimizer or clipping kernel.
- Independently review omitted `UInt8` and `UInt16` support if users need those dtypes.
