---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Untrusted Polars plan preflight: arena coverage and deserialization ordering

## Invariant and threat model

Client-supplied serialized Polars plans can contain operations or callback-bearing objects that must not reach deserialization before the security preflight. This investigation narrowly asks whether a nested plan is omitted from screening because a serialization wrapper uses an indirect reference, and whether OpenDP's `LazyFrameQuery.deserialize` passes through preflight before Polars. A counterexample would be a valid serialized plan node ignored by the allowlist and subsequently deserialized under `trusted=False`.

This is **not** a comprehensive guarantee about arbitrary DataFrame payloads, supported operation options, or direct Polars APIs. Security-sensitive follow-up must honor [OpenDP's coordinated disclosure policy](https://github.com/opendp/opendp/blob/main/SECURITY.md).

## Affected symbols and source audits

- [Preflight module source report](../source/rust/src/polars/preflight/mod.rs.md) — `sanitize_serialized_dslplan` and `inspect_serialized_dslplan`.
- [Untrusted subset source report](../source/rust/src/polars/preflight/subset.rs.md) — `check_operations`, `plan` and `visit`.
- Pinned OpenDP [FFI boundary](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/polars.rs) and [Python `LazyFrameQuery.deserialize`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/extras/polars/__init__.py).
- Exact dependency: Polars [`SerializableDslPlan` at tag `py-1.36.1`](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-plan/src/dsl/serializable_plan.rs), pinned by the reviewed [OpenDP Cargo manifest](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/Cargo.toml).

## Reasoning and evidence

1. The versioned schema is a root map holding a `dsl_plans` arena, not a recursive inline serialization of the full DSL tree. Polars' `DP::IR` conversion inserts its child DSL plan into the same arena and records the resulting `DslPlanKey`. The deserializer resolves that key later.
2. OpenDP's untrusted `check_operations` checks every non-nil arena slot's plan variant, including unreachable slots. `plan` recognizes only selected tags; disallowed variants are rejected. The inert handling of an `IR` node's reference is compatible with this design; its target is still covered by the separate slot traversal. Thus **no missing plan-node validation was identified on this indirect-reference path**.
3. `inspect_serialized_dslplan` checks the compiled schema header, parses exactly one MessagePack value, and invokes `check_operations` before returning a sanitized byte vector. The FFI entrypoint calls this sanitizer. Python `LazyFrameQuery.deserialize` snapshots input bytes, sanitizes them with default `trusted=False`, and then delegates to `polars.LazyFrame.deserialize`. The reviewed path therefore orders validation before deserialization.
4. Upstream [`checks_unreachable_plan_nodes` test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/preflight/tests.rs) covers rejection of a prohibited operation in a disconnected arena slot, and other existing tests cover unsupported operations, nested dtype expressions, duplicate MessagePack fields and malformed headers. **Those tests were read, not executed.**

The preflight was originally introduced after [OpenDP issue #3185](https://github.com/opendp/opendp/issues/3185), addressed by [merged PR #3186](https://github.com/opendp/opendp/pull/3186). That historical fix is separate from an independent completeness proof. This review identifies no new exploit or confirmed defect within its **arena/ordering** scope.

## Findings

- **Bounded negative finding:** A serialization wrapper represented by an `IR` arena key does not evade per-slot validation under the pinned Polars serialization schema.
- **Bounded negative finding:** In the reviewed Python API, untrusted plan bytes pass through OpenDP's preflight prior to Polars deserialization.
- **Not established:** Security of every allowed inert option, arbitrary embedded serialized DataFrames, all callback-bearing forms, or external callers that bypass OpenDP's API. These are unreviewed obligations, not confirmed findings.

## Unresolved questions

- Verify the full Polars schema against each callback-bearing field (not only plan and dtype expressions), paying special attention after changes in the pinned version.
- Assess the serialization and deserialization behavior of embedded DataFrame payloads separately.
- Execute pinned native preflight tests and host-language adversarial-input regressions as a separate, narrowly controlled audit.
