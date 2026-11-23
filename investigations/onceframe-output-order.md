---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Partial
---

# OnceFrame output permutation and one-time consumption

## Invariant and threat model

An ordinary `OnceFrame.collect` must consume its private Polars plan at most once, including on failure, and return a row permutation rather than the original potentially sensitive order. The permutation should be independent of the row contents and uniformly sampled with cryptographically strong randomness in the configured build. A repeat evaluation or a content-dependent/fixed ordering would violate the examined property.

Scope: native Rust collect, Python collect through the Polars FFI shim, OpenDP's vector shuffler and RNG adapter, at upstream `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` on `main`. This is **not** an audit of all Polars DP query semantics, pre-shuffle order-sensitive computations, Rust/FFI pointer safety in general, or the honest-but-curious `lazy()` bypass.

## Affected symbols and source audits

- [Rust OnceFrame and `shuffle_dataframe`](../source/rust/src/polars/mod.rs.md): [commit-pinned source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/mod.rs#L503).
- [OpenDP `Shuffle` and RNG adapter](../source/rust/src/traits/samplers/mod.rs.md): [commit-pinned source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/mod.rs#L20).
- [Polars shuffle FFI wrapper](../source/rust/src/data/ffi/polars.rs.md): [commit-pinned source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/data/ffi/polars.rs#L101).
- [Python `OnceFrame.collect`](../source/python/src/opendp/extras/polars/__init__.py.md): [commit-pinned source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/extras/polars/__init__.py#L627).

## Reasoning and evidence

1. **Permutation construction.** `shuffle_dataframe` checks that frame height fits `IdxSize`, reserves a vector, creates exactly indices `0..n`, invokes `indices.shuffle()?`, then calls `dataframe.take(...)`. Given correct `take` semantics, no rows are introduced or omitted, including for n = 0 or 1.
2. **Entropy source.** `Shuffle for Vec<T>` uses `rand::SliceRandom` with `GeneratorOpenDP`. Its `fill_bytes` delegates to OpenSSL `RAND_priv_bytes` when `use-openssl` is enabled (a default Rust feature per [Cargo](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/Cargo.toml#L115)). Entropy errors are retained and returned. The non-OpenSSL path uses `rand::thread_rng` and is explicitly described in source as non-secure, so the strongest randomness claim is conditional.
3. **One-shot collection.** Rust's non-FFI `OnceFrame` takes its plan from `Option` before Polars collection, and the internal `TakeLazyFrame` also consumes it. The FFI build refuses Rust-side external collection; Python `collect` calls consuming `_take_lazy`, collects with common-subexpression elimination disabled, and invokes the same Rust shuffler via FFI. The Rust FFI wrapper downcasts and clones a DataFrame, then delegates to `shuffle_dataframe`.
4. **Existing tests.** Upstream has a [native schema-and-row-preservation test](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/test.rs#L86) and [Python tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/test/test_polars.py#L415) for failures, lengths 0/1/10, and Enum preservation. These tests were **read but not executed** in this session. The RNG's permutation distribution and feature-matrix behavior were not independently tested.
5. **Upstream history.** [PR #3240](https://github.com/opendp/opendp/pull/3240) merged 2026-11-18 and replaced noncryptographic Polars sampling with the indexed shuffle while consuming failed collections. Historical [issue #1826](https://github.com/opendp/opendp/issues/1826) is closed. [PR #3234](https://github.com/opendp/opendp/pull/3234) describes itself as superseded; it was not treated as a current fix.

The static code paths are consistent with the stated invariant under the noted assumptions. This is a conditional argument, **not** proof of uniform cryptographic sampling or complete privacy correctness.

## Findings

**No new defect identified within this scope.** Verification: static source review only. No candidate issue was created. The relevant merged fix is present in upstream `main` at the reviewed SHA.

## Unresolved questions

- Execute `cargo test` with Polars plus default OpenSSL features and the relevant Python Polars tests. This workspace was inspected through GitHub, so these tests were not run locally.
- Verify the exact `rand 0.7.3` `SliceRandom` sampling algorithm and its assumptions, including generator-error paths.
- Exercise `DataFrame::take` against null, Enum, multiple chunks, and large heights, and verify row/schema preservation.
- Confirm build-policy expectations when `use-openssl` is disabled; the source documents its fallback as non-secure.
- The documented honest-but-curious `lazy()` escape hatch requires the analyst to avoid order-sensitive computation and repeated evaluation; this audit does not certify arbitrary analyst behavior.
