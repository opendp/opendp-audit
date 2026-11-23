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

## Analysis

The constructor first stabilizes the left and right subexpressions separately using a rowwise input domain. It rejects binary operations on array columns and categorical columns, restricts the operator allowlist, and asks Polars to infer the output dtype via `expr.to_field`. The output domain is created by `SeriesDomain::new_from_field` and then has its nullability updated.

**Null introduction:** The nullable flag is `left.nullable || right.nullable || is_division_or_remainder`, where the last term includes `FloorDivide`, `TrueDivide`, `Divide`, and `Modulus`. This is the key guard for zero denominators even when neither operand admits nulls. `EqValidity` and `NotEqValidity` override this and set nullable false because null-safe equality produces a boolean for each row. Other comparisons propagate source nullability. The [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_binary/test.rs#L1) include integer remainder by zero, validity comparisons with nulls, boolean three-valued operations, and integer wrapping. A 28-case independent source-policy truth table (seven arithmetic operators × four possible source-nullability combinations) reproduced the formula, with precisely the four division/remainder operators requiring nullable output when neither source is nullable. This is an algebraic policy check, **not** a Polars execution or an independent verification of its runtime null behavior.

**Coercion and errors:** When dtypes differ, the constructor permits numeric/boolean implicit coercion via `is_numeric_coercion`, and permits Enum/String equality, but otherwise rejects unmatched dtypes and requires an explicit reviewed cast. Enum/String ordering is rejected because unknown private strings can produce a data-dependent error. Temporal binary expressions require the two temporal dtypes to match exactly and require a comparison operator; cross-temporal promotions, which may overflow and become null, are rejected. Explicit casts themselves are separately constrained by the [cast constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_cast/mod.rs#L1).

**Previously repaired defects:** [upstream issue #2940](https://github.com/opendp/opendp/issues/2940) documented a genuine free-count leak from modulo-zero nulls and was fixed by [merged PR #3051](https://github.com/opendp/opendp/pull/3051). [Upstream issue #3218](https://github.com/opendp/opendp/issues/3218) documented implicit datetime conversion introducing nulls and was fixed by [merged PR #3220](https://github.com/opendp/opendp/pull/3220). Both fixes are in upstream `main` at the reviewed SHA. Neither is a novel open bug.

**Executed checks:** A source-text preflight verified 11 expected implementation/test guards, and a 28-case independent nullability-policy table was evaluated. The upstream Rust tests were inspected only. No OpenDP or Polars runtime is installed in the local environment and no native OpenDP tests were run during this review.

**Assessment:** No new defect established in the bounded review. The guards are present and consistent with intended nullability and cast policies; end-to-end privacy/data-dependent failure behavior remains **Partial**, not proven.

## Next checks

- Execute the upstream `expr_binary` Rust integration/unit tests against the supported Polars version, including zero denominators and mixed signed/unsigned numeric dtypes.
- Extend testing to numeric-coercion boundary cases not covered by current concrete samples and to other Polars optimizer rewrites.
- Examine exceptional numeric operations (for example signed minimum divided by negative one) in the exact linked Polars version before asserting data-independent failure under all supported arithmetic inputs.
