---
schema_version: 1
source: rust/src/polars/preflight/subset.rs
updated: 2026-11-23
---

# `rust/src/polars/preflight/subset.rs`

## Scope and assumptions

- **Scope:** Restricted untrusted serialized DSL-plan vocabulary and its traversal of the `dsl_plans` arena, nested expression/function/dtype roles and tagged operations; specifically the safety of treating `IR` references as inert.
- **Invariant:** All serialized plan-node slots are checked before deserialization, including nodes not reachable from the root. Prohibited plan and expression tags cannot hide in a nested `DslPlan` behind an `IR` reference.
- **Assumptions:** Pinned Polars `py-1.36.1` serializes all nested `DslPlan` children into the `dsl_plans` arena with keys, and the untrusted code path invokes `check_operations` on the entire versioned MessagePack object. The correctness of every permitted operation and callback-free option payload is not covered.
- **Pinned sources:** [OpenDP traversal](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/preflight/subset.rs), [Polars arena format](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-plan/src/dsl/serializable_plan.rs), [OpenDP tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/preflight/tests.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `polars::preflight::subset::check_operations` | security/plan-arena-coverage | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Entire arena coverage](#entire-arena-coverage) |
| `polars::preflight::subset::plan` | security/ir-reference-coverage | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Inert plan references](#inert-plan-references) |
| `polars::preflight::subset::visit` | security/nested-operation-routing | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Nested expressions and limits](#nested-expressions-and-limits) |

## Analysis

### Entire arena coverage

`check_operations` requires exactly three distinct top-level keys `root`, `dataframes`, and `dsl_plans`. The map visitor rejects duplicate/non-string map fields. `dsl_plans` is visited as `Arena`, which requires an array, whose non-nil slot values are maps with a `value` field visited as `Plan`. Every slot is inspected; the visitor does not follow only the top-level root key. Therefore even a disconnected plan slot with a prohibited variant is rejected by its `plan` handler.

The pinned serializer `SerializableDslPlan` stores one node per `dsl_plans` slot; `DslPlan::IR { dsl, .. }` becomes `SerializableDslPlanNode::IR { dsl: DslPlanKey, version }`. `dsl_plan_key` inserts the referenced node into that arena. Deserialization later resolves the key from the arena. This establishes the key relationship necessary for the above coverage claim within the pinned Polars schema. The existing upstream test `checks_unreachable_plan_nodes` specifically exercises a prohibited extra arena node.

### Inert plan references

`plan` treats `IR` and `DataFrameScan` fields as inert, recursively checking structural map shape/extensions rather than interpreting them as nested plans. For `IR` this **does not create an inline-plan bypass** in pinned Polars: the `dsl` field is a reference key, and its target plan is checked separately as an arena slot. `DataFrameScan` holds a serialized DataFrame reference and schema rather than a nested plan; validation of arbitrary DataFrame payload bytes is a **separate** security property and is not established here.

### Nested expressions and limits

Supported plan tags route known expression-bearing fields to `Expr`/`Exprs` roles. `expr` explicitly follows permitted expression variants, `Function` delegates to a function allowlist, `Cast` delegates dtype expressions to `dtype`, and `dtype::OfExpr` returns to `Expr`. Unsupported tags are rejected. Every visited map checks duplicate keys, and extension values are rejected in the inert visitor. The review traced representative branches and inspected the vocabulary but did **not** prove every inert option payload harmless under Polars' actual deserializer. Therefore the broad nested-operation-routing property remains `Partial`.

**Evidence type:** Static inspection only, pinned to the SHA above and Polars tag. Existing native tests read, not executed in this audit.

## Next checks

- Independently enumerate every callback-bearing polymorphic field in the pinned Polars serialization schema and verify that permitted inert subtrees cannot contain one.
- Check serialized DataFrame payload format and decoder behavior separately.
- Execute native tests for nested expressions, extra arena slots, malformed map fields and plugin rewriting after Polars upgrades. See [cross-file investigation](../../../../../investigations/polars-preflight-plan-arena-validation.md).
