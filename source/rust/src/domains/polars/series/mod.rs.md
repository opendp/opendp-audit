---
schema_version: 1
source: rust/src/domains/polars/series/mod.rs
updated: 2026-11-23
---

# `rust/src/domains/polars/series/mod.rs`

## Scope and assumptions

- **Source scope:** Non-deprecated `SeriesDomain::member` for primitive, bool, and String Polars series; constructor nullability via `SeriesDomain::new` and `OptionDomain`. Checked how atomic element bounds, allowed nulls and Arrow validity bitmaps interact. This is not a full audit of categorical, temporal, nested, FFI or all mutable domain helpers.
- **Property:** Validity-bitmap-aware membership must accept a nullable series if every *valid* value satisfies the atom domain, independently of physical payloads stored at invalid slots. A nonnullable domain must reject any null. Name/type mismatches and native Polars errors were outside the narrow counterexample.
- **Assumptions:** OpenDP `AtomDomain<T>::member` checks bounds of the supplied *nonnull* value. Polars' `values_iter()` ignores validity, and `non_null_values_iter()` filters invalid slots; verified directly in the **pinned Polars `py-1.36.1` source**. Underlying null-slot buffer values have no logical meaning.
- **Pinned references:** [OpenDP `SeriesDomain`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/series/mod.rs), [OpenDP native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/series/test.rs), [Polars `py-1.36.1` primitive iterator](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-arrow/src/array/primitive/mod.rs), and [`FrameDomain::member` delegation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/frame/mod.rs). [Coordination #83](https://github.com/opendp/opendp-audit/issues/83).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `domains::polars::series::SeriesDomain::member` | correctness/nullable-bounded-membership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Null-slot validity defect](#null-slot-validity-defect) |
| `domains::polars::series::SeriesDomain::member` | correctness/nonnullable-null-rejection | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Correct null rejection](#correct-null-rejection) |
| `domains::polars::series::SeriesDomain::member` | correctness/nonnull-atom-bounds | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Raw-value iteration and tests](#raw-value-iteration-and-tests) |
| `domains::polars::series::SeriesDomain::new` | correctness/option-nullability | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Correct null rejection](#correct-null-rejection) |
| `domains::polars::series::SeriesDomain::member` | privacy/downstream-domain-postcondition | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Impact and limits](#impact-and-limits) |

## Analysis

### Null-slot validity defect

The `atom_member!` macro used for primitive numeric dtypes, bool and String first casts the Polars series to a typed ChunkedArray, rejects `null_count() > 0` only when `self.nullable == false`, and then iterates over each Arrow chunk using **`arr.values_iter()`**. Every returned underlying physical value is passed to the atom domain's `member` predicate.

This is incorrect for *nullable bounded domains*: in **the exact pinned `py-1.36.1` Polars source**, `PrimitiveArray::values_iter` is explicitly documented as **ignoring the array validity bitmap**, while `non_null_values_iter` uses the bitmap to skip null slots. The physical value of a null slot is explicitly unspecified. Thus a legal nullable series can be incorrectly rejected if the ignored null slot's backing value lies outside the public atom bounds.

A minimal witness is a nullable `Int32` domain with closed element bounds `[1,3]` and logical series `[null, 2]`. The only nonnull value, 2, belongs to `[1,3]`, so the series must be a member regardless of the null slot's raw buffer contents. If that raw slot is 0, `values_iter()` yields both 0 and 2 and `AtomDomain<i32>::member(0)` is false. It follows that this implementation wrongly returns false for the permitted value. This is a **false negative / under-approximation**, not evidence of acceptance of out-of-bounds nonnull values.

### Correct null rejection

`SeriesDomain::new(name, OptionDomain<D>)` retains the inner `D` element domain while setting `nullable=true`; the non-optional `AtomDomain<D>` constructor sets `nullable=false`. When `self.nullable == false` and Polars reports any null, the macro returns `false` before iterating values. That nonnullable check is correct; the error is only that `nullable=true` does not cause the later loop to ignore invalid slots.

The existing upstream `test_series_nan_with_option` tests optional floats without bounds, which can mask this error because the hidden numeric null payload typically belongs to an unbounded domain. `test_series_bounded` tests bounded nonnull values and `test_series_non_nan` uses an unbounded Boolean domain. No inspected source test covers bounded, nullable numeric membership.

### Raw-value iteration and tests

The audit includes a [standalone Python logical reference model](https://github.com/opendp/opendp-audit/blob/main/tools/tests/test_polars_series_member_null_validity_model.py), with cases for hidden 0/999 payloads, valid and invalid nonnull values, and the nonnullable rejection control. This deliberately does **not** execute compiled OpenDP/Polars.

A [native pinned OpenDP integration regression](https://github.com/opendp/opendp-audit/blob/main/tools/integration/polars_series_member_null_backing.rs) additionally checks `SeriesDomain::member` using Polars 1.36.1 and inspects both the primitive raw buffer iterator and the validity-aware iterator. [Its dedicated workflow](https://github.com/opendp/opendp-audit/blob/main/.github/workflows/polars-series-member-null.yml) runs the test in a temporary checkout of the pinned upstream revision. Record the actual CI result before claiming native reproduction.

### Impact and limits

`FrameDomain::member` delegates to `SeriesDomain::member` on each column, so this false-negative behavior can propagate to whole-frame domain membership. It violates the advertised domain-membership semantics and can reject valid inputs or produced outputs in code paths that perform a membership check. It does **not** by itself show a private-data-dependent release, a budget undercount, or violation of an output-distance bound. Such privacy consequences were not reproduced; the claim is **correctness**, with privacy impact **unconfirmed**.

A repair would change the per-chunk iteration to `arr.non_null_values_iter()` (or an equivalent validity-filtered iterator), preserve the nonnullable null-count guard, and add tests for bounded optional integers and floats with null payloads outside the declared bounds. No upstream code was modified in this audit.

## Next checks

- Verify the dedicated compiled pinned-OpenDP/Polars CI result; test native nullable bounded integers and float domain members.
- Add a native regression to upstream OpenDP when fixing `SeriesDomain::member`.
- Review the full downstream use of `FrameDomain::member` and `ExprDomain::member` to assess whether false negatives can become externally visible errors or impact privacy-related postconditions.
