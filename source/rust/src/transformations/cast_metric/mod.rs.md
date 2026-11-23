---
schema_version: 1
source: rust/src/transformations/cast_metric/mod.rs
updated: 2026-11-22
---

# `rust/src/transformations/cast_metric/mod.rs`

## Scope and assumptions

- **Scope:** The non-deprecated `make_metric_unbounded` identity cast from `ChangeOneDistance` to `SymmetricDistance` or `HammingDistance` to `InsertDeleteDistance`. Specifically, verify that its `u32` stability map remains a conservative bound at every representable input distance. Inspect the reverse `make_metric_bounded` map for context, without claiming a full audit of the random ordering or unordered metric casts.
- **Invariant:** Given an equal-length dataset domain of known size, every output pair of `make_metric_unbounded` must be no farther apart than `map(d_in)` whenever the input pair is at most `d_in` apart. Its map must not silently wrap or panic on an otherwise valid `u32` argument.
- **Assumptions:** Supported `VectorDomain` with fixed size, event-level integer distance `IntDistance = u32`, and conventional Rust arithmetic behavior (unchecked release multiplication wraps modulo `2^32`; checked multiplication panics on overflow). The example uses a size-one domain, so no huge dataset allocation is necessary.
- **Pinned upstream:** [Metric cast source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/cast_metric/mod.rs), [metric definitions](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/mod.rs), [`StabilityMap` and `Transformation::map`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs), [FFI constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/cast_metric/ffi.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_metric_unbounded` | privacy/stability-bound | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Overflow invalidates the bound](#overflow-invalidates-the-bound) |
| `make_metric_unbounded` | correctness/overflow-handling | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Checked versus unchecked builds](#checked-versus-unchecked-builds) |
| `make_metric_bounded` | privacy/stability-bound | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Reverse cast](#reverse-cast) |

## Analysis

### Overflow invalidates the bound

The constructor requires `input_domain.get_size()?` but puts no condition on the magnitude of a future stability-map query `d_in`. It returns the identity function and `StabilityMap::new(|d_in| d_in * 2)`. `MI::Distance` and `MI::UnboundedMetric::Distance` are both `IntDistance = u32`. Unlike the shared `StabilityMap::new_from_constant`, `StabilityMap::new` wraps this infallible closure without conservative multiplication or overflow checking. `Transformation::map(&d_in)` calls the closure directly, without restricting `d_in` to the domain's maximum possible distance.

Take `VectorDomain::new(AtomDomain::<i32>::default()).with_size(1)` and either of the supported metric pairs. Let `x = [0]` and `x' = [1]`. The **input** `ChangeOneDistance` or `HammingDistance` is exactly 1, while the **output** `SymmetricDistance` or `InsertDeleteDistance` of the unmodified vectors is exactly 2. Therefore a valid stability bound for **any** `d_in >= 1` must be at least 2. At the valid query `d_in = 2_147_483_648u32 = 2^31`, the mapping attempts `2 * d_in = 2^32`, which cannot be represented as `u32`; unchecked arithmetic yields **0**, incorrectly claiming zero output distance for these neighboring datasets. This is a real violation of the stability map's documented universal upper-bound contract, not just a large-domain edge case: the input domain in the witness has **one** record.

A model can produce a corresponding downstream privacy-accounting underestimate when the cast is chained with any measurement whose privacy map returns zero on intermediate distance zero. The audit does **not** claim a demonstrated exploit in a concrete production mechanism or an ordinary-sized privacy-budget query. See the [investigation](../../../../../investigations/metric-unbounded-cast-overflow.md) and [audit defect #27](https://github.com/opendp/opendp-audit/issues/27).

### Checked versus unchecked builds

On ordinary release builds with disabled overflow checks, `d_in * 2` uses wrapping integer multiplication, so `map(&2_147_483_648)` yields `Ok(0)`. On overflow-checked builds, the same multiplication panics while evaluating a `Fallible` map instead of returning an error. In either mode, the code does not provide a sound, fallible result across its complete `u32` input space. No explicit Cargo profile enabling release overflow checks was identified in `rust/Cargo.toml`.

**Executed:** A standalone Python reference model checked `u32` modulo arithmetic at both sides of `2^31`, a non-vacuous size-one counterexample for **both** metric pairs, and all binary vector pairs up to length four against the exact `2 * d` metric relation. All model tests passed. **Not executed:** Compiled OpenDP Rust, native debug/release map calls, or FFI executions. See [reproduction tests](../../../../../tools/tests/test_metric_unbounded_cast_overflow.py).

### Reverse cast

`make_metric_bounded` also returns an identity function but maps from symmetric distance to change-one distance by `d_in / 2`. The constructor requires a sized domain, and a pair of equal-length vectors has even symmetric distance, exactly twice its change-one distance. Under that assumption, floor division by two is conservative for the bounded metric at all valid `u32` inputs, including odd thresholds. This is a **bounded source-level observation**, not a full audit of every supported dynamic domain and its `IsSizedDomain` semantics, so its status remains `Partial`.

## Disposition and next checks

- **Finding:** Source-confirmed stability-bound undercount for extreme but representable map inputs in unchecked builds, with a corresponding fallibility/panic defect in checked builds. Impact is **potential privacy-accounting unsoundness** when this map is composed, not a demonstrated end-to-end DP leak. The offending path is reachable with a size-one domain.
- **Upstream disposition:** **Unreported** at the pinned revision, after checking audit/upstream issues and open pull requests for an equivalent fix. Existing historical [PR #465](https://github.com/opendp/opendp/pull/465) introduced metric casters but does not address the current multiplication. Tracked as [audit candidate #27](https://github.com/opendp/opendp-audit/issues/27); coordination task [#25](https://github.com/opendp/opendp-audit/issues/25).
- **Decisive regression:** In compiled Rust debug and release builds, call the `ChangeOneDistance` and `HammingDistance` casts on size-one domains, assert `map(&1) == 2`, and ensure `map(&2_147_483_648)` either returns a valid conservative result or returns `Err` without panicking or yielding `Ok(0)`.
- **Suggested remediation:** Use an explicitly fallible checked/outward multiplication; `StabilityMap::new_from_constant(2)` already applies `InfCast`/`InfMul` and is one candidate if its trait bounds fit. Do not silently saturate or wrap an unrepresentable bound.
