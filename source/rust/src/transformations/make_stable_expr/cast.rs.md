---
schema_version: 1
source: rust/src/transformations/make_stable_expr/cast.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/cast.rs`

## Scope and assumptions

- **Scope:** The current Polars private-cast admissibility classifier, numeric-pair restrictions, null-preserving classifier, and integer interval containment. The caller is `expr_cast::make_expr_cast`; accepted Polars runtime cast implementations are a dependency not compiled or rerun here.
- **Invariants:** Only reviewed dtype pairs can be certified for private data. Allowlisting must exclude private-data-dependent failures, physical categorical codes, unsupported temporal conversions, and nested casts. A successful classifier must conservatively set `may_introduce_null`; a non-null-preserving cast must never be reported as null-preserving. Integer widening is permitted only when the target integer range contains the source range.
- **Assumptions:** Polars `CastOptions::NonStrict` maps invalid ordinary numeric and string conversions to null and does not raise a private-data-dependent exception for the allowed pairs. Public fixed Enum category mapping is stable. These are external behavioral contracts and were not independently proven.
- **Upstream source:** [`cast.rs` at `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/cast.rs), [caller](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_cast/mod.rs), [merged hardening PR #3220](https://github.com/opendp/opendp/pull/3220), and [audit #69](https://github.com/opendp/opendp-audit/issues/69).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `transformations::make_stable_expr::cast::check_private_cast` | correctness/dtype-allowlist | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Allowlist boundary](#allowlist-boundary) |
| `transformations::make_stable_expr::cast::check_private_cast` | privacy/data-independent-errors | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Remaining runtime dependency](#remaining-runtime-dependency) |
| `transformations::make_stable_expr::cast::is_numeric_coercion` | correctness/numeric-pair-classification | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Allowlist boundary](#allowlist-boundary) |
| `transformations::make_stable_expr::cast::is_integer_widening_cast` | correctness/integer-range-containment | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Nullability and widening](#nullability-and-widening) |
| `transformations::make_stable_expr::cast::is_null_preserving_cast` | correctness/nonnullable-preservation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Nullability and widening](#nullability-and-widening) |
| `transformations::make_stable_expr::cast::integer_bounds` | correctness/integer-range-table | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Nullability and widening](#nullability-and-widening) |

## Analysis

### Allowlist boundary

The shared `check_private_cast` returns a `Fallible<bool>`, where `true` means a nonnull source value **may** become null. The classifier permits an identity cast only for explicitly supported scalar, temporal, and categorical/Enum types; it rejects identity for Null, Binary, List, Array, and Struct. For distinct dtypes, it permits the following narrowly specified families:

- Numeric/Boolean to numeric/Boolean, using `is_numeric_coercion`;
- primitive numeric or Boolean to String, and String to primitive numeric;
- Categorical to String or fixed Enum; Enum to String; and String to fixed Enum.

All other pairs return a construction error. Notably, **Categorical to integer** is rejected because the physical code may depend on private record order. Numeric to Categorical, physical integer to Date/Time/Datetime, and cross-temporal conversions are not certified. The source makes these restrictions explicit rather than assuming Polars non-strict mode is universally infallible.

The classifier is used by both the cast constructor and neighboring stable-expression code. [Merged PR #3220](https://github.com/opendp/opendp/pull/3220), dated November 18, 2026, introduced this allowlist and the corresponding Rust matrix tests. The reviewed tests exercise all numeric/Boolean pairs, String conversions, rejection of nested identity casts, cross-temporal rejection, and unsafe categorical conversions. These are **inspected upstream tests**, not tests compiled in this audit session.

### Nullability and widening

`integer_bounds` returns exact signed or unsigned mathematical min/max values, represented as `i128`, for UInt32, UInt64, Int8, Int16, Int32, and Int64. `is_integer_widening_cast` returns true only when both types have entries and the target closed range fully contains the source range. This is a sufficient condition to preserve nonnull status for exact integer conversion. UInt8 and UInt16 are **omitted**, so widening from those types can be pessimistically classified as potentially nullable; this is conservative, not a domain-soundness violation.

`is_null_preserving_cast` returns true for identity, exact integer widening, logical Categorical/Enum to String, Float32 to Float64, supported integer to Float64 and String, floating-point to String, and Boolean to String. Numeric precision need not be preserved to maintain non-nullness, so loss of precision in integer-to-Float64 conversion does not itself contradict this contract. Other admitted conversions, such as String to Int64, Float64 to Int64, Boolean to numeric, or UInt8 to UInt32, return false, forcing a nullable output descriptor.

The [standard-library reference model](https://github.com/opendp/opendp-audit/blob/main/tools/tests/test_polars_private_cast_classifier_model.py) checks the supported integer range table and all 36 full integer-pair containment decisions, plus 50 seeded samples per valid range pairing. It also checks representative nullable/nonnull pairs, numeric matrix membership, and excluded temporal/nested cases. It was **not** generated from or executed against the Rust implementation. The model verifies the mathematical containment rule and consistency of the documented policy only; actual Polars null production remains unverified.

### Remaining runtime dependency

A dtype allowlist is necessary to exclude known private-dependent failures, but its correctness depends on Polars behavior for admitted pairs. In particular, String-to-numeric parsing and Categorical-to-Enum need version-matched exception tests, including malformed values and mismatched category sets. It is not sufficient to infer infallibility merely from `CastOptions::NonStrict`. Consequently the full privacy/error-independent and null-preservation properties are **Partial**, despite `correctness/dtype-allowlist` and the exact interval rule being **Audited** within their explicit source-level scope.

The related historical [issue #3038](https://github.com/opendp/opendp/issues/3038) concerns casts introducing nulls contrary to the declared output domain; it is closed, and the current classifier provides the needed conservative flag. [Issue #3218](https://github.com/opendp/opendp/issues/3218) and [merged PR #3220](https://github.com/opendp/opendp/pull/3220) document why unsupported temporal coercion is excluded. These are **previously reported/resolved** issues, not novel findings.

## Next checks

- Run native OpenDP/Polars tests across all allowed non-identity casts with malformed private strings, boundary floats, Enum category mismatches, and any Polars-version-specific categorical conversions, asserting no private-dependent errors and output-domain membership.
- Re-audit on Polars version changes or if the allowlist is broadened.
- Consider adding UInt8 and UInt16 range entries only as a separate utility improvement, without weakening the conservative nullability flag before tests.
