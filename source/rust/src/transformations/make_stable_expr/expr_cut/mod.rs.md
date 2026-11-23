---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_cut/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_cut/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated Polars `make_expr_cut`, focusing on the distinction between fixed **returned Enum category codes** and potential **observable global Categorical state**, numeric input validation, and nullable-output accounting. Not an end-to-end DP proof or a compiled Polars side-channel reproduction.
- **Invariants:** (1) Physical bin indices derived from `cut(...).to_physical()` must not depend on neighboring records' category order; (2) construction must reject source types that can fail conversion on private non-null values; (3) output-domain nullability must accommodate `NaN`/null inputs; (4) executing a stable expression must not reveal private data through effects outside the returned data, including global category interners.
- **Assumptions:** Bin boundaries, explicit labels, and expression structure are public; Polars `Enum` uses a fixed ordering from `FrozenCategories`; `cut` produces Categorical internally, as in [upstream issue #3231](https://github.com/opendp/opendp/issues/3231). The external Polars implementation is not audited here.
- **Reviewed upstream:** `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. [Implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_cut/mod.rs), [Rust tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_cut/test.rs), [physical code conversion](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_to_physical/mod.rs). [Audit task #49](https://github.com/opendp/opendp-audit/issues/49).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `transformations::make_stable_expr::expr_cut::make_expr_cut` | correctness/fixed-enum-encoding | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Returned code stability](#returned-code-stability) |
| `transformations::make_stable_expr::expr_cut::make_expr_cut` | correctness/numeric-input-guard | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Construction guards](#construction-guards) |
| `transformations::make_stable_expr::expr_cut::make_expr_cut` | correctness/nullability-of-bins | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Construction guards](#construction-guards) |
| `transformations::make_stable_expr::expr_cut::make_expr_cut` | privacy/observable-categorical-state | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Remaining global-state risk](#remaining-global-state-risk); [upstream #3231](https://github.com/opendp/opendp/issues/3231) |

## Analysis

### Returned code stability

The constructor rejects `include_breaks=true`, validates that a `cut` expression has exactly one input, and constructs the stable input expression. It sorts public breaks before deriving default labels, rejects `NaN` breaks, checks the number of explicit labels, and creates a `FrozenCategories` value from public labels. It assigns the output column `DataType::Enum` with those categories, and its returned function builds:

```rust
expr.cut(breaks.clone(), labels.clone(), left_closed, include_breaks)
    .cast(enum_dtype.clone())
```

Thus the returned column's *physical indices* use public Enum order rather than dataset-dependent Categorical order. The reviewed [`to_physical` implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_to_physical/mod.rs) rejects raw Categorical, while admitting Enum with fixed-width integer representation (UInt8, UInt16, or UInt32). The upstream `test_cut_physical_codes_independent_of_rows` checks the values for an extra row occupying another bin; `test_cut_sorts_breaks_before_deriving_enum_labels` covers unsorted public boundaries. These tests were inspected, **not executed** in this session.

This resolves the returned-code issue reported in [upstream #2944](https://github.com/opendp/opendp/issues/2944) via [merged PR #3081](https://github.com/opendp/opendp/pull/3081) (November 6, 2026). The narrow `Audited` status covers only this representation property, conditional on the reviewed Polars Enum semantics—not absence of every side effect or a DP guarantee for all consumers.

### Construction guards

The source checks `middle_domain.column.dtype().is_primitive_numeric()` and rejects Boolean, String, Categorical, Enum, and nested nonnumeric dtypes at construction. Without this guard, a Polars implicit numeric cast might succeed on all-null input and fail on private non-null input. The guard arrived through [merged PR #3223](https://github.com/opendp/opendp/pull/3223) (November 18, 2026); its Rust test enumerates rejected input types. The labels are required to match the number of bins; `FrozenCategories::new` also validates its public category set.

The constructor **always** sets the output column's `nullable` flag to `true`, even when the input column is nonnullable. This is conservative: Polars `cut` maps `NaN` to null, and a nonnullable floating-point series can contain `NaN`. The upstream `test_cut_nullable_numeric_with_nan_and_infinity` checks that both null and NaN inputs produce null bin outputs. Consequently, the output does not falsely inherit a fixed count of non-null values from a fixed input row count, an important distinction addressed in merged [PR #3081](https://github.com/opendp/opendp/pull/3081) (upstream issue #2939).

These claims concern **the reviewed explicit source guards and domain descriptors**, not a comprehensive test of Polars' handling of every numeric dtype and bin boundary.

### Remaining global-state risk

**Existing, unresolved upstream privacy concern:** Although the output is cast from Categorical to Enum, the constructed expression **still invokes Polars `cut` first**. An output cast cannot by itself establish that any global categorical interner modified during this intermediate evaluation is invisible outside the measurement.

[Upstream issue #3231](https://github.com/opendp/opendp/issues/3231) explicitly reports that `cut` inserts labels into global categorical mapping state, potentially exposing private bin occupancy. The issue remained **open** as of this review. The reviewed source includes no independent mechanism to suppress, isolate, or roll back that side effect. Its existing output-code tests do not inspect global category state and therefore do not settle the reported side channel.

**Verification:** Source review establishes the `cut`-then-`cast` ordering and lack of local state isolation. The actual global-state mutation, observability, and distinguishability rely on the upstream report and the installed Polars version; a compiled OpenDP/Polars reproduction was **not run** (the review environment did not provide a Polars runtime). Accordingly, `privacy/observable-categorical-state` remains **Partial** and is tracked by existing upstream #3231, **not** a duplicate audit defect issue. The merged PR #3081 resolves raw returned-code instability, but is not evidence that the separate global-state concern is resolved.

## Next checks

1. Isolate a native Polars/OpenDP execution to check whether global categorical state observable after `cut` differs across neighboring inputs, without disclosing any private inputs or relying solely on returned Enum codes.
2. Follow upstream #3231 and future Polars API changes. Establish whether a direct Enum-producing cut implementation removes intermediate Categorical side effects, then refresh the audited property.
3. Re-evaluate numeric dtypes, null behavior, and publicly determined category ordering after any change to Polars' `cut` planner or to the public Enum cast.
