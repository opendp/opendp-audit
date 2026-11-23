---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_cast/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_cast/mod.rs`

## Scope and assumptions

- **Scope:** The non-deprecated `make_expr_cast` transformation: conversion of cast options, construction from stable input expressions, validation of target literal dtype and reviewed dtype pairs, propagation of nullable output-domain descriptors, and rowwise stability. The shared classifier has its own [source report](https://github.com/opendp/opendp-audit/blob/main/source/rust/src/transformations/make_stable_expr/cast.rs.md).
- **Invariants:** No successful private cast may use Polars strict mode (which can reveal failed conversions through errors) or unchecked overflowing mode. The target dtype must be a public literal. Only a certified source/target pair is accepted, and nullable output must be allowed whenever an invalid private value may become null. The emitted expression must match the constructor's sanitized options.
- **Assumptions:** Successful Polars `CastOptions::NonStrict` conversion for the admitted pairs is deterministic, rowwise, and data-independently fallible; the shared `check_private_cast` classifier is sound for the pinned Polars version. Source-level analysis does not independently establish those native runtime conditions.
- **Pinned upstream SHA:** `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. [Constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_cast/mod.rs), [shared classifier](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/cast.rs), [native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_cast/test.rs), [SeriesDomain::set_dtype](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/series/mod.rs). Coordination: [audit issue #69](https://github.com/opendp/opendp-audit/issues/69).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `transformations::make_stable_expr::expr_cast::make_expr_cast` | privacy/strict-overflow-control | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cast option sanitization](#cast-option-sanitization) |
| `transformations::make_stable_expr::expr_cast::make_expr_cast` | correctness/dtype-literal-guard | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cast option sanitization](#cast-option-sanitization) |
| `transformations::make_stable_expr::expr_cast::make_expr_cast` | correctness/output-domain-nullability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Output-domain propagation](#output-domain-propagation) |
| `transformations::make_stable_expr::expr_cast::make_expr_cast` | privacy/rowwise-stability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Runtime contract and limits](#runtime-contract-and-limits) |

## Analysis

### Cast option sanitization

The constructor accepts only `Expr::Cast`; it exhaustively matches Polars' `CastOptions` variants: `Strict` and `NonStrict` both become `NonStrict`, while `Overflowing` is rejected before constructing the transformation. An invalid public cast expression cannot induce a release-time strict error or hidden integer wraparound through this entry point.

It first calls `make_stable` for the source expression. The target dtype is then extracted from `to_type.as_literal()`, and nonliteral targets are rejected. The source/target dtype pair passes through the shared `check_private_cast` allowlist, introduced in [merged hardening PR #3220](https://github.com/opendp/opendp/pull/3220). This step explicitly rejects unreviewed conversions involving temporal families, physical Categorical codes, and nested types. The emitted `Function::then_expr` builds a new `Expr::Cast` with the **sanitized `options`**, not with the original strict/overflow options. This is direct source-level evidence of the asserted guard behavior, not a claim that non-strict conversion never has its own defects.

### Output-domain propagation

The code clones the source `ExprDomain`. When the source dtype differs from the target dtype, it calls `data_column.set_dtype(target)` and then updates `data_column.nullable |= may_introduce_null`. The reviewed `SeriesDomain::set_dtype` replaces only the element-domain descriptor and does **not** reset the independent nullable flag. The resulting domain therefore conservatively retains preexisting nullability and adds permission for nulls whenever the shared classifier returns true. The new element-domain descriptor is not mistakenly retained with the old datatype; for floats it is reinitialized to the matching `AtomDomain::<f32>` or `AtomDomain::<f64>`.

When input and output dtype are identical, the constructor does not rebuild the element domain. Such casts are permitted by the classifier only for explicitly supported identity dtypes, and the output-domain descriptors are retained. The upstream `test_make_expr_cast_nullability` checks that non-strict String-to-Int64 casts yield nullable output and that an invalid string produces null. `test_make_expr_cast_widening_preserves_non_null` checks Int32-to-Int64. These native Rust tests were inspected, not run in this session.

The general correctness of the nullable flag is **Partial**: it depends on the shared allowlist's categorization and on actual Polars runtime conversions. Historical [upstream #3038](https://github.com/opendp/opendp/issues/3038), which described an earlier nullability error, is closed. The present code contains the corresponding corrective logic and the later conservative allowlist.

### Runtime contract and limits

Mathematically, applying any deterministic function to each record independently is stable for event-level insert/delete distance (assuming emitted record counts are unchanged). Here `make_expr_cast` produces a rowwise Polars `Expr::Cast` with unchanged metric and an identity `StabilityMap::new(Clone::clone)`. The construction has no explicit access to private records. The privacy statement still depends on the native Polars cast being truly per-row, non-exceptional on all admitted input values and using a public fixed encoding; therefore full error-independence and stability are not certified solely by these checks.

The shared classifier report and its [independent Python reference checks](https://github.com/opendp/opendp-audit/blob/main/tools/tests/test_polars_private_cast_classifier_model.py) cover integer range inclusion, representative nullable/nonnull conversions, and rejected dtype families. They do **not** execute native OpenDP or Polars. Rust's existing source tests check a wider practical array of conversions and errors, but were not executed here.

### Disposition

No new distinct defect was established in the reviewed constructor. Prior issues covering nullability and private-dependent cast errors are already closed: [upstream #3038](https://github.com/opendp/opendp/issues/3038) and [upstream #3218](https://github.com/opendp/opendp/issues/3218); the [merged #3220 patch](https://github.com/opendp/opendp/pull/3220) supplies the reviewed allowlist. No duplicate defect issue is warranted.

## Next checks

- Native version-pinned Polars execution over the admitted dtype matrix with boundary and malformed values, with both collection error checks and `output_domain.member` checks.
- Probe Categorical-to-Enum conversions, including mismatched categories and global interners, because Polars' internal implementation is external to the Rust constructor.
- Re-examine the classifier and emitted cast options after future Polars dtype or optimizer changes, especially any new `CastOptions` variant.
