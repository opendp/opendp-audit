---
schema_version: 1
source: rust/src/transformations/make_stable_lazyframe/h_stack/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_lazyframe/h_stack/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated `make_h_stack`, its grouping-certificate invalidation and identifier protection, including shared `is_identity`, `retain_margins`, `retain_bounds`, and `unaffected` helpers. Not a proof of arbitrary Polars expression evaluation.
- **Invariants:** A HStack replacement that can change a column invalidates all certificates depending on that column; an identity replacement preserves them. A new column does not disturb explicit unrelated grouping keys, but changes invalidate selectors whose dependencies are not enumerable. The identifier roots protected by `SymmetricIdDistance` cannot be overwritten.
- **Assumptions:** Polars `root_names()`, `has_multiple_outputs()` and expression output-name inference faithfully describe actual column dependencies; `Expr::Column(name)` and aliases back to the same output name are value identities. `ProjectionOptions` enforce duplicate name checking and broadcasting. All component expression transformations satisfy their contracts.
- **Pinned upstream:** [HStack implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/h_stack/mod.rs), [unit tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/h_stack/test.rs), [lineage helpers](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/mod.rs), [projection options](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/options.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_h_stack` | privacy/grouping-certificate-lineage | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file lineage analysis](../../../../../../investigations/polars-hstack-lineage.md) |
| `make_h_stack` | correctness/identifier-preservation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Identifier and options checks](../../../../../../investigations/polars-hstack-lineage.md) |

## Analysis

**Negative result within the scope:** The constructor requires canonical projection options (broadcasting and duplicate checks), stabilizes every newly written expression in `Context::RowByRow`, and rejects all output names that intersect the identifier expression's root names. It assembles output domains with last-writer precedence by column name. It marks each nonidentity expression's output column as changed, and retains margin/bound certificates only when their known roots are disjoint from changed columns. Selector-derived grouping certificates are conservatively discarded if any column changes. Unchanged `col("k")` or `col("k").alias("k")` remains an identity; replacing `k` from `x` invalidates certificates based on `k`; introducing unrelated `new` preserves explicit `k` grouping.

**Executed:** The independent standard-library [model test](../../../../../../tools/tests/test_hstack_lineage_model.py) passed 1,280 exhaustive explicit-root/selector combinations and 20,000 deterministic randomized replacement/dependency cases, plus name-protection and new-column checks. This tests the **source's control-flow/set semantics**, not compiled OpenDP or Polars. Existing upstream Rust tests were inspected but not executed.

**Limitations:** This cannot establish that Polars's `meta().root_names()` and `has_multiple_outputs()` cover every exotic expression, including selectors and optimizer rewrites; native Rust/Polars execution and formal proof of identifier semantics remain outstanding. In particular, the source relies on the identifier's roots being available from `meta()` and tests do not cover every complex identifier expression. For this reason both properties remain **Partial** rather than claiming universal privacy soundness. No distinct bug was found or filed for this scope.

## Next checks

Run feature-enabled compiled Rust/Polars tests for alias chains, selector expressions, computed identifier roots, and HStack overwrites. Check domain membership and actual grouping distances after optimizer rewriting before changing the status of either property.
