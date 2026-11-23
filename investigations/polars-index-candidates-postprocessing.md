---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Public candidate indexing after private Polars quantile selection

## Invariant and threat model

An index sampled with a valid differential-privacy guarantee may be mapped to a fixed, public candidate series without increasing privacy loss. The plugin must not accidentally evaluate unreleased source data during lookup. Invalid indices or schema errors should depend only on the already-private index output and the public candidate series, not directly on private input. This review does **not** attempt to establish the upstream noisy-max privacy theorem.

## Affected symbols and source audits

- [Index candidate source audit](../source/rust/src/measurements/make_private_expr/expr_index_candidates/mod.rs.md), [pinned Rust code](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_index_candidates/mod.rs).
- [Private quantile caller](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_dp_quantile/mod.rs), [private noisy-max index](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_noisy_max/mod.rs), and [measurement postprocessing composition](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/mod.rs).
- [Finite reference model](../tools/tests/test_index_candidates_postprocessing_model.py) and [upstream native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_index_candidates/test.rs).

## Reasoning and evidence

The private-expression dispatcher recognizes the `IndexCandidatesShim`; the matcher insists on a public literal candidates `Series`. It calls the index-producing measurement before adding the replacement plugin. The `m_prior >> Function::then_expr(...)` composition is implemented as `make_chain_pm` and copies `m_prior.privacy_map` unchanged. The stored public series and the input index column are the only runtime inputs to `index_candidates_udf`; the plugin does not receive the original private dataframe.

The output type is derived from the candidates `Series`. At runtime, selecting with a `UInt32` index returns that public candidate value, and a failed `take` cannot reveal anything except a deterministic property of the already DP-produced index and public series. In `dp_quantile` a public median is extracted from the candidates, and missing or empty candidates are rejected in that caller. The normal index producer is a private noisy-max of an array of candidate scores. This review did not prove all constraints required for every possible custom index producer or every Polars optimizer transformation.

**Executed:** Six dependency-free Python tests including 729 finite rational distribution pairs multiplied by three candidate mappings, exhaustive short in-range index tuples, and explicit invalid-index behavior. For all examined mappings the maximal output probability ratio did not exceed the input ratio, including when candidate names repeated. These calculations are **not native Rust or Polars executions**; they support only a bounded postprocessing argument.

## Findings

**Negative within scope:** No new flaw in privacy-map propagation or public-candidate indexing was identified, and no candidate defect issue is warranted. The generic matcher does not reject an empty candidate series, but the `dp_quantile` caller does, and any resulting lookup error on a different caller is postprocessing of its private index. This possible usability edge is not characterized as a confirmed defect without a concrete supported failing caller. Upstream issue and PR searches found no equivalent outstanding report; no upstream modification was made.

## Unresolved questions

- Execute actual OpenDP Rust with Polars to confirm nullable/out-of-range lookup behavior, chunking and Series dtype preservation.
- Check that noisy-max output indices and public candidate lengths remain aligned after rewriting and optimizing the complete private quantile expression.
- Investigate any supported custom private-index callers before deciding whether generic empty-candidate constructor validation is required.
