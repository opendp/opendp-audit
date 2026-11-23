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
| `make_expr_boolean_function` | correctness/not-dtype-precondition | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Public Float64 Not is accepted by OpenDP but rejected by pinned Polars](#not-dtype-precondition-mismatch); [candidate #103](https://github.com/opendp/opendp-audit/issues/103) |
| `make_expr_boolean_function` | privacy/rowwise-stability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Aggregation exclusions and stability](#aggregation-exclusions-and-stability) |

## Analysis

### Nullability branch trace

The operator is restricted to the seven reviewed variants. When `IsNull` or `IsNotNull` is selected, `output_domain.column.nullable = false`, matching Polars' non-null Boolean outputs even for nullable numeric inputs. For `IsFinite`, `IsInfinite`, `IsNan`, `IsNotNan` and `Not`, the input's nullable property is retained. The pinned Rust tests explicitly check nullable and non-null float/integer columns, including actual NaN versus null, and show null propagation for each numeric probe.

### Type and descriptor handling

For probes, `set_dtype(DataType::Boolean)` resets the element-domain descriptor to an unrestricted Boolean domain. For `Not`, it uses the input dtype but still calls `set_dtype`, which replaces the prior element domain and discards bounds and NaN descriptors. This is conservative for bitwise negation of signed integers (e.g. `!0 = -1`) and preserves the declared null mask. The pinned native tests exercise Boolean and signed 64-bit `Not`, including null propagation. Other combinations (e.g. unsupported dtype/operator pairs) were not executed; `Partial` status avoids claiming exhaustive runtime validity.

### Not dtype precondition mismatch

**Distinct, low-severity finding:** The allowlist includes `Not`, but the constructor checks neither the input's public dtype nor Polars output-schema inference before returning a `Transformation`. A `SeriesDomain::new("x", AtomDomain::<f64>::default())` and `col("x").not()` therefore pass the local BooleanFunction construction checks; the `select` traversal likewise builds expression transformations without a `to_field` check. The returned `ExprDomain` retains `Float64` and the identity stability map.

At [pinned Polars commit `2a151c10fa76790711c2f75e6d012dd69c627ddd`](https://github.com/pola-rs/polars/tree/2a151c10fa76790711c2f75e6d012dd69c627ddd), [`IRBooleanFunction::Not::get_field`](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-plan/src/plans/aexpr/function_expr/boolean.rs) accepts only Boolean and integer datatypes, and [`negate_bitwise`](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-ops/src/series/ops/not.rs) imposes the same restriction. Float32, Float64, and String are rejected with an `InvalidOperation` error. [Pinned-Polars integration script](https://github.com/opendp/opendp-audit/blob/main/tools/integration/polars_boolean_not_dtype.py) **ran successfully** in [CI #45111889610](https://github.com/opendp/opendp-audit/actions/runs/45111889610): three unsupported dtypes failed as expected; nullable Int64 and Boolean succeeded with the expected row results. The scripted execution is **Polars only**; compiled OpenDP construction/execution has not been tested.

Because the failure is determined by *public dtype*, this is a constructor/availability mismatch, **not a demonstrated privacy violation**. Existing tests cover supported Boolean and signed-integer `Not`, but not unsupported dtype admission. Track in [candidate defect #103](https://github.com/opendp/opendp-audit/issues/103); no matching upstream issue or corrective PR was found.

### Aggregation exclusions and stability

`Any` and `All` are rejected during construction as aggregation operators, as are unrecognized BooleanFunction variants. For supported operators the prior stable expression is composed with a row-wise `Function::then_expr` and identity stability map. This is sound for ordinary non-expanding row-wise predicates under event-level metrics, assuming the Polars predicate itself neither changes row alignment nor raises data-dependent errors. No runtime tests, invalid-dtype error checks or optimizer-proof work were performed; this is a **Partial** stability conclusion, not a proof of every combination.

## Next checks

Exercise compiled Rust/Polars against a dtype/operator compatibility matrix, especially `Not` for unsigned integers and invalid pairs, and compare materialized output to `ExprDomain::member`. The new dtype-precondition mismatch is documented in [issue #103](https://github.com/opendp/opendp-audit/issues/103); its end-to-end OpenDP reproduction is still outstanding.
