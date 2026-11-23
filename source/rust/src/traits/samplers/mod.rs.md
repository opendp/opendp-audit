---
schema_version: 1
source: rust/src/traits/samplers/mod.rs
updated: 2026-11-22
---

# `rust/src/traits/samplers/mod.rs`

## Scope and assumptions

Reviewed `Shuffle` and `GeneratorOpenDP` as used by OnceFrame's index vector. The uniform-permutation argument assumes unbiased `rand::SliceRandom` index selection and independent random bytes. The default build enables `use-openssl`. [Pinned sampler source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/mod.rs#L1); [pinned Cargo features](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/Cargo.toml#L115).

This report covers only the declared properties at upstream commit `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. The cross-file argument and its limits are in [the OnceFrame investigation](../../../../../investigations/onceframe-output-order.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `traits::samplers::Shuffle::shuffle<Vec<T>>` | privacy/uniform-output-permutation | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file evidence](../../../../../investigations/onceframe-output-order.md) — Uses `rand::SliceRandom::shuffle` with OpenDP's RNG adapter. |
| `traits::samplers::GeneratorOpenDP::fill_bytes` | privacy/entropy-source | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file evidence](../../../../../investigations/onceframe-output-order.md) — Entropy errors are stored and returned after shuffling. |

## Analysis

The `Vec<T>` implementation invokes `SliceRandom::shuffle`, a Fisher–Yates-style shuffle over the index vector. Its RNG adapter calls `fill_bytes`; with default `use-openssl`, it calls OpenSSL `RAND_priv_bytes` and records failure rather than claiming successful output. The build without that feature instead uses `rand::thread_rng`, which this file explicitly documents as non-secure: the CSPRNG claim should be scoped to a suitably configured build. No statistical or dependency-source-level verification was executed. [Source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/mod.rs#L20).

**Execution status:** Code and upstream tests were inspected through GitHub; no Rust or Python test suite was executed in this audit session. Therefore coverage remains **Partial**.

## Next checks

Verify the linked `rand` version's bounded-index sampler and test entropy-error propagation. Test security assumptions for builds disabling `use-openssl`.
