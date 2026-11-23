---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Polars private postprocessing: composition and missing-group fills

## Invariant and threat model

A deterministic expression combining multiple private outputs must carry the composition of **all** operand privacy losses. A missing-group fill for a public key must only be emitted when every operand provides one. Projection or renaming of a private LazyFrame may reveal only previously released columns. This audit covers these properties in non-deprecated expression and LazyFrame postprocessing, not arbitrary untrusted query plans.

## Cross-file sources

- [Private expression postprocessor audit](../source/rust/src/measurements/make_private_expr/expr_postprocess/mod.rs.md) and [upstream implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_postprocess/mod.rs).
- [Private LazyFrame postprocessor audit](../source/rust/src/measurements/make_private_lazyframe/postprocess/mod.rs.md) and [upstream implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/postprocess/mod.rs).
- [Nonadaptive composition](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/non_adaptive/mod.rs), [postprocessing preserves privacy map](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/mod.rs), [`ExprPlan`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/expr/mod.rs), [projection options](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/options.rs).
- [Independent exact-rational model](../tools/tests/test_polars_private_postprocess_model.py) and [coordination task #72](https://github.com/opendp/opendp-audit/issues/72).

## Evidence and reasoning

### Composed privacy law

The expression constructor first calls `make_private` on every input expression, then `make_composition`, retaining its composed map after forming the output AST. With valid child mechanisms and independent randomness, a deterministic function of their joint outputs cannot enlarge their composed privacy loss.

The independent model tests **81** ordered configurations of two binary mechanisms with rational output probabilities `{1/4, 1/2, 3/4}` for each neighboring input. For each configuration, it evaluates all **16** deterministic binary postprocessors of the four joint outcomes, checking both likelihood-ratio directions for both output atoms. Total: **1,296 postprocessed distributions** and **5,184 exact inequalities**, with no violation. This is a finite mathematical model, **not native OpenDP execution**, an empirical sampler test, or a general proof for zCDP/approximate-DP floating-point arithmetic.

### Missing-group fills and nonempty safety

The constructor returns a combined optional fill only when **all** child fills are present (`Option::collect`). The model tests all **126** nonempty Boolean presence patterns of length one through six and confirms this all-or-nothing law. Alias and binary postprocessors apply the same operator to valid fills and original expressions. An absent fill is not treated as public zero and may lead an explicit public-key join to reject that expression.

Although the constructor accesses `plans[0]`, the dependency `make_composition` rejects an empty vector at construction; its successful execution returns the same number of outputs as components. The matched alias and binary constructors supply arities one and two respectively, so their fixed-length destructuring matches.

### LazyFrame projection and plan lineage

A LazyFrame Select/HStack postprocessor accepts only column-selection expressions and runs on the **rewritten private input**. Its `Measurement >> Function` chain retains the child privacy map. The explicit projection options require duplicate checks and broadcasting regardless of parallelism; the model covers all eight Boolean combinations, accepting two.

Expression postprocessing keeps the **first** child's `ExprPlan.plan`. Reviewed `Function::from_expr`, `Function::then_expr` and `ExprPlan::then` paths preserve the input plan, but the constructor has no general check of all child plans. No reachable mismatched-plan example was identified. This is a remaining **lineage precondition**, not a confirmed defect.

## Findings

**No confirmed defect** in the scoped nonadaptive composition, empty input rejection, all-or-nothing fill propagation, or standard projection-option checks. The broad privacy and plan-lineage claims remain `Partial` because native Polars execution, every child `PrivateExpr` implementation, and arbitrary optimizer rewrites were not verified.

## Next checks

- Run compiled OpenDP/Polars tests combining two different private expressions and a public key join with missing groups.
- Verify child-plan preservation for all current private-expression constructors and future plan rewrites.
- Test nested alias, selector and wildcard classification in the actual Polars planner.
