---
schema_version: 1
source: rust/src/combinators/chain/mod.rs
updated: 2026-11-22
---

# `rust/src/combinators/chain/mod.rs`

## Scope and assumptions

- **Reviewed invariant:** The three non-adaptive chaining constructors preserve function order, compose the correct stability/privacy maps, and propagate failure without evaluating the remaining component. Intermediate domains and metrics must match for transformation/measurement and transformation/transformation chains.
- **Properties:** `privacy/map-composition`, `correctness/stability-composition`, `privacy/postprocessing`.
- **Assumptions:** Component transformations and measurements already satisfy their individual stability and privacy contracts. Their maps are conservative and monotone on admissible distances. Postprocessing depends only on the private release and public context, not the original confidential input; callbacks are free of privacy-relevant side effects. These premises are not established simply by Rust trait bounds or arbitrary user callbacks.
- **Commit-pinned source:** [chaining constructors](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/mod.rs), [map and function combinators](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs), [FFI](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/ffi.rs), [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_chain_mt` | privacy/map-composition | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Proof obligations](../../../../../investigations/chain-composition-contracts.md) |
| `make_chain_tt` | correctness/stability-composition | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Proof obligations](../../../../../investigations/chain-composition-contracts.md) |
| `make_chain_pm` | privacy/postprocessing | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Data-processing argument](../../../../../investigations/chain-composition-contracts.md) |

## Analysis

### `make_chain_mt` — `privacy/map-composition`

**Conclusion:** No defect found for the stated component contracts. The constructor requires `transformation0.output_domain == measurement1.input_domain` and `transformation0.output_metric == measurement1.input_metric`, and builds `Function::make_chain(measurement1.function, transformation0.function)` with `PrivacyMap::make_chain(measurement1.privacy_map, transformation0.stability_map)`. For admissible input distance `d`, the advertised output is therefore `privacy1(stability0(d))`. `Measurement::new` rechecks input-domain/metric compatibility.

### `make_chain_tt` — `correctness/stability-composition`

**Conclusion:** The same intermediate compatibility checks precede `Function::make_chain(function1, function0)` and `StabilityMap::make_chain(stability1, stability0)`, giving `stability1(stability0(d))` for transformed input distance `d`. It retains the outer output domain and output metric.

### `make_chain_pm` — `privacy/postprocessing`

**Conclusion:** Composes the released value with `postprocess1`, retains the original `input_domain`, `input_metric`, `output_measure`, and **unmodified** `measurement0.privacy_map`. This is sound for postprocessing using only the release and public state. The fallible postprocessor's returned error remains an observable result of postprocessing; it does not invalidate data processing if it depends only on the release.

**Evidence:** The [cross-file investigation](../../../../../investigations/chain-composition-contracts.md) traces the underlying combinators, existing Rust unit/FFI tests, and a locally executed 10,000-case algebraic model plus four short-circuit cases. No compiled OpenDP tests were run for this audit. Both generic typed and FFI wrapper code were read; the wrappers invoke the same constructors.

**Limitations:** Generic constructors cannot prove the mathematical behavior of user-defined callbacks; monotonicity and purity are premises. Equality on domains and metrics is checked using their `PartialEq` implementations; no audit of every custom domain's equality implementation was performed. Interactive/adaptive composition and `partials` feature-gated chains are outside this scope. No claim is made that arbitrary side-effectful postprocessors are safe.

## Next checks

Run compiled Rust/FFI regression tests with mismatching intermediate metric or domain, and fallible inner/outer maps. Audit the feature-gated `partials` chaining constructors and custom domain equality separately. No new defect or issue is identified within the reviewed scope.
