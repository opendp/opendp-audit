---
schema_version: 1
source: rust/src/polars/preflight/mod.rs
updated: 2026-11-23
---

# `rust/src/polars/preflight/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated serialized-Polars-plan preflight at upstream `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. Checked versioned envelope validation, tree traversal dispatch, plugin rebinding and the untrusted Python/FFI entrypoint. This is a **bounded** review of preflight control flow, not a comprehensive deserializer security assessment.
- **Invariant:** Untrusted plan bytes must be checked before Polars deserializes them. Rewritten plugin bytes must be returned only after successful structural checks, and supported plugins must be rebound to the server-supplied library path.
- **Assumptions:** Polars' pinned `py-1.36.1` serialization conforms to its `SerializableDslPlan` arena schema; the Python API uses the default `trusted=False` for untrusted input, and downstream privacy constructors validate semantic behavior after deserialization. The audit does not establish safety of arbitrary embedded DataFrame buffers or test all custom plugin payload forms.
- **Pinned sources:** [OpenDP preflight](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/preflight/mod.rs), [subset traversal](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/preflight/subset.rs), [entrypoint](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/polars.rs), [pinned Polars versioned serializer](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-plan/src/dsl/serializable_plan.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `polars::preflight::inspect_serialized_dslplan` | security/versioned-plan-gate | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Header and arena inspection](#header-and-arena-inspection) |
| `polars::preflight::sanitize_serialized_dslplan` | security/validated-plan-rewrite | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Conditional serialization](#conditional-serialization) |
| `polars::preflight::rebind_plugin` | security/plugin-library-rebinding | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Plugin restrictions](#plugin-restrictions) |

## Analysis

### Header and arena inspection

`inspect_serialized_dslplan` rejects missing/truncated magic/version/schema, determines a reference header using `DslPlan::default().serialize_versioned` from the compiled Polars build, and refuses bytes that do not match. It then parses one MessagePack value and rejects trailing bytes. For `trusted=false` it delegates to `subset::check_operations`, which checks each slot in the serialized `dsl_plans` arena. The embedded-plan coverage is not based on an assumption that `IR` contains an inline DSL: in pinned Polars it serializes as an **arena key**. See the [cross-file investigation](../../../../../investigations/polars-preflight-plan-arena-validation.md).

At the public FFI entrypoint, `opendp_data__sanitize_polars_plan` rejects invalid buffer pointers/bit lengths and invokes this preflight. In Python, `LazyFrameQuery.deserialize` snapshots incoming bytes, calls `sanitize_polars_plan` with the default `trusted=False` and only then calls `polars.LazyFrame.deserialize`. That ordering is source-verified for this API; other direct calls to Polars are outside the reviewed boundary.

### Conditional serialization

`sanitize_serialized_dslplan` rejects an empty server library path and runs the inspection **before** returning the bytes. If nothing was rebound, it returns the input buffer copied into a new `Vec<u8>`; otherwise it retains the validated version header and re-encodes the inspected MessagePack tree. A failed inspection cannot produce a sanitized output. The review did not execute a Polars binary and did not establish semantic equivalence for every permitted payload through encode/decode: hence `Partial`.

### Plugin restrictions

For an untrusted `FfiPlugin` tag, `rebind_plugin` checks a restricted symbol set, requires a well-formed field collection and empty `kwargs`, and substitutes the trusted library path. The subset visitor subsequently checks duplicate fields in the plugin map. For a trusted plan, plugin rebinding is selective while operation restrictions are intentionally skipped. The symbol allowlist and empty-keyword argument checks are source-verified, but their completeness relative to all upstream Polars plugin code paths is **not** independently proved.

### Evidence and limitations

Static inspection of OpenDP and its pinned Polars serializer, plus reading [OpenDP's existing preflight tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/preflight/tests.rs). No native preflight tests were executed during this review. The existing tests inspect unsupported operations, unreachable arena nodes, duplicate fields, callback-bearing dtype expressions and header failures; these were read, not rerun.

The original eager-deserialization concern was tracked as [upstream #3185](https://github.com/opendp/opendp/issues/3185), addressed by merged [PR #3186](https://github.com/opendp/opendp/pull/3186). Neither fact proves the entire deserializer safe; an independent review of DataFrame payload formats and deserializer-side callback behavior remains outside this unit.

## Next checks

- Run native preflight regressions against the pinned Polars version, especially all applicable serialization tags and byte-buffer corner cases.
- Audit embedded serialized DataFrame payloads and Polars callback deserialization separately; do not infer safety from plan-node allowlisting alone.
- Update this coverage if the Polars version or serialized schema changes.
