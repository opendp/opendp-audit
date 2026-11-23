---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Integer-widening Polars aggregation cast preserves mathematical distances

## Invariant and threat model

An aggregate result already certified with an `LpDistance<P,f64>` metric may be widened from one integer type to another without an additional stability factor **only if every source integer is representable in the target type**. If a narrowing or mixed-sign conversion clips/wraps values, a source-defined stability argument may need an independent proof. Private-data-dependent conversion exceptions can also invalidate the claimed function contract. This investigation covers the mathematical range and exact-integer preservation conditions, **not** a full privacy proof for the upstream aggregation.

## Affected symbols and source audits

- [Source audit of `make_cast_aggregation`](../source/rust/src/transformations/make_stable_expr/expr_cast_aggregation/mod.rs.md) and [pinned implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_cast_aggregation/mod.rs).
- [Shared `is_integer_widening_cast`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/cast.rs) and [existing classifier audit](https://github.com/opendp/opendp-audit/blob/main/source/rust/src/transformations/make_stable_expr/cast.rs.md).
- [Existing native Rust examples](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_cast_aggregation/test.rs) and [executable mathematical test model](../tools/tests/test_polars_aggregate_widening_model.py).

## Reasoning and evidence

The cast constructor calls `make_stable` on its inner aggregation. After receiving the output `ExprDomain`, it checks `is_integer_widening_cast(from_dtype, to_dtype)`. This shared predicate has exact integer min/max bounds for six types and admits only target ranges containing the complete source range. Under mathematical integer semantics, this makes a cast the identity on source values, so absolute differences—and therefore vector `Lp` distances for any positive exponent—remain unchanged. This supports use of `StabilityMap::new(Clone::clone)` without adding a sensitivity multiplier.

`CastOptions::Strict` is rewritten to `NonStrict`. `CastOptions::Overflowing` is not rewritten, but there is no representable source value that can overflow when converted to a target whose range contains the source's range. Thus allowing the mode is not itself an identified defect. The public datatype guard rejects nonliteral target dtypes and the range guard rejects unsupported casts.

**Executed:** Five Python standard-library tests on 36 integer type pairs. Tests include the full range containment matrix, selected rejection/acceptance cases, boundary samples, exact integer difference equality, and `L1/L2/L4`-power equalities for small aggregate vectors. All tests passed. The entire available local test suite, including these five, passed. **Not executed:** actual Rust generics, Polars casting, exact FFI behavior, or binary floating-point metric arithmetic. No native execution is implied by the mathematical checks.

## Findings

**No new defect within this bounded scope.** The source's full-range containment predicate is conservative and sufficient for mathematical value preservation. Residual risks are external to the reviewed mathematical invariant: pinned Polars runtime behavior on nulls and `Overflowing` mode, numerical representation of large integer differences as `f64`, upstream aggregate validity, and the unrelated `LpDistance<0>` metric-contract problem already tracked in [audit issue #37](https://github.com/opendp/opendp-audit/issues/37). No redundant candidate bug issue is warranted.

## Unresolved questions

- Run native tests of accepted boundary-value casts under strict, non-strict and overflowing modes, ensuring no error and correct nullability.
- Investigate large integer differences entering `LpDistance<P,f64>` separately before upgrading the privacy/stability row from `Partial`.
- Consider separately whether adding conservative `UInt8`/`UInt16` interval entries would improve utility; their omission does not allow an unsafe cast.
