---
schema_version: 1
source: rust/src/domains/polars/array/mod.rs
updated: 2026-11-23
---

# `rust/src/domains/polars/array/mod.rs`

## Scope and assumptions

- **Audit scope:** Direct `ArrayDomain::member` for fixed-size Polars Series carriers and nested element-domain constraints; FFI and SeriesDomain interaction.
- **Invariant:** Members must have the declared width and must satisfy each nested element-domain predicate, including dtype, numeric bounds, and non-NaN policy.
- **Assumptions:** A length-two primitive Series is a representable standalone `ArrayDomain::Carrier`; source code unconditionally returns true on correct length. Native OpenDP has not been executed.
- **Source links:** [implementation](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/domains/polars/array/mod.rs), [FFI](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/domains/polars/array/ffi.rs), [SeriesDomain](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/domains/polars/series/mod.rs), [investigation](../../../../../../investigations/polars-composite-domain-membership.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `opendp::domains::ArrayDomain::member` | correctness/domain-membership | Audited | `a010591f55b1713c926f8e355091471634480307` | Checks only Series length, never reads nested `element_domain`; accepts out-of-bounds, NaN, and wrong-type entries with correct length. [Investigation](../../../../../../investigations/polars-composite-domain-membership.md); [#138](https://github.com/opendp/opendp-audit/issues/138). |
| `opendp::domains::ArrayDomain::new` | correctness/descriptor-preservation | Audited | `a010591f55b1713c926f8e355091471634480307` | Preserves provided `element_domain` and fixed width but member implementation does not enforce their combined contract. |

## Analysis

### `ArrayDomain::member` — `correctness/domain-membership`

**Conclusion:** The method's only condition is `value.len() != self.size` (error); all values of matching length return true. Thus `ArrayDomain::new(AtomDomain::<i32>::new_closed((0,1))?,2)` accepts a Series `[0,9]`, and an ArrayDomain of non-NaN f64 also accepts `[1.0, NaN]`.

**Evidence:** Unconditional control flow establishes the source-level error; the [investigation](../../../../../../investigations/polars-composite-domain-membership.md) includes Rust regression cases.

**Limitations:** The generic `SeriesDomain::member` currently returns `NotImplemented` for Array dtype, so the finding is **not** claimed as a working SeriesDomain bypass. No native execution or DP privacy attack was performed.

**Related:** [Audit defect #138](https://github.com/opendp/opendp-audit/issues/138); sibling enum membership defect [#137](https://github.com/opendp/opendp-audit/issues/137); different nested NaN metric-space issue [#57](https://github.com/opendp/opendp-audit/issues/57).

## Next checks

Introduce dtype/nullity/per-element validation, add native Rust tests for bounds, NaNs, wrong dtypes and widths, and evaluate downstream effects separately.
