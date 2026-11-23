---
schema_version: 1
upstream_commit: a010591f55b1713c926f8e355091471634480307
updated: 2026-11-23
status: Partial
---

# Polars composite domains do not enforce their declared membership predicates

## Invariant and threat model

A public `Domain::member` check must accept exactly the members described by the domain (subject to the domain's own representation contract). For `EnumDomain`, any of the declared enum strings is valid. For `ArrayDomain`, a fixed-length Polars `Series` carrier must have elements conforming to the configured `element_domain`. These checks inform user validation and any consumer that trusts `Domain::member`; they are **not themselves a privacy mechanism**.

Reviewed upstream main at `a010591f55b1713c926f8e355091471634480307`, focusing on the direct member implementations and their public Rust/FFI exposure. The concrete source-level defects are distinct from [existing audit #57](https://github.com/opendp/opendp-audit/issues/57), which concerns `ExprDomain` metric-space checks for NaN-permitting float domains.

## Affected symbols and source audits

- [`EnumDomain::new` and `EnumDomain::member`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/domains/polars/enum/mod.rs) and [source audit](../source/rust/src/domains/polars/enum/mod.rs.md).
- [`ArrayDomain::new` and `ArrayDomain::member`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/domains/polars/array/mod.rs) and [source audit](../source/rust/src/domains/polars/array/mod.rs.md).
- [`SeriesDomain` and `DynSeriesElementDomain`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/domains/polars/series/mod.rs) explain nesting and the limitation of current `SeriesDomain::member` for Enum/Array.
- [`EnumDomain` FFI](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/domains/polars/enum/ffi.rs) and [`ArrayDomain` FFI](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/domains/polars/array/ffi.rs) expose the domain constructors. [Generic `Domain.member` FFI](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/domains/ffi.rs) invokes their member implementations.
- [Audit task #136](https://github.com/opendp/opendp-audit/issues/136).

## Reasoning and evidence

### 1. EnumDomain checks membership of the first category only

`EnumDomain::member` evaluates `is_in(&self.categories, &Series::new(...value...).implode()?.into_series(), false)?.get(0).unwrap()`. Polars `is_in(left, right)` yields one boolean **per element of the left series**. Since the left series is the declared categories, `.get(0)` answers whether the **first category** occurs in the one-element candidate set. This does *not* answer whether the supplied value occurs anywhere in all declared categories.

A minimal regression is:

```rust
let domain = EnumDomain::new(Series::new("".into(), vec!["a", "b", "c"]))?;
assert!(domain.member(&"a".into())?);
assert!(domain.member(&"b".into())?); // expected true, predicted false on current source
assert!(domain.member(&"c".into())?); // expected true, predicted false on current source
assert!(!domain.member(&"d".into())?);
```

[Current unit test](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/domains/polars/enum/test.rs) tests only the first category `a` and a missing category `d`; it cannot catch this defect. Independent [Polars is_in documentation](https://docs.pola.rs/api/python/stable/reference/series/api/polars.Series.is_in.html) confirms the left-operand alignment. An empty categories series also reaches a `.get(0).unwrap()` expression and **may** panic if the result is empty; the exact native empty-case behavior has not been verified and is not included in the confirmed finding.

**Finding:** [issue #137](https://github.com/opendp/opendp-audit/issues/137), confirmed from source; no native OpenDP/Polars execution.

### 2. ArrayDomain accepts elements that violate its nested domain

`ArrayDomain` explicitly stores a `DynSeriesElementDomain` (which includes dtype and can retain bounds/NaN policy) and a fixed size. Its `Domain::member` implementation returns an error if `value.len() != self.size`; otherwise it unconditionally returns `Ok(true)`, without looking at values, dtype, nullity, bounds, or NaN policy.

Minimal Rust regressions to execute:

```rust
let bounded = ArrayDomain::new(AtomDomain::<i32>::new_closed((0, 1))?, 2);
assert!(bounded.member(&Series::new("".into(), [0_i32, 1]))?);
assert!(!bounded.member(&Series::new("".into(), [0_i32, 9]))?);
// Current member implementation returns true for both.

let finite = ArrayDomain::new(AtomDomain::<f64>::new_non_nan(), 2);
assert!(!finite.member(&Series::new("".into(), [1.0, f64::NAN]))?);
// Current member implementation returns true.
```

`DynSeriesElementDomain` currently provides `dtype`, `as_any`, and equality methods, not dynamic membership. The fix therefore requires a well-specified dispatch/member interface or an appropriate typed implementation; length-only logic is not sufficient.

**Finding:** [issue #138](https://github.com/opendp/opendp-audit/issues/138), confirmed from source; no native OpenDP/Polars execution.

### Reachability and impact boundaries

The standalone `EnumDomain` and `ArrayDomain` member APIs are public in Rust and exposed via the generic FFI `Domain.member` call. However, [`SeriesDomain::member`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/domains/polars/series/mod.rs) currently handles primitive types and returns `NotImplemented` for nested Array and Enum series; therefore we **cannot** infer that `SeriesDomain::member` silently accepts invalid nested data. `ExprDomain` metric-space conditions may independently be insufficient for nested NaNs ([audit #57](https://github.com/opendp/opendp-audit/issues/57)), but that finding is not duplicated here.

These are **correctness/domain-contract** defects, not demonstrated privacy-budget underestimates. Claims about actual DP releases or FFI aborts need further execution and call-path tracing.

## Findings

- [#137: EnumDomain checks only the first category](https://github.com/opendp/opendp-audit/issues/137) — verification **Confirmed (source-level)**, upstream disposition **Unreported**, correctness.
- [#138: ArrayDomain ignores nested value constraints](https://github.com/opendp/opendp-audit/issues/138) — verification **Confirmed (source-level)**, upstream disposition **Pending PR #3242**; audit issue closed under the repository's existing-fix tracking policy, while the fix is not merged into upstream `main`.
- Searched open and closed upstream/audit issues and PRs. A later check identified [open/draft PR #3242](https://github.com/opendp/opendp/pull/3242), which adds nested dtype/null/value checks to `ArrayDomain::member`, addressing #138. Its `enum/mod.rs` changes add null-category validation and dtype support but **do not change `EnumDomain::member` or add a regression for the second declared category**; #137 remains unreported/unfixed. PR #3242 is not merged into upstream `main` as of this review.
- Reviewed the public constructors, FFI exposure, and surrounding SeriesDomain limitations. No native OpenDP/Polars runtime test was executed.

## Unresolved questions

1. Run the native Rust regressions with OpenDP's pinned Polars dependency, checking every declared enum category, zero-category handling, array bounds/NaN/dtype/nullity, and empty fixed-size arrays.
2. Fix `EnumDomain::member` to check a singleton value against all declared categories (not only the first result), with safe empty-category handling.
3. Implement per-element `ArrayDomain::member` checks, or document/limit unsupported carrier types explicitly.
4. Review whether other callers assume direct domain membership has certified nested values. Do not upgrade the classification to a privacy exploit without an actual privacy-accounting or observable-output counterexample.
