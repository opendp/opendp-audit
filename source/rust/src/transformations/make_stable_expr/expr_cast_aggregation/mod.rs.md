---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_cast_aggregation/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_cast_aggregation/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated `make_cast_aggregation<MI,P>` for Polars aggregate expressions, including the `is_integer_widening_cast` guard, literal dtype extraction, cast option handling, output-domain propagation, and the identity stability map. No generic Polars row-wise cast or upstream summation-privacy proof is asserted here.
- **Invariants:** Only casts that preserve *every* source integer value may be used with unchanged `LpDistance<P,f64>` stability bounds. A strict cast must not create a private-dependent error, and an overflowing cast must not alter any valid source value. For positive `P`, exact integer widening is distance-preserving as a mathematical operation.
- **Assumptions:** The prior stable aggregation has a sound output metric and element dtype; `is_integer_widening_cast` uses the source's `integer_bounds` table; integer casting to a supertype preserves integer values (including boundaries). The model does not establish that every Polars execution, float-based metric conversion, or `P=0` instantiation satisfies these assumptions.
- **Pinned source:** [Aggregation cast](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_cast_aggregation/mod.rs), [shared integer range check](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/cast.rs), [upstream native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_cast_aggregation/test.rs), and [existing classifier audit](https://github.com/opendp/opendp-audit/blob/main/source/rust/src/transformations/make_stable_expr/cast.rs.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_cast_aggregation` | correctness/target-dtype-containment | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Construction guard](#construction-guard) |
| `make_cast_aggregation` | correctness/strict-overflow-options | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cast options](#cast-options) |
| `make_cast_aggregation` | privacy/mathematical-stability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Exact integer distances](#exact-integer-distances) |
| `make_cast_aggregation` | correctness/output-domain | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Output domain](#output-domain) |

## Analysis

### Construction guard

The constructor requires an `Expr::Cast` and public target datatype via `to_type.as_literal()`. It first stabilizes the input aggregation, then extracts the aggregation output datatype and calls `is_integer_widening_cast(from, to)`. That guard compares **exact** source/target integer range endpoints: target minimum must be at most source minimum, and target maximum at least source maximum. It rejects narrowing conversions, mixed-sign conversions with an insufficient target range, and non-integer types. Its supported range table is `UInt32`, `UInt64`, `Int8`, `Int16`, `Int32`, and `Int64`; widening from `UInt8/UInt16` is conservatively rejected because the range table does not include them. This is a utility limitation, not unsound acceptance.

Examples that pass include `UInt32→Int64`, `UInt32→UInt64`, `Int8→Int64`, and identity; `UInt64→Int64`, `Int64→UInt64`, and `Int32→UInt32` fail. All 36 pairs of the six represented types were checked against their mathematical range containment rule in the independent [model tests](https://github.com/opendp/opendp-audit/blob/main/tools/tests/test_polars_aggregate_widening_model.py).

### Cast options

When the submitted expression uses `CastOptions::Strict`, the constructor changes it to `NonStrict` before emitting the expression. It leaves `NonStrict` unchanged. Unlike the ordinary row-wise `make_expr_cast`, it also leaves `Overflowing` unchanged. **This does not establish an overflow bug in the reviewed constructor:** every accepted source integer lies in the target integer interval, so a value-preserving integer cast does not require overflow behavior. The analysis depends on Polars interpreting an overflowing cast identically to an ordinary cast when all input values are representable. Native execution under the pinned Polars version is still needed to test that assumption. There is no private-data-dependent strict-cast failure from out-of-range integer values within a valid source domain.

### Exact integer distances

The constructed `Transformation` retains `middle_metric` as both input and output metric and installs `StabilityMap::new(Clone::clone)`. For any accepted **exact** integer widening and any scalar integer operands `x,y`, the mathematical distance satisfies `|cast(x)-cast(y)| = |x-y|`. This extends pointwise to the mathematical `Lp` norm of vectors for positive integer `P`. The reference model tested source-range endpoints and small integers across every accepted pair and checked the powers of `L1`, `L2`, and `L4` distances for representative vectors; all passed.

**Limit:** These are mathematical integer equalities. The source uses `LpDistance<P,f64>` as a Rust metric, and large integer differences may not be exactly representable as `f64`; the model did not establish the rounding behavior of every `LpDistance` evaluation or `P=0`, which is separately tracked in [audit issue #37](https://github.com/opendp/opendp-audit/issues/37). Status is therefore `Partial` for full privacy/stability certification. A prior aggregation's own stability map is also assumed correct, not re-proved.

### Output domain

The code clones the prior aggregation's `ExprDomain`, then calls `column.set_dtype(to_type)`, leaving the aggregation context and metric unchanged. It does not force the output column to become nullable, but accepted integer-widening casts preserve all valid nonnull input values; a nullable prior domain remains nullable. The source model checks interval inclusion, not Polars runtime null propagation or the correctness of arbitrary upstream aggregation outputs. Status `Partial` reflects that runtime dependency.

**Executed:** Five new dependency-free Python tests of type range pairs, endpoint inclusion, mathematical integer distance, and cast-mode representability. No compiled OpenDP Rust, Polars, or FFI code was run. Existing native Rust tests were inspected and cover `len().cast(Int64)`, `len().cast(UInt64)`, and several invalid downcasts. No distinct new defect was established in this scope.

## Next checks

- Run pinned Rust/Polars tests with `UInt32→Int64`, `UInt32→UInt64`, `Int8→Int16`, and the corresponding invalid pairs, including exact endpoint data, nulls, and all `CastOptions` variants.
- Establish whether large integer-to-`f64` metric conversions produce conservative bounds or errors; this separate numerical question cannot be settled from mathematical integer equality alone.
- Keep `P=0` out of supported metric claims pending resolution of [audit issue #37](https://github.com/opendp/opendp-audit/issues/37).
- **Disposition:** No new candidate defect issue was filed for this constructor; the reviewed integer-range rule did not admit an invalid pair. Coordination task [#80](https://github.com/opendp/opendp-audit/issues/80).
