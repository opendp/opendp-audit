---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Nullable `SeriesDomain::member` examines physical payloads of null slots

## Revisions and scope

- OpenDP: [`ef1a238634d6196b01a1a1e77d3d5ad2340e3094`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/series/mod.rs).
- Its pinned Polars dependency: `py-1.36.1`, [`PrimitiveArray::values_iter`](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-arrow/src/array/primitive/mod.rs).
- Audit coordination: [#83](https://github.com/opendp/opendp-audit/issues/83).
- Runnable native OpenDP regression: [`tools/integration/polars_series_member_null_backing.rs`](../tools/integration/polars_series_member_null_backing.rs), launched by [`polars-series-member-null.yml`](../.github/workflows/polars-series-member-null.yml).
- Pure logical-reference model: [`tools/tests/test_polars_series_member_null_validity_model.py`](../tools/tests/test_polars_series_member_null_validity_model.py).

## Required membership semantics

`SeriesDomain::new("x", OptionDomain::new(AtomDomain::<i32>::new_closed((1, 3))?))` describes an `Int32` series named `x` whose **nonnull** elements belong to the closed interval `[1, 3]`, while **null** elements are permitted. Therefore `[None, Some(2)]` must be a member. The underlying value stored at the null position has no meaning for membership.

Polars Arrow arrays store nullness in a validity bitmap. In pinned `py-1.36.1`, `PrimitiveArray::values_iter()` explicitly iterates *all backing values, ignoring the validity bitmap*. The same implementation offers `non_null_values_iter()` to skip null slots and says physical values at null positions are unspecified.

## Source-level discrepancy

In `SeriesDomain::member`, the `atom_member!` macro:

1. Retrieves the expected atom domain and Polars typed chunked array.
2. Rejects any nulls only if `self.nullable == false`.
3. Iterates **`arr.values_iter()`** in every chunk, calling `atom_domain.member` on every physical payload.

Step 3 checks invalid positions *even when `nullable == true`*. For `i32` bounds `[1, 3]`, a null slot with hidden backing value `0` triggers `false`, although that position is logically null. A logically identical series with a different unspecified backing payload can produce a different membership result. The defect is a **false negative** (under-approximating the declared series domain), not evidence of an overbroad domain.

The same pattern is used for floats and other primitive dtypes. It is most visible with bounded numeric domains. Existing `test_series_nan_with_option` uses an *unbounded* float atom domain, so it does not exercise the problematic combination of `nullable=true` and bounds excluding the null payload.

## Downstream impact and proof boundary

`FrameDomain::member` delegates to each column's `SeriesDomain::member`; therefore its membership result can also reject otherwise valid frames. Code that relies on successful membership checks for correctly typed data may falsely reject valid inputs or outputs. There is **no demonstrated disclosure or privacy-budget undercount** from this under-approximation. Such consequences require separate downstream analysis.

## Recommended repair

In the `atom_member!` macro, replace the validity-ignoring iterator with `arr.non_null_values_iter()` (or an equivalent validity-aware `iter().flatten()`), retaining the existing explicit null-count check when `nullable` is false. Add native regression tests for bounded nullable numeric and floating domains, including logically equal arrays with different null-slot physical payloads.

## Evidence status

**Source/API discrepancy:** verified on the exact pinned OpenDP and Polars revisions. The compiled regression was submitted to GitHub Actions as part of audit #83; its result must be recorded separately before claiming native reproduction. The standalone Python reference model checks logical validity-bitmap semantics but does not call OpenDP or Polars.
