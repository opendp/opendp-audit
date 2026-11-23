---
schema_version: 1
source: rust/src/measurements/make_private_expr/expr_len/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/make_private_expr/expr_len/mod.rs`

## Scope and assumptions

Reviewed non-deprecated `make_expr_private_len` at upstream revision `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. Its zero-privacy map is intended **only** for an exact `Expr::Len` under the multiverse `Invariant::Lengths`: all permitted neighboring datasets have the same grouping keys and group lengths. This review checks the dispatch guard, output expression, fill semantics and zero map. It does not execute compiled OpenDP/Polars or certify how an external caller establishes that multiverse invariant.

- [Pinned Rust implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_len/mod.rs), [upstream native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_len/test.rs), [dispatch](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/mod.rs).
- [Definition of `Invariant::Lengths`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/frame/mod.rs), [independent investigation](../../../../../../investigations/polars-public-length-and-literal-privacy.md), [reference model](../../../../../../tools/tests/test_polars_privacy_free_expr_model.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_expr_private_len` | privacy/public-group-length-zero-cost | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Privacy argument](#privacy-argument), [independent finite model](../../../../../../tools/tests/test_polars_privacy_free_expr_model.py) |
| `make_expr_private_len` | correctness/length-invariant-guard | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Constructor guard](#constructor-guard) |
| `make_expr_private_len` | privacy/end-to-end-grouped-release | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Limits of the zero-cost claim](#limits-of-the-zero-cost-claim) |

## Analysis

### Constructor guard

The constructor first matches the **exact** `Expr::Len` variant. It then requires an aggregation context and specifically checks `margin.invariant == Some(Invariant::Lengths)`; `Keys` or `None` is rejected. On success, the expression is `len()` with zero fill for an absent keyed result and `PrivacyMap::new(|_| MO::Distance::zero())`. No noise is added. The upstream Rust tests inspect successful public-length grouped execution and construction failure where lengths are not public; they were inspected, not executed in this pass.

### Privacy argument

Within `Invariant::Lengths`, both grouping keys and **per-key lengths** are identical across all admissible neighboring datasets, even if row values differ. Consequently the grouped output of `len()` is identical, and privacy loss is zero. The [independent Python model](../../../../../../tools/tests/test_polars_privacy_free_expr_model.py) enumerated **67,081** ordered pairs over 259 short datasets; **15,085** pairs had identical public group lengths, and all produced identical exact grouped lengths. This is an independent mathematical verification of the premise, not native Polars execution.

`Invariant::Keys` alone is insufficient: the grouped keys may be fixed while the number of rows in one group changes. The constructor correctly rejects this weaker premise.

### Limits of the zero-cost claim

`Invariant::Lengths` is a **multiverse/public-information assertion** supplied through input domain metadata, not proved by the `Margin::member` check on one individual frame. The privacy guarantee is conditional on the user/model's assertion being true for the full neighboring relation. A caller must not treat arbitrary private lengths as public simply by attaching the descriptor.

This measurement constructor has **no output `ExprDomain`**: it is distinct from the stable `make_expr_len` transformation's [incorrect grouped output `max_groups` (#78)](https://github.com/opendp/opendp-audit/issues/78). Neither this audit nor its model proves privacy for exposing previously private grouping keys elsewhere in a full query.

## Findings and next checks

No new defect in the exact-length constructor within its declared multiverse premise. Run the upstream Rust tests and additional native group-by cases with public lengths, null data, empty groups and honest-but-curious single-evaluation semantics. Overall end-to-end privacy coverage **Partial** because establishment of the public-length invariant and whole-query composition were not verified. [Coordination task #84](https://github.com/opendp/opendp-audit/issues/84).
