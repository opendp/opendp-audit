---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_binary/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_binary/mod.rs`

## Scope and assumptions

- **Audit scope:** Review `make_expr_binary` for nullable output descriptors, supported operator and implicit-cast policy, temporal comparison safety, and Enum/String comparison behavior. Analyze the ordinary rowwise `StableExpr` path, not unrelated aggregations or Polars optimizer internals.
- **Invariants:** A binary expression may not advertise a non-nullable output when a supported operator can generate null from valid non-null inputs. The constructor must reject unverified datatype coercions and data-dependent runtime failure paths.
- **Assumptions:** The Polars engine and its type inference conform to the tested semantics of the pinned OpenDP revision. Arithmetic overflows in the supported integer operations wrap as in the upstream test. This is a static audit with independent source assertions, not a compiled Rust/Polars execution.
- **Pinned sources:** [constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_binary/mod.rs#L1), [upstream regression tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_binary/test.rs#L1), [numeric coercion helper](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/cast.rs#L1), [series output domain](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/series/mod.rs#L1).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `transformations::make_stable_expr::expr_binary::make_expr_binary` | correctness/output-nullability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Nullability and validity guard reasoning](#analysis); explicit modulo/division null guards present, runtime verification remains outstanding. |
| `transformations::make_stable_expr::expr_binary::make_expr_binary` | correctness/implicit-coercion-preconditions | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Static inspection](#analysis) of numeric, temporal and Enum/String policy; other optimizer rewrites excluded from scope. |
| `transformations::make_stable_expr::expr_binary::make_expr_binary` | privacy/data-dependent-failure | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file investigation](../../../../../../investigations/stable-binary-nullability-and-coercion.md); fixes for previously demonstrated modulo and datetime leaks are present on reviewed `main`. |
| `transformations::make_stable_expr::expr_binary::make_expr_binary` | correctness/signed-integer-division-overflow | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Pinned-Polars arithmetic review](../../../../../../investigations/stable-binary-nullability-and-coercion.md#exceptional-integer-division-and-modulo-in-pinned-polars); 165,536 source-model comparisons; native runtime pending. |

## Analysis

The constructor first stabilizes the left and right subexpressions separately using a rowwise input domain. It rejects binary operations on array columns and categorical columns, restricts the operator allowlist, and asks Polars to infer the output dtype via `expr.to_field`. The output domain is created by `SeriesDomain::new_from_field` and then has its nullability updated.

**Null introduction:** The nullable flag is `left.nullable || right.nullable || is_division_or_remainder`, where the last term includes `FloorDivide`, `TrueDivide`, `Divide`, and `Modulus`. This is the key guard for zero denominators even when neither operand admits nulls. `EqValidity` and `NotEqValidity` override this and set nullable false because null-safe equality produces a boolean for each row. Other comparisons propagate source nullability. The [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_binary/test.rs#L1) include integer remainder by zero, validity comparisons with nulls, boolean three-valued operations, and integer wrapping. A 28-case independent source-policy truth table (seven arithmetic operators × four possible source-nullability combinations) reproduced the formula, with precisely the four division/remainder operators requiring nullable output when neither source is nullable. This is an algebraic policy check, **not** a Polars execution or an independent verification of its runtime null behavior.

**Coercion and errors:** When dtypes differ, the constructor permits numeric/boolean implicit coercion via `is_numeric_coercion`, and permits Enum/String equality, but otherwise rejects unmatched dtypes and requires an explicit reviewed cast. Enum/String ordering is rejected because unknown private strings can produce a data-dependent error. Temporal binary expressions require the two temporal dtypes to match exactly and require a comparison operator; cross-temporal promotions, which may overflow and become null, are rejected. Explicit casts themselves are separately constrained by the [cast constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_cast/mod.rs#L1).

**Previously repaired defects:** [upstream issue #2940](https://github.com/opendp/opendp/issues/2940) documented a genuine free-count leak from modulo-zero nulls and was fixed by [merged PR #3051](https://github.com/opendp/opendp/pull/3051). [Upstream issue #3218](https://github.com/opendp/opendp/issues/3218) documented implicit datetime conversion introducing nulls and was fixed by [merged PR #3220](https://github.com/opendp/opendp/pull/3220). Both fixes are in upstream `main` at the reviewed SHA. Neither is a novel open bug.

### Exceptional signed integer division in the pinned Polars dependency

OpenDP's [Cargo.toml](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/Cargo.toml) pins Polars Rust crates at `0.52.0` and locally patches them to the Python-compatible `py-1.36.1` source tree, whose tagged commit is `2a151c10fa76790711c2f75e6d012dd69c627ddd`. This review examined that *tagged* implementation instead of inferring behavior from current Polars.

The [Polars binary-expression dispatch](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-expr/src/expressions/binary.rs) sends `FloorDivide` to [`floor_div_series`](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-ops/src/series/ops/floor_divide.rs), which uses primitive signed/unsigned arithmetic kernels. The [signed kernels](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-compute/src/arithmetic/signed.rs) mask zero divisors as null for vector/vector division and modulo, use `wrapping_floor_div_mod` for signed pairs, special-case scalar divisors `0` as all-null and `-1` as wrapping negation, and handle scalar-left division through the same wrapping helper. The [helper](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-utils/src/floor_divmod.rs) checks zero before division and uses `wrapping_div` and `wrapping_rem`, so `i64::MIN / -1` wraps to `i64::MIN` rather than triggering Rust's checked-division panic. The [unsigned kernels](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-compute/src/arithmetic/unsigned.rs) similarly guard zero in vector and scalar paths. Floating-point [`TrueDivide` and `Divide` dispatch](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-expr/src/expressions/binary.rs) and [floating-point primitives](https://github.com/pola-rs/polars/blob/2a151c10fa76790711c2f75e6d012dd69c627ddd/crates/polars-compute/src/arithmetic/float.rs) use floating-point division rather than integer checked division for those paths.

An independently executed JavaScript `BigInt` source-semantics model compared Polars' signed wrapping-and-floor adjustment to a **separate sign-normalized mathematical floor formula**, wrapping the expected quotient to the signed bit width. It exhaustively checked all **65,536** ordered pairs of `i8` values, including all 256 zero divisors and `i8::MIN / -1`, plus **100,000** deterministic `i64` cases with boundary Cartesian pairs and a seeded xorshift generator. **Zero mismatches.** This is **not** compiled Polars/OpenDP execution; optimizer rewrites and mixed-dtype coercions were not exercised. [Detailed investigation](../../../../../../investigations/stable-binary-nullability-and-coercion.md#exceptional-integer-division-and-modulo-in-pinned-polars).

The suspected signed-minimum division panic therefore has **no supporting evidence on these examined ordinary kernels**. Data-dependent-failure coverage remains Partial because runtime and other operations were not exhaustively checked.

**Executed checks:** A source-text preflight verified 11 expected implementation/test guards, a 28-case independent nullability-policy table was evaluated, and a separate 165,536-case `BigInt` source-semantics model tested signed division/remainder; all checks passed. The upstream Rust tests were inspected only. No OpenDP or Polars runtime is installed in the local environment and no native OpenDP tests were run during this review.

**Assessment:** No new defect established in the bounded review. The guards are present and consistent with intended nullability and cast policies; end-to-end privacy/data-dependent failure behavior remains **Partial**, not proven.

## Next checks

- Execute the upstream `expr_binary` Rust integration/unit tests against the supported Polars version, including zero denominators and mixed signed/unsigned numeric dtypes.
- Extend testing to numeric-coercion boundary cases not covered by current concrete samples and to other Polars optimizer rewrites.
- Confirm the pinned-Polars source analysis by executing native `py-1.36.1` regression tests for signed minimum divided by negative one, zero divisors, scalar/vector dispatch, and mixed numeric dtype coercions.
