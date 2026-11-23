---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Polars binary-expression nullability and implicit coercions

## Invariant and threat model

A stable Polars binary expression is used in private query planning before privacy calibration. Incorrect output domain descriptors can leak through a downstream count (for example, nulls introduced by private zero denominators). Data-dependent casting exceptions can separately disclose private values by making releases fail only for some datasets.

**Reviewed scope:** The rowwise binary expression constructor, explicit operator allowlist, nullability formula, temporal comparison restrictions, Enum/String behavior, and the numeric coercion helper. This is not an evaluation of all Polars optimizer passes or all possible operands.

## Affected symbols and source audits

- [Primary source audit](../source/rust/src/transformations/make_stable_expr/expr_binary/mod.rs.md) and [pinned constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_binary/mod.rs#L1).
- [`SeriesDomain::new_from_field` nullability and membership](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/series/mod.rs#L1).
- [`is_numeric_coercion` and reviewed cast allowlist](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/cast.rs#L1).
- [`make_expr_cast` rejects unsafe casts](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_cast/mod.rs#L1).
- [Upstream binary-expression unit tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_binary/test.rs#L1).

## Reasoning and evidence

### Nulls under valid inputs

The binary constructor initializes `SeriesDomain::new_from_field`, which conservatively starts with a nullable output, then assigns the precise descriptor `left.nullable || right.nullable || matches!(op, FloorDivide | TrueDivide | Divide | Modulus)`. It overrides that descriptor to false for validity-aware equality operators. A non-nullable operand pair with a zero integer denominator is a decisive example: modulo or division can produce null despite no input null, so the four operators must stay nullable even without source nulls. The upstream regression test expressly covers this scenario.

A small executed static reference check enumerated seven arithmetic operators (`Plus`, `Minus`, `Multiply`, `Divide`, `TrueDivide`, `FloorDivide`, `Modulus`) across both input-nullable bits (28 combinations). It verified the expected policy expression and confirmed the special conservative flag for the four zero-divisor-capable operations. The check is an independent policy algebra exercise, not a Polars behavior test. The Boolean validity operations were reviewed separately from source and upstream tests.

### Data-dependent conversions and comparison failures

The constructor rejects array and categorical operands, excludes unsupported operators, compares temporal dtypes exactly, and limits temporal operators to comparisons. An Enum/String *ordering* comparison is explicitly rejected because a private string not in the Enum's category set may error during evaluation. Enum/String *equality* is supported, with an upstream regression using an unknown category and comparing both operand directions. Unknown mixed dtypes outside numeric/boolean coercion and Enum/String equality are rejected.

For supported numeric/boolean implicit coercion, `is_numeric_coercion` checks the two source datatype families; the output dtype is obtained via Polars `expr.to_field` rather than guessed. The upstream tests include Int64/UInt64 extremes, Float32/Float64 NaN and infinity, nullable operands, and dynamic literal combinations. These cases were read but not independently run.

The general property that every allowed numeric implicit promotion and integer division is total and cannot raise a data-dependent exception is **not established** by this review. A follow-up below verifies the pinned implementation of ordinary signed integer floor division and modulo under a bounded independent model, but optimized execution and mixed coercion remain to be tested before upgrading the privacy property to Audited.

### Exceptional integer division and modulo in pinned Polars

**Dependency revision.** OpenDP at `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` pins Rust Polars `0.52.0` and uses `[patch.crates-io]` at the Python tag `py-1.36.1` (commit `2a151c10fa76790711c2f75e6d012dd69c627ddd`) in its [Cargo manifest](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/Cargo.toml). We inspected the historical tagged Polars kernels, not the mutable current upstream Polars implementation.

**Tracing ordinary expression execution:** `make_expr_binary` accepts `FloorDivide` and `Modulus`, with output nullability set even for non-null source operands. [Polars `BinaryExpr` dispatch](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-expr/src/expressions/binary.rs) routes `FloorDivide` to [`floor_div_series`](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-ops/src/series/ops/floor_divide.rs), which applies `wrapping_floor_div` kernels. The signed [vector/vector, scalar-right, and scalar-left kernels](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-compute/src/arithmetic/signed.rs) mask zero denominators as null, return null for zero scalar divisors, and use wrapping negation for the `-1` scalar divisor. The common [`FloorDivMod::wrapping_floor_div_mod`](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-utils/src/floor_divmod.rs) checks zero before performing the signed `wrapping_div` and `wrapping_rem`; importantly, `MIN / -1` is wrapping, not panicking. The [unsigned kernels](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-compute/src/arithmetic/unsigned.rs) guard vector and scalar zero denominators before evaluating integer division/remainder. [Floating kernels](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-compute/src/arithmetic/float.rs) implement their divisions as floating operations, with IEEE `inf` or `NaN` behavior where applicable.

**Independent model executed:** A pure JavaScript `BigInt` simulation encoded the signed helper's truncation-plus-remainder floor correction, including `wrapping_div` and a nullable zero-denominator outcome. An independent mathematical oracle used a *sign-normalized floor formula* for an exact integer quotient, wrapped its result to the given bit width, and computed the exact remainder. Exhaustive `i8` pairs included every `(-128..=127)^2` combination (**65,536**), including all **256** zero divisors and `(-128, -1)`. **100,000** `i64` pairs included the 10×10 Cartesian boundary alphabet `{MIN,MIN+1,-17,-3,-1,0,1,2,17,MAX}` and deterministic xorshift64-generated signed inputs (seed `0x91cb1a84`). **Zero mismatches** across **165,536** comparisons. The `MIN/-1` result wraps, as the pinned source promises, and zero denominators have a null validity mask.

The model is of specified algorithm semantics, **not compiled Rust or native Polars**, and cannot by itself establish behavior of optimizations, dynamic literals, SIMD backends, other numeric conversions, or full private query execution. It resolves the narrow signed-minimum overflow hypothesis *at the pinned source/algorithm level* without establishing the broader privacy property.

### Historical fixes and coordination

- [Upstream #2940](https://github.com/opendp/opendp/issues/2940), a modulo-by-zero nullable-output privacy leak, is **fixed on main** through [merged PR #3051](https://github.com/opendp/opendp/pull/3051).
- [Upstream #3218](https://github.com/opendp/opendp/issues/3218), a cross-datetime coercion nullable-output leak, is **fixed on main** through [merged PR #3220](https://github.com/opendp/opendp/pull/3220).
- The broader previously reported [upstream #3093](https://github.com/opendp/opendp/issues/3093) concerns other query operations (`qcut` and integer `pow`), not a newly identified counterexample in this binary-expression review.

All three upstream issues were closed. The accepted explicit guards for the two relevant problems appear in the inspected upstream revision. No duplicate audit defect issue was opened.

### Verification limitations

Static source/test examination and 11 source-guard assertions were executed through the connected GitHub repository; the source-policy arithmetic table covered 28 combinations; the `BigInt` signed division/remainder model compared 165,536 integer pairs. The local runtime lacks Polars and OpenDP, so no native Rust/Polars tests were executed. Static assertions do not establish dynamic compiler-version semantics, runtime arithmetic error behavior, or privacy guarantees.

## Findings

**No new defect established within the stated scope.** The two concrete historical privacy issues are fixed on upstream `main`. Output-nullability and data-dependent-failure properties remain **Partial** until runtime and implementation-level numerical exceptional cases are checked.

## Unresolved questions

- Verify non-nullability of `EqValidity`/`NotEqValidity` and the division/remainder null contract in the exact Polars dependency version under optimized execution.
- Confirm the signed-minimum/`-1`, zero-denominator and scalar/vector arithmetic paths through compiled Polars `py-1.36.1` and optimized lazy plans; the source/model review found no failure in the examined kernels.
- Extend review to other operations that can introduce nulls or errors via implicit casts or optimizer rewrites.
