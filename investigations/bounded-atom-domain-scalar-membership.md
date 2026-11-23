---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Bounded AtomDomain scalar membership capability

## Invariant and threat model

A `new_closed` atom domain of an in-range, ordered scalar must either provide `Ok(true)` from `member`, or refuse unsupported bounded construction. This is a public-domain correctness contract, not a privacy-budget claim.

## Affected symbols and source audits

- [`AtomDomain::new_closed`, `AtomDomain::member`, `Bounds::new_closed`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/mod.rs); [source report](../source/rust/src/domains/mod.rs.md).
- [`CheckAtom::check_member`, `CheckAtom::is_bounded`, built-in implementations](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/operations/mod.rs); [source report](../source/rust/src/traits/operations/mod.rs.md).

## Reasoning and evidence

1. `AtomDomain::<String>::new_closed(("a".into(), "z".into()))` is permitted by its trait bounds and succeeds after `Bounds::new_closed` validates non-null, sorted endpoints.
2. `AtomDomain::member` forwards `Some(bounds)` to `CheckAtom::check_member`. For a non-null value this always calls `is_bounded`.
3. `impl_CheckAtom_simple!(bool String char &str)` implements `CheckAtom` without overriding `is_bounded`. Its default returns `FailedFunction: bounds check is not implemented`. Hence bounded domains of all four built-in scalar types fail even for in-range values.
4. Numeric `CheckAtom` implementations delegate bounded checks to `Bounds::member`, and unbounded strings do not call `is_bounded`. These are negative controls. NaN endpoints are rejected by `Bounds::new`.

**Native verification (2026-11-23):** [Pinned CI run 45112011556](https://github.com/opendp/opendp-audit/actions/runs/45112011556) built the actual OpenDP Rust crate at `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` with `--no-default-features --features contrib` and executed [the regression](../tools/integration/bounded_atom_domain_membership.rs): **2 passed, 0 failed**. The `bounded_simple_scalar_domains_error_on_member` test reproduced the errors for all four simple scalar types, while `numeric_unbounded_and_invalid_bound_controls` checked expected successful and rejected cases. This is native reproduction of the API mismatch, not an inferred privacy failure.

## Findings

[Candidate defect #100](https://github.com/opendp/opendp-audit/issues/100) tracks the unsupported bounded scalar-membership behavior. It is not equivalent to the [nullable Polars series issue #87](https://github.com/opendp/opendp-audit/issues/87), which concerns interpreting null backing data. Searches of audit and upstream issues and PRs yielded no equivalent known fix.

## Unresolved questions

Choose whether to implement `is_bounded` for these scalars or reject bounded construction, and assess whether custom `CheckAtom` implementations have analogous contracts. No privacy loss has been demonstrated.
