---
schema_version: 1
source: rust/src/measurements/make_private_expr/expr_postprocess/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/make_private_expr/expr_postprocess/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated `make_expr_postprocess` and `match_postprocess`: privacy composition before alias/binary operators, nonempty child plans, optional fills and shared logical-plan lineage.
- **Invariants:** Every private operand is charged before postprocessing; absent fills are not fabricated; only valid arities are constructed; the final expression runs on its intended private plan.
- **Assumptions:** Each child measurement satisfies its privacy map, output randomization satisfies the nonadaptive composition theorem, and the postprocessor is a deterministic function of already-private outputs. Child plans are expected to originate from the same input logical plan, but this is not checked locally.
- **Pinned code:** [Expression postprocessing](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_postprocess/mod.rs), [nonadaptive composition](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/non_adaptive/mod.rs), [`ExprPlan`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/expr/mod.rs), and [native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_postprocess/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::make_private_expr::expr_postprocess::make_expr_postprocess` | privacy/nonadaptive-postprocessing-composition | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file investigation](../../../../../../investigations/polars-private-postprocess-composition.md) |
| `measurements::make_private_expr::expr_postprocess::make_expr_postprocess` | correctness/nonempty-plan-guard | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Guard and lineage](#nonempty-guard-and-plan-lineage) |
| `measurements::make_private_expr::expr_postprocess::make_expr_postprocess` | correctness/missing-group-fill-propagation | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Fill semantics](#optional-fills-and-arity) |
| `measurements::make_private_expr::expr_postprocess::match_postprocess` | correctness/alias-binary-arity | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Fill semantics](#optional-fills-and-arity) |

## Analysis

### Composed privacy maps precede postprocessing

Each input expression is independently constructed as a private measurement for the same domain, metric and measure. The function calls `make_composition(m_exprs)`, which checks equal input spaces, evaluates each child map and composes costs using `CompositionMeasure::compose`. The final `Measurement::new` copies `m_comp.privacy_map.clone()` rather than a zero-cost map. The operator is applied to output expression ASTs **after** that charged composition.

The independent [exact-rational model](../../../../../../tools/tests/test_polars_private_postprocess_model.py) enumerates 81 pairs of binary mechanism laws and all 16 deterministic binary maps of their four joint outcomes: 1,296 joint/postprocessed laws and 5,184 exact bidirectional mass inequalities, none exceeding the product of the two component likelihood-ratio bounds. It assumes independent valid child laws and **does not execute OpenDP Rust**, test arbitrary approximate/zCDP maps or prove the compositor implementation correct. Privacy coverage therefore remains `Partial`.

### Nonempty guard and plan lineage

The code reads `plans[0].plan`, but the upstream `make_composition` constructor rejects an empty child-measurement vector, and a successful evaluation yields one entry per child. Thus the apparent empty-vector indexing panic is not reachable through the supported constructor. Existing Rust tests of aliases and binary expressions were inspected, not run.

The implementation retains only the **first** child's logical plan without comparing the other plans. Ordinary `Function::from_expr` and `Function::then_expr` / `ExprPlan::then` paths preserve the input logical plan, but exhaustive common-plan invariance across all current/future `PrivateExpr` implementations was **not proven**. This is a residual contract dependency, **not** a confirmed reachable defect.

### Optional fills and arity

The code collects child `Option<Expr>` fills into `Option<Vec<Expr>>`. The combined fill is present **only when every component fill is present**, then passes through the same postprocessor as the released expression ASTs. When any fill is absent, it reports `None` rather than fabricating a missing-group value. The independent model covers all 126 presence patterns for one to six inputs, including alias and binary transformations.

The matcher constructs a one-child vector for `Expr::Alias` and a two-child vector for `Expr::BinaryExpr`, matching their later fixed-length `try_from`/`expect` unpacking. No mismatched arity or empty input is created by those two branches.

## Findings

**No confirmed defect identified** in nonadaptive privacy charging, nonempty rejection, conservative fill propagation or matched postprocessor arity under the stated preconditions. Complete Rust/Polars runtime behavior and arbitrary input-plan lineage remain **Partial**.

## Next checks

- Run compiled Polars tests combining distinct private expression plugins under binary postprocessing and public-key missing-group joins.
- Consider an explicit shared-plan check or document the lineage invariant for future `PrivateExpr` implementors; first demonstrate whether mismatched plans can actually be produced.
