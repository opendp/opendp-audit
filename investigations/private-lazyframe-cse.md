---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Private Polars plan CSE and independent DP noise

## Invariant and threat model

Noise samples within one private release must be independent when the privacy proof relies on independent draws; Polars must not eliminate a repeated randomized subexpression by reusing a previously sampled value. This review covers the ordinary `make_private_lazyframe` → `OnceFrame` → collect paths and the explicit CSE setting. It does not prove independence under all optimizer passes or the behavior of an analyst who manually enables CSE through the honest-but-curious `lazy()` escape hatch.

## Affected symbols and source audits

- [Primary constructor report](../source/rust/src/measurements/make_private_lazyframe/mod.rs.md), covering `make_private_lazyframe` on pinned [Rust source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/mod.rs#L136).
- [Python `OnceFrame` report](../source/python/src/opendp/extras/polars/__init__.py.md) and [Python implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/extras/polars/__init__.py#L626).
- [Rust `OnceFrame` report](../source/rust/src/polars/mod.rs.md) and [Rust implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/mod.rs#L503).
- [Existing upstream regression](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/test/test_polars_noise_cse.py#L1).

## Reasoning and evidence

**Rust constructor.** The compiled private plan is wrapped into a `LazyFrame`, caller optimizer options are copied, and `with_comm_subexpr_elim(false)` is applied *last* before constructing `OnceFrame`. Thus the constructor does not inherit an input CSE=true setting for this option. The plan is not materialized at construction.

**Python ordinary collect.** `OnceFrame.collect()` obtains the plan through the consuming `_onceframe_take_lazy` query, then passes `pl.QueryOptFlags(comm_subexpr_elim=False)` to Polars at collection. This explicitly prevents collection-time CSE in the intended release method. Shuffling occurs afterward and addresses row-order leakage, not duplicated random noise.

**Rust collect.** In non-FFI builds, `OnceFrame::collect` consumes the stored Rust `LazyFrame`, for which the constructor applied the CSE-disabled option. When `polars-ffi` is enabled, Rust external collection is refused; Python performs collection with the separate flag. This is a cross-file static path argument, not a native execution trace.

**Known regression.** Upstream [issue #3238](https://github.com/opendp/opendp/issues/3238) reported CSE-induced reuse of private noise and was closed by [merged PR #3233](https://github.com/opendp/opendp/pull/3233). The regression test constructs public-group imputation with two independent DP aggregates and multiple absent public keys. It asserts four generated noise draws are pairwise distinct for normal OnceFrame collection and manual lazy collection with CSE off. Explicit lazy collection with CSE on is marked strict `xfail`: this path remains unsafe and is documented as an analyst responsibility under the honest-but-curious feature.

**Executed versus inspected:** All listed upstream source, PR, and test text was read via GitHub. No native Rust or Python Polars/FFI test was executed as part of this audit. The audit repository's record schema is validated separately by its CI.

## Findings

The already reported CSE privacy flaw is **fixed on upstream `main`** for the ordinary guarded paths at SHA `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. No *new* defect identified within this bounded review. No duplicate candidate issue filed.

## Unresolved questions

- Whether Polars optimization passes other than `comm_subexpr_elim`, including common-subplan elimination, can merge independent randomized UDF executions.
- Behavioral verification with the exact supported Polars version and FFI bridge.
- The honest-but-curious bypass permits re-enabling CSE; this is explicitly outside the guarded default API contract.
