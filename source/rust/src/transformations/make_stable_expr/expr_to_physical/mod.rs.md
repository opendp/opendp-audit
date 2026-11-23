---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_to_physical/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_to_physical/mod.rs`

## Scope and assumptions

Review the non-deprecated `make_expr_to_physical` constructor at upstream `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`, checking output physical dtype, row-wise stability, category-code mapping, and nullable/negative temporal values. The invariant is that a source element's physical representation does not depend on other private rows, and the declared output domain contains every possible physical value.

The constructor relies on Polars' `DataType::to_physical()` and `Expr::to_physical()` semantics, the stability of its recursively constructed input expression, and the fixed public metadata of any `Enum` dtype. These assumptions are checked in part using a separate pinned Polars executor regression, **not** a compiled OpenDP constructor.

- [Pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_to_physical/mod.rs)
- [Native Rust tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_to_physical/test.rs)
- [SeriesDomain conversions](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/series/mod.rs)

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_expr_to_physical` | correctness/physical-dtype | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Type dispatch](#type-dispatch), [pinned Polars regression](../../../../../../tools/integration/polars_to_physical_runtime.py) |
| `make_expr_to_physical` | privacy/category-coding-stability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Category code stability](#category-code-stability), [investigation](../../../../../../investigations/polars-to-physical-domain-and-stability.md) |
| `make_expr_to_physical` | correctness/temporal-nullability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Signed temporal and nullability checks](#signed-temporal-and-nullability-checks) |

## Analysis

### Type dispatch

The constructor accepts precisely one input for `FunctionExpr::ToPhysical`; it first stabilizes that expression. When the physical dtype equals the source dtype, it retains the original element-domain descriptors. It accepts fixed `Enum` to `UInt8`, `UInt16` or `UInt32` according to Polars' inferred physical width; `Date` to `Int32`; and `Datetime`, `Time`, `Duration` to `Int64`. Other type-changing pairs are rejected at construction. Every accepted case constructs a row-wise `to_physical` expression with an identity stability map.

### Category code stability

`Categorical` is explicitly rejected because category codes can depend on the observed private values. `Enum` uses a predetermined category mapping and `SeriesDomain::set_dtype` resets its element domain to the corresponding unsigned integer domain. These guards address historical privacy-impacting [upstream issue #2944](https://github.com/opendp/opendp/issues/2944), fixed by merged [PR #3081](https://github.com/opendp/opendp/pull/3081). The source and [native test fixtures](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_to_physical/test.rs) cover Enum widths 8/16/32 and rejected Categorical.

### Signed temporal and nullability checks

`Date` is represented as signed `Int32` days since 1970-01-01; negative pre-epoch dates therefore remain in the declared output domain. The original wrong unsigned domain was [upstream issue #2937](https://github.com/opendp/opendp/issues/2937), fixed by merged [PR #3052](https://github.com/opendp/opendp/pull/3052). The other supported temporal conversions output signed `Int64`. `set_dtype` and `set_element_domain` change only `SeriesDomain.element_domain`, retaining the independent `nullable` mask; already-physical dtype identities retain existing bounds/NaN descriptors.

**Evidence boundary:** This is source-level constructor review plus a separate [Polars-only integration regression](../../../../../../tools/integration/polars_to_physical_runtime.py). Native OpenDP/Polars construction, full `ExprDomain::member` tests, and privacy-neighbor distributions were not independently executed. No new defect identified within the reviewed branches.

## Next checks

Compile the pinned OpenDP Rust tests and assert that the returned `ExprDomain` accepts actual nullable/pre-epoch Date and Enum outputs, including optimizer rewrites.
