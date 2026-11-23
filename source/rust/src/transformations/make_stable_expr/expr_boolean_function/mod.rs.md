---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_boolean_function/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_boolean_function/mod.rs`

## Scope and assumptions

- **Scope:** Supported row-wise `BooleanFunction` predicates (`IsNull`, `IsNotNull`, `IsFinite`, `IsInfinite`, `IsNan`, `IsNotNan`) and unary `Not`. Check nullability, dtype, and inherited stability; exclude `Any` and `All` as the implementation does.
- **Invariant:** Output nullability must contain actual null results; `IsNull` and `IsNotNull` must not carry nulls. Numeric/NaN probes preserve input nulls, while `Not` preserves dtype and row-wise nullability. Attribute descriptors from prior non-boolean types must not be incorrectly retained.
- **Assumptions:** Polars implements the inspected BooleanFunction variants row-wise and respects the native test oracle. No native Polars execution was performed here.
- **Upstream:** [implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_boolean_function/mod.rs), [comprehensive native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_boolean_function/test.rs), [SeriesDomain::set_dtype](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/series/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_expr_boolean_function` | correctness/nullability | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Nullability branch trace](#nullability-branch-trace) and [cross-file investigation](../../../../../../investigations/polars-rowwise-leaf-alias-boolean.md) |
| `make_expr_boolean_function` | correctness/dtype-and-bitwise-not | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Type and descriptor handling](#type-and-descriptor-handling) |
| `make_expr_boolean_function` | privacy/rowwise-stability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Aggregation exclusions and stability](#aggregation-exclusions-and-stability) |

## Analysis

### Nullability branch trace

The operator is restricted to the seven reviewed variants. When `IsNull` or `IsNotNull` is selected, `output_domain.column.nullable = false`, matching Polars' non-null Boolean outputs even for nullable numeric inputs. For `IsFinite`, `IsInfinite`, `IsNan`, `IsNotNan` and `Not`, the input's nullable property is retained. The pinned Rust tests explicitly check nullable and non-null float/integer columns, including actual NaN versus null, and show null propagation for each numeric probe.

### Type and descriptor handling

For probes, `set_dtype(DataType::Boolean)` resets the element-domain descriptor to an unrestricted Boolean domain. For `Not`, it uses the input dtype but still calls `set_dtype`, which replaces the prior element domain and discards bounds and NaN descriptors. This is conservative for bitwise negation of signed integers (e.g. `!0 = -1`) and preserves the declared null mask. The pinned native tests exercise Boolean and signed 64-bit `Not`, including null propagation. Other combinations (e.g. unsupported dtype/operator pairs) were not executed; `Partial` status avoids claiming exhaustive runtime validity.

### Aggregation exclusions and stability

`Any` and `All` are rejected during construction as aggregation operators, as are unrecognized BooleanFunction variants. For supported operators the prior stable expression is composed with a row-wise `Function::then_expr` and identity stability map. This is sound for ordinary non-expanding row-wise predicates under event-level metrics, assuming the Polars predicate itself neither changes row alignment nor raises data-dependent errors. No runtime tests, invalid-dtype error checks or optimizer-proof work were performed; this is a **Partial** stability conclusion, not a proof of every combination.

## Next checks

Exercise compiled Rust/Polars against a dtype/operator compatibility matrix, especially `Not` for unsigned integers and invalid pairs, and compare materialized output to `ExprDomain::member`. No new verified bug within the supported, source-reviewed branches.
