---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Audited
---

# Polars set-covering helper narrows u32 weights before negation

## Invariant and threat model

OpenDP's public Polars frame-margin and frame-distance bound descriptors use `u32` for group counts. The shared covering helper must accept the whole `u32` range without panicking and should choose smaller weights on exact coverage/set-size ties. The first obligation is **availability**; the second affects utility and the tightness of conservative public contribution bounds. This investigation does not find a privacy-map undercount.

## Affected symbols and records

- [Source audit: `FrameDomain::get_margin`, `find_min_covering` and margin setters](../source/rust/src/domains/polars/frame/mod.rs.md), pinned [upstream frame code](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/frame/mod.rs).
- [Source audit: `Bounds::get_bound` and `Bound::with_num_groups`](../source/rust/src/metrics/polars/mod.rs.md), pinned [upstream metrics code](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/polars/mod.rs).
- [Source-based Python model](../tools/tests/test_polars_covering_weight_model.py), [audit defect #92](https://github.com/opendp/opendp-audit/issues/92), and [coordination task #91](https://github.com/opendp/opendp-audit/issues/91).

## Minimal arithmetic and call-chain reproduction

The comparison key in `find_min_covering` is `(new_coverage, -(set.len() as i32), -(*weight as i32))`. Its `weight` originates as a `u32` stored in either `Margin::max_groups` or `Bound::num_groups`. The value `2^31` is a **valid public group upper bound**, and there is no constructor restriction rejecting it. On that value, `weight as i32` equals `i32::MIN`. Checked Rust unary negation of that value panics inside `max_by_key`, while unchecked negation wraps. A single bound and a single requested column suffice; no allocation of `2^31` records is required.

Two source-level witnesses:

```rust
// A simple valid frame domain, using the public constructor.
let domain = LazyFrameDomain::new(vec![
    SeriesDomain::new("A", AtomDomain::<i32>::default()),
])?.with_margin(Margin::by(["A"]).with_max_groups(2_147_483_648))?;
let _ = domain.get_margin(&HashSet::from(["A".into()]));

// The same helper is reachable from the public frame-distance type.
let bounds = Bounds(vec![Bound::by(["A"]).with_num_groups(2_147_483_648)]);
let _ = bounds.get_bound(&HashSet::from(["A".into()]));
```

For unchecked builds the stronger observable symptom is **incorrect tie-breaking**. Query `by={A}` using descriptors `by={A,B}` weight `1` and `by={A,C}` weight `2^31+1`. Both cover the requested key and have identical set size. Because the comparator transforms the larger bound into `+2_147_483_647` and the smaller into `-1`, the larger weight is selected. The resulting inferred group bound is conservative but vastly less useful. A `std::cmp::Reverse` tuple of the original unsigned weights avoids both failure modes.

## Verification and evidence gaps

**Executed locally:** Six standard-library Python tests translated the source's narrowing, checked versus unchecked negation, cover-selection rules, and reversed priority on tied descriptors. The tests passed and include all four boundary values around `2^31` and `u32::MAX`. They are **not** compiled OpenDP Rust or Polars runs. The pinned native upstream covering tests were inspected; they only test small weights and do not reach `i32::MIN`. Native integration runs under debug and release builds remain outstanding.

**Source conclusion:** The comparator arithmetic is incompatible with a full-range `u32` bound, and both public descriptor callers pass values through unchanged. This is a confirmed *source-level* arithmetic defect with an availability manifestation under overflow checking and a tie-order correctness manifestation otherwise.

**Privacy qualification:** The greedy helper returns a covering union of candidate sets and multiplies selected **upper** bounds; choosing a larger valid bound does not imply an unsafe smaller bound. This audit found no differential privacy undercount, output disclosure, or private-input-dependent exception. A full proof of marginal and frame-distance composition was outside this bounded scope.

## Disposition and next steps

- **Upstream:** **Unreported** at pinned current `main`; audit and upstream issue/PR searches found no equivalent fix. Historical [PR #2153](https://github.com/opendp/opendp/pull/2153) implemented/proved the existing helper and was merged in 2024; it is not corrective for this bug.
- **Tracking:** [Issue #92](https://github.com/opendp/opendp-audit/issues/92), classified correctness/availability; no privacy label because undercount was not established.
- **Remediation:** Replace `-(set.len() as i32)` and `-(*weight as i32)` with `Reverse(set.len())` and `Reverse(*weight)` in the comparison tuple, preserving coverage as the primary key. Add native Rust regressions with `2^31-1`, `2^31`, `2^31+1`, and `u32::MAX` through both caller APIs.
