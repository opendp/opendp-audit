---
schema_version: 1
source: rust/src/core/mod.rs
updated: 2026-11-22
---

# `rust/src/core/mod.rs`

## Scope and assumptions

- **Audit scope:** Only `Function::make_chain`, `PrivacyMap::make_chain`, and `StabilityMap::make_chain` as used by `make_chain_mt`, `make_chain_tt`, and `make_chain_pm`; not the remaining core module.
- **Invariant:** Given fallible inner `f0` and outer `f1`, every composed function/map evaluates `f0` before `f1`, returns `f1(f0(input))` on success, and propagates an inner `Err` without invoking the outer callback. The privacy/stability bound remains conservative assuming valid monotone component maps.
- **Source:** [Reviewed core implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs), [chaining call sites](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `Function::make_chain` | correctness/fallible-composition | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Order and errors](../../../../investigations/chain-composition-contracts.md) |
| `PrivacyMap::make_chain` | privacy/map-composition | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Order and assumptions](../../../../investigations/chain-composition-contracts.md) |
| `StabilityMap::make_chain` | correctness/stability-composition | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Order and assumptions](../../../../investigations/chain-composition-contracts.md) |

## Analysis

**Conclusion:** Each implementation follows the order `outer(&inner(input)?)`. The `?` stops evaluation on an inner failure, and an outer failure propagates unchanged. The underlying `Arc` callbacks are cloned into a new composite callback, so a composed map does not borrow a temporary map. `Function::make_chain` chains releases, while `PrivacyMap` and `StabilityMap` chains act on the associated distance types.

**Privacy rationale:** When `s0` is a valid stability map and `p1` is a valid monotone privacy map, `p1(s0(d))` is a conservative privacy bound. Likewise, `s1(s0(d))` remains a conservative stability bound. This is a source-level composition argument conditional on the component contracts, not a proof that arbitrary callbacks passed to `new_fallible` are valid.

**Executed:** Python abstract-model checks covered 10,000 deterministic linear composition inputs and four failure short-circuit cases. These verify algebraic expectations, **not** compiled OpenDP or its Rust `Arc` implementations. Existing upstream unit and FFI tests cover normal invocation/map values but were not run in this audit.

**Limitations:** No independent audit of `MetricSpace`, arbitrary custom `Domain::PartialEq`, `Function` side effects, or the `partials` feature; see [investigation](../../../../investigations/chain-composition-contracts.md).

## Next checks

Run native Rust unit and FFI tests and add fallible inner-map/outer-map order tests. No finding within this narrowly scoped code path.
