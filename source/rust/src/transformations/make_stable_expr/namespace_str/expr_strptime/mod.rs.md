---
schema_version: 1
source: rust/src/transformations/make_stable_expr/namespace_str/expr_strptime/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/namespace_str/expr_strptime/mod.rs`

## Scope and assumptions

- **Audit scope:** The non-deprecated `make_expr_strptime` constructor for Polars string-to-temporal expressions, focused on construction-time type/argument checks, data-dependent error prevention, nullable output-domain claims, and the identity stability map. This is not an audit of the Polars parsing implementation, every accepted custom format, or the runtime optimizer.
- **Invariants:** A successful constructor must use a public explicit format, a stable input String expression, an eligible output type, a non-strict parser with data-independent ambiguity options, and an inferred dtype agreeing with the certified type. Failed parses should produce null rather than a private-data-dependent exception, and the output domain must allow those nulls. Each row must be parsed independently for identity event-level stability.
- **Assumptions:** Polars `strptime` with supported explicit formats and output types is row-wise, uses null for ordinary invalid parses under `strict=false`, and has no other private-value-dependent error paths. Polars' schema inference agrees with its runtime dtype. These external assumptions were not proved here.
- **Pinned upstream SHA:** `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. [Implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/namespace_str/expr_strptime/mod.rs), [proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/namespace_str/expr_strptime/make_expr_strptime.tex), and [Rust tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/namespace_str/expr_strptime/test.rs). Coordination: [audit #62](https://github.com/opendp/opendp-audit/issues/62).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `transformations::make_stable_expr::namespace_str::expr_strptime::make_expr_strptime` | correctness/argument-validation | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Argument and type guards](#argument-and-type-guards) |
| `transformations::make_stable_expr::namespace_str::expr_strptime::make_expr_strptime` | privacy/parse-error-independence | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Error-path hardening](#error-path-hardening); [resolved upstream #3226](https://github.com/opendp/opendp/issues/3226) |
| `transformations::make_stable_expr::namespace_str::expr_strptime::make_expr_strptime` | correctness/output-domain-nullability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Output-domain and stability claims](#output-domain-and-stability-claims) |
| `transformations::make_stable_expr::namespace_str::expr_strptime::make_expr_strptime` | privacy/rowwise-stability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Output-domain and stability claims](#output-domain-and-stability-claims) |

## Analysis

### Argument and type guards

The function only matches `Expr::Function` with `StringFunction::Strptime` and a literal requested output type. It requires exactly two Polars expression inputs, but deliberately **does not evaluate or stabilize the second user-supplied ambiguity argument**; the function later substitutes a public constant. It constructs the first/input expression through `make_stable` and requires its output dtype to equal `DataType::String`.

A public format is mandatory: `strptime_options.format.is_none()` returns a construction error, preventing Polars from inferring a format from private records. For requested `Time` outputs, it disallows `exact=false`. The supported requested output dtypes are `Time`, `Date` and timezone-naive `Datetime` with millisecond or microsecond units. It rejects nanosecond `Datetime` (known Polars panic risk), timezone-aware `Datetime` (localization errors), and every other output dtype. These are source-verifiable guard conditions applied before a private row is evaluated.

The code also runs **schema inference on a synthetic public String column**, invoking `strptime(...).to_field(...)` with the user-supplied *public* format and its sanitized parser options. If Polars infers a dtype other than the requested `to_type_lit`—for example an implicit UTC timezone from a format containing a timezone offset—construction rejects the expression. This check depends on the Polars planner's output schema, not on private values.

### Error-path hardening

The constructor unconditionally sets `strptime_options.strict = false`. This avoids exposing ordinary parse failures as errors. It discards the original second ambiguity expression by using `lit("null")`; it never evaluates that possibly private expression during the produced transformation. As noted above, it also rejects explicit timezone-aware output and inferred timezone-aware output. The source-level approach specifically removes the daylight-saving-time gap localization path that could fail on one private dataset but not its neighbor.

[Upstream issue #3226](https://github.com/opendp/opendp/issues/3226) documents the former distinguishing-event bug with timezone-aware parsing. It was **closed by merged PR #3225** on **2026-11-17**; the verified [patch](https://github.com/opendp/opendp/pull/3225/files) matches this source: constant ambiguity, timezone restrictions, and inferred dtype matching. The upstream test `test_strptime_rejects_timezone_aware_parsing` includes explicit timezone localization and implicit offset-format rejection; `test_strptime_naive_datetime_remains_supported` checks the permitted naive case with an invalid value resulting in null. Those tests were inspected, **not executed** here.

This resolves the known DST path in the reviewed source. It does **not** independently establish that all other custom formats and in-range temporal values are free of private-data-dependent panic or `ComputeError`; that broader privacy property remains **Partial**.

### Output-domain and stability claims

Once the output type passes static validation, `series_domain.set_dtype(to_type_lit.clone())` replaces the active column's dtype, and `series_domain.nullable = true` conservatively accounts for invalid strings mapping to null even from a nonnullable input. The earlier column expression's context is retained. The function composes `t_prior` with a `Function::then_expr` that applies `str.strptime` using the same sanitized options and public constant ambiguity; its stability map is `Clone::clone`.

For any fixed deterministic parser that emits a value or null for each row without data-dependent exceptions, rowwise parsing is 1-stable under symmetric row-add/remove distance. Source inspection verifies the constructor and composition structure; the necessary Polars runtime behavior and actual output-domain membership were not re-established, hence `Partial` status.

### Evidence and disposition

Evidence consisted of commit-pinned source, updated LaTeX proof, upstream issue/merged-PR history, and inspected native Rust tests. **No compiled OpenDP/Polars execution was run**: neither package is installed in the local environment. No additional mathematical reference model was made, because an independent Python date parser would not verify Polars' private-data-dependent error behavior.

**Disposition:** The identified DST-related defect is already fixed upstream (#3226 / #3225). No separate new defect was established by this bounded review; do not open a duplicate audit issue. No source changes to upstream OpenDP were made.

## Next checks

- Run version-matched native Polars/OpenDP tests for the accepted `Time`/`Date`/timezone-naive `Datetime(ms/us)` types under malformed public formats, extreme in-range strings, invalid dates, and surprising but syntactically accepted offset directives.
- Assert that compiled execution returns a null rather than an error for malformed private strings, and that resulting Polars schema matches `output_domain`.
- Revisit Polars version upgrades and any expanded parsing API: a newly admitted timezone or temporal unit requires a new error-path proof.
