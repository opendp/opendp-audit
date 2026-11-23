---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Non-deprecated Polars to_physical: dtype/domain correspondence

## Invariant and threat model

A row-wise `to_physical` conversion should not change other rows' physical representations when one private value changes, and the output domain must admit negative temporal values and null masks. Category encodings that are assigned based on the dataset violate identity stability.

## Affected symbols and sources

- [OpenDP source report](../source/rust/src/transformations/make_stable_expr/expr_to_physical/mod.rs.md) and [constructor implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_to_physical/mod.rs).
- [Native Rust test source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_to_physical/test.rs); [SeriesDomain setters](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/series/mod.rs).
- [Pinned compiled-Polars integration script](../tools/integration/polars_to_physical_runtime.py), run by [CI workflow](../.github/workflows/polars-to-physical.yml).
- [Stable `cut` conversion](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_cut/mod.rs) makes a public-label `Enum` from cut breaks before it can be converted to physical codes.

## Source and regression reasoning

### Categorical versus fixed Enum

`Categorical` mapping may change when a new earlier category is introduced, potentially changing many existing codes after a one-row insertion. Current OpenDP rejects it. In contrast, an `Enum` dtype fixes code order in public schema and the constructor accepts only its Polars-selected `UInt8/UInt16/UInt32` physical types. The pinned integration test checks Enum code consistency across differing row orders and a Categorical first-observation witness. This verifies *Polars executor behavior*, not that the OpenDP constructor's guard was exercised.

### Signed temporal values and nulls

Pre-epoch `Date` values become negative `Int32` day counts, correcting the old falsely unsigned output domain. `Datetime`, `Time` and `Duration` become signed `Int64` physical values. Source-level `SeriesDomain::set_dtype` and `set_element_domain` replace the element domain while preserving the outer `nullable` bit. Already physical floating types keep their original NaN/null descriptors instead of being replaced with a narrower domain.

The independent Polars regression checks representative signed pre-epoch values, temporal physical types, nullable masks, Enum physical width boundaries and floating NaN preservation.

### Historical issue disposition

[Upstream #2937](https://github.com/opendp/opendp/issues/2937) (Date falsely unsigned) was fixed by merged [PR #3052](https://github.com/opendp/opendp/pull/3052) on October 20, 2026. [Upstream #2944](https://github.com/opendp/opendp/issues/2944) (data-dependent Categorical codes) was fixed by merged [PR #3081](https://github.com/opendp/opendp/pull/3081) on November 6, 2026. Both fixes are present in pinned OpenDP revision `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. These are existing historical defects, not new bug reports.

## Verification boundary and findings

**Inspected:** The exact upstream Rust constructor, native test source, domain setter implementations and stable cut transformation. **Executed:** Seven regression tests against the **actual compiled Polars 1.36.1 executor**, all passed in [GitHub Actions run 45109018877](https://github.com/opendp/opendp-audit/actions/runs/45109018877). They cover date, temporal, Enum widths and category-code behavior, float NaN and nulls. The categorical test uses separate fresh processes because Polars 1.36.1 enables a process-global string cache. **Not executed:** The OpenDP Rust constructor, a complete composed differential-privacy release, or OpenDP's native source test suite.

No new unreported defect identified by source inspection or pinned Polars runtime tests; native OpenDP correctness/privacy remains **Partial**. The initial runtime CI attempt failed on an incorrect assumption that string caching was disabled; commit [42440ec](https://github.com/opendp/opendp-audit/commit/42440ecaec46deef52c6dc99d4081f6cd45d4c08) isolated fresh-process categorical checks, and the rerun passed.

## Remaining checks

Native OpenDP/Polars invocation and `ExprDomain::member` for nullable dates, enums, timezones, and optimizer-rewritten plans.
