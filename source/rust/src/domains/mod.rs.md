---
schema_version: 1
source: rust/src/domains/mod.rs
updated: 2026-11-23
---

# `rust/src/domains/mod.rs`

## Scope and assumptions

- **Scope:** `AtomDomain::new_closed`, `AtomDomain::member`, `Bounds::new_closed`, for built-in numeric and ordered simple scalars (`String`, `bool`, `char`, `&str`).
- **Invariant:** After construction, bounded domains must return a Boolean membership result for valid scalar values, or reject unsupported bounded types at construction.
- **Source:** [Pinned upstream implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/mod.rs), [`CheckAtom` implementations](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/operations/mod.rs).
- **Evidence level:** Source trace plus successful pinned OpenDP native regression (2 passed), run in GitHub Actions.

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `AtomDomain::new_closed` | correctness/bounded-scalar-membership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | Accepts ordered simple scalar bounds without checking whether membership is implemented. |
| `AtomDomain::member` | correctness/bounded-scalar-membership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | Forwards non-null bounded members to `CheckAtom::is_bounded`; [issue #100](https://github.com/opendp/opendp-audit/issues/100). |
| `Bounds::new_closed` | correctness/bounded-scalar-membership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | Checks order and nullity, not scalar bounded-membership support. |

## Analysis

### Constructor/member contract — `correctness/bounded-scalar-membership`

**Conclusion:** `AtomDomain::<String>::new_closed(("a".into(), "z".into()))` succeeds; `member(&"m".to_string())` instead errors with `FailedFunction: bounds check is not implemented`. The same applies to `bool`, `char`, and `&str`. Numeric `CheckAtom` implementations override `is_bounded` and do not have this error.

**Evidence:** `Bounds::new_closed` validates bounds and returns the interval without invoking `is_bounded`. `AtomDomain::member` calls `CheckAtom::check_member`, which calls `is_bounded` whenever bounds exist and the value is non-null. The `impl_CheckAtom_simple!(bool String char &str)` macro overrides no methods, so `is_bounded` uses its error-returning default. Numeric implementations call `Bounds::member`. Unbounded strings bypass the branch; NaNs are handled by `check_member` before bounds.

**Impact:** Non-deprecated domain API correctness/usability, **not** a demonstrated privacy loss. [Cross-file investigation](../../../../investigations/bounded-atom-domain-scalar-membership.md) and [audit finding #100](https://github.com/opendp/opendp-audit/issues/100).

**Limitations:** Native regression executed for the listed built-ins only; custom `CheckAtom` types and other domain types are not reviewed.

## Next checks

The pinned native regression passed. Either implement bounded membership for these scalar types or reject unsupported bounds during construction.

**Native verification (2026-11-23):** [Pinned OpenDP CI](https://github.com/opendp/opendp-audit/actions/runs/45112011556) executed `cargo test --no-default-features --features contrib --test bounded_atom_domain_membership` at `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`: **2 passed, 0 failed**, including all simple-scalar witnesses and numeric/unbounded controls. Verification for [issue #100](https://github.com/opendp/opendp-audit/issues/100) is **Reproduced**. This does not establish privacy impact.
