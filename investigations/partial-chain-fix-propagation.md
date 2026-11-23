---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Audited
---

# Partial chaining: fixing input spaces before function/map composition

## Scope and invariant

This investigation covers the 12 overloaded shifts in [the `partials` implementation](../source/rust/src/combinators/chain/shr/partials.rs.md), focusing on **deferred fixing order and fallible constructor propagation**, not mathematical proofs of arbitrary user callbacks. Upstream source is pinned to `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. The `partials` feature is enabled by default in `rust/Cargo.toml` and the local audit did not use a deprecated API.

The key rule is that fixing a partial on the right of a concrete or already-fixed transformation uses the *left output* domain and metric; fixing a partial on the left uses the *chain input* domain and metric. On success, the chain's function and distance maps must match the eager `make_chain_tt`, `make_chain_mt` or `make_chain_pm` implementations. On a failed left stage, no downstream partial constructor should run.

## Cross-file trace

- [`PartialTransformation::new/fix` and `PartialMeasurement::new/fix`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs) are `FnOnce(DI, MI) -> Fallible<T>` wrappers. They defer constructor evaluation until the `fix` call and consume the partial exactly once. No argument cloning or map evaluation occurs inside `fix` itself.
- [`Shr` partial overloads](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/shr/partials.rs): four transformation-to-transformation overloads, two space-to-partial overloads, four transformation-to-measurement overloads, and two measurement-to-postprocessing overloads. These call the correct eager chain constructor after fixing the required operands.
- The `PartialTransformation >> PartialMeasurement` overload first fixes the left transformation, then invokes `transformation >> rhs`, which resolves through the `Transformation >> PartialMeasurement` overload. This in turn fixes the right measurement with the transformation's resolved output space and calls `make_chain_mt`; there is no recursive re-fixing of the left stage.
- In `Fallible<Transformation> >> PartialTransformation` and `Fallible<Transformation> >> PartialMeasurement`, `let lhs = self?;` prevents the deferred right constructor from running when the prior stage failed.
- The `PartialMeasurement >> Transformation` overload calls `make_chain_pm(&rhs.function, &lhs)` after fixing the left. It intentionally ignores `rhs`'s domain and stability map because this is noninteractive postprocessing of the measurement release. Its safety relies on the postprocessing's data-independence and the release being valid for the function.
- [Eager chaining](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/mod.rs) checks intermediate domains and metrics for `tt`/`mt`; [core map chaining](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs) preserves left-to-right function/map order. The older [chain investigation](chain-composition-contracts.md) covers the eager paths separately.

## Executed verification

**Actually executed:** A standalone Python source-model script at `partial_chain_model_check.py` (local-only, not an upstream test) verified all 12 overload stage traces, checked short-circuit behavior at every modeled fallible stage and both fallible-left overloads, and compared 5,000 deterministic algebraic composition cases. All checks passed. This is a model of the **source control flow** and does not exercise OpenDP's Rust trait dispatch or runtime behavior. Separately, the audit repository's schema validator and eight validator unit tests were executed locally.

**Inspected but not executed:** Rust test `tests_shr::test_shr` in [the source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/shr/partials.rs), plus the `FnOnce` implementations and the concrete `make_chain_*` functions.

## Conclusion and remaining proof obligations

**Negative finding within the scoped property:** No incorrect construction order or error propagation was identified in the feature-gated partial overloads. This **does not certify arbitrary user-supplied partial factories**: `PartialTransformation::new`/`PartialMeasurement::new` accept arbitrary `FnOnce` closures that could return inconsistent input metadata or perform side effects. Their semantic correctness is a caller obligation, not a demonstrated library defect in the generator-backed constructors.

No new candidate bug issue is warranted for this scope. Upstream and audit issues/PRs were checked for overlapping partial-chaining work; none reported the same property. Native Rust feature-enabled tests, generated `then_*` construction behavior, and custom intermediate domain equality remain follow-ups.
