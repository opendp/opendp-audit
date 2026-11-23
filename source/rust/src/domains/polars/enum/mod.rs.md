---
schema_version: 1
source: rust/src/domains/polars/enum/mod.rs
updated: 2026-11-23
---

# `rust/src/domains/polars/enum/mod.rs`

## Scope and assumptions

- **Audit scope:** Direct `EnumDomain` construction and `Domain::member` predicate for declared string categories; Rust and FFI exposure; existing unit-test coverage.
- **Invariant:** Membership must accept every declared category and reject every other string; empty categories should not panic.
- **Assumptions:** A Polars String `Series` contains the public categories; `is_in(left, right)` produces one boolean per left-series element. The source-level conclusion has not been validated with a compiled OpenDP/Polars run.
- **Source links:** [implementation](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/domains/polars/enum/mod.rs), [current tests](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/domains/polars/enum/test.rs), [FFI](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/domains/polars/enum/ffi.rs), [investigation](../../../../../../investigations/polars-composite-domain-membership.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `opendp::domains::EnumDomain::member` | correctness/domain-membership | Audited | `a010591f55b1713c926f8e355091471634480307` | `is_in(categories, singleton(value))` returns a per-category mask; `.get(0)` considers only first category. [Investigation](../../../../../../investigations/polars-composite-domain-membership.md); [#137](https://github.com/opendp/opendp-audit/issues/137). |
| `opendp::domains::EnumDomain::new` | correctness/constructor-constraints | Partial | `a010591f55b1713c926f8e355091471634480307` | Validates String dtype and category uniqueness. Does not reject an empty series; `member` then indexes the zero-th mask slot. Native empty-case failure mode not verified. |

## Analysis

### `EnumDomain::member` — `correctness/domain-membership`

**Conclusion:** Source-level correctness failure. With category series `["a","b","c"]`, member of `"a"` is true, while `"b"` and `"c"` are predicted false because the code accesses the first boolean of a per-category membership result. The existing test checks `"a"` and `"d"`, both of which agree with the faulty implementation.

**Evidence:** The `is_in` argument ordering is explicit in the source and conforms to Polars's published left-operand semantics. The [investigation](../../../../../../investigations/polars-composite-domain-membership.md) records the minimal Rust regression and API reachability.

**Limitations:** Not executed against native OpenDP. Empty-set behavior may produce a panic but has not been confirmed. A downstream DP privacy leak is not claimed.

**Related:** [Audit defect #137](https://github.com/opendp/opendp-audit/issues/137) is separate from [#138](https://github.com/opendp/opendp-audit/issues/138) (array membership, pending upstream [PR #3242](https://github.com/opendp/opendp/pull/3242)) and [#57](https://github.com/opendp/opendp-audit/issues/57) (metric-space validation). PR #3242 touches `EnumDomain` but only validates null categories and adds dtype support; its diff leaves the faulty `member` expression unchanged.

## Next checks

Add a native Rust regression for the second/last category and empty category sets; change membership to test the value against the full set.
