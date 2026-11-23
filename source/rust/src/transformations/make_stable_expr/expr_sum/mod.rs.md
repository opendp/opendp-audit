---
schema_version: 1
source: rust/src/transformations/make_stable_expr/expr_sum/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/make_stable_expr/expr_sum/mod.rs`

## Scope and assumptions

- **Audit scope:** Non-deprecated Polars `make_expr_sum`, `sum_components`, `sum_stability_map`, `Summand` dtype associations and the integer/float implementations of `Accumulator::relaxation`. Reviewed constructor guards, margin requirements, output dtype/domain, integer overflow exclusion, and the L01Inf-to-Lp aggregation sensitivity formula. The native Polars aggregation backend, exact-directed cast traits, and group-by input preparation were not executed end-to-end.
- **Invariants:** A successful grouped sum has a stable bounded nonnullable, non-NaN numeric input and a finite public maximum per-group length; integer sums cannot overflow for any admitted group; floating sums have finite ordered bounds, safe accumulation and nonzero relaxation when rounding can vary with permutation. The resulting summed value has the dtype emitted by Polars and an output aggregation margin of length one. The stability map must cover changes across up to `l0` partitions, `l1` total records and `l_inf` records per partition under P=1 or P=2, and must include rounding relaxation.
- **Assumptions:** The input domain and margin certificates are sound; individual group sums are computed by at most `n−1` correctly rounded additions of finite values; exact integers do not overflow when the checked size limit is met; `InfCast`, `InfAdd`, `InfMul`, and `InfSqrt` perform conservative directed operations. Input order is not necessarily public, so floating summation order variation must be accounted for by the additive relaxation.
- **Sources pinned at `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`:** [`expr_sum/mod.rs`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_sum/mod.rs), [native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_sum/test.rs), [`traits/sum.rs`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/sum.rs), [`sum/int/mod.rs`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/sum/int/mod.rs), and [audit claim #75](https://github.com/opendp/opendp-audit/issues/75).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `transformations::make_stable_expr::expr_sum::make_expr_sum` | correctness/input-bounds-null-and-margin-guards | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Constructor guard trace](#constructor-guard-trace) |
| `transformations::make_stable_expr::expr_sum::make_expr_sum` | correctness/output-margin | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Output type and empty-group semantics](#output-type-and-empty-group-semantics) |
| `transformations::make_stable_expr::expr_sum::sum_components` | correctness/polars-sum-type | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Output type and empty-group semantics](#output-type-and-empty-group-semantics) |
| `transformations::make_stable_expr::expr_sum::sum_stability_map` | privacy/partition-lp-sensitivity | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Sensitivity accounting](#sensitivity-accounting) |
| `transformations::make_stable_expr::expr_sum::Summand` | correctness/accumulator-dtype-map | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Output type and empty-group semantics](#output-type-and-empty-group-semantics) |
| `transformations::make_stable_expr::expr_sum::Accumulator::relaxation` | correctness/float-accumulation-error | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Float relaxation](#float-relaxation) |
| `transformations::make_stable_expr::expr_sum::Accumulator::relaxation` | correctness/integer-overflow-guard | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Integer overflow](#integer-overflow) |

## Analysis

### Constructor guard trace

The constructor matches only `Expr::Agg(AggExpr::Sum(input))`. It calls `input.make_stable`, requires an aggregation context and nonnullable column domain, and rejects floats whose atom domain allows NaN. It dispatches only the listed integer or float types, rejecting unsupported dtypes. Every type's sensitivity setup requires public closed bounds via `atom_domain::get_closed_bounds`; the float relaxation helper additionally rejects any nonfinite or inverted bounds.

The margin must supply `max_length`, which is converted to `usize` by exact checked integer cast. The constructor requests `max_groups` whenever the float relaxation is nonzero; otherwise the relaxation term is zero and `max_groups` need not be specified. Failure is at constructor time and independent of dataset contents. It composes the source transformation with an aggregation expression and the computed stability map, rather than checking private values at execution.

### Output type and empty-group semantics

The `Summand` associations match the reviewed pinned Polars type behavior: `i8,i16 → i64`, `i32 → i32`, `i64 → i64`, `u32 → u32`, `u64 → u64`, and both floats retain their widths. `sum_components` creates an atom domain of the accumulator dtype and a typed zero literal used with `Function::then_expr(Expr::sum).fill_with`. It changes the output aggregation margin's `max_length` to one and retains grouping keys, `max_groups` and the incoming invariant. The current upstream `test_polars_sum_types` verifies this matrix on a native Polars frame; it was **inspected, not executed** in this review. Runtime output dtype/domain behavior remains `Partial`.

### Sensitivity accounting

The code bounds a per-group ideal sum shift using

- **Variable group lengths:** `d · max(|L|, U)` for maximum changed records `d` and public bounds `L ≤ U`. With ordered bounds this equals `d · max(|L|,|U|)`, even when `U < 0`.
- **Public fixed lengths:** `floor(d / 2) · (U−L)` because a replacement of one record costs two insert/delete edits. The integer division is conservative for odd upper bounds `d`, as only complete replacements can occur within equal-length groups.

For output norm `P=1` the norm map uses identity; for `P=2` it uses a conservatively rounded square root; other `P` values are rejected by the map (not proactively by the constructor). With `(l0,l1,l_inf)` event-contribution bounds, the main term is the smaller of `pp_map(l1)` and `norm_P(l0) * pp_map(l_inf)`. The term `norm_P(max_groups) * pp_relaxation` is **added**, not only included for nonzero `d_in`, to cover floating reordering and alternate grouping/chunk summation histories. All arithmetic on the reported floating sensitivity uses directed operations (`InfCast`, `InfMul`, `InfAdd`, `InfSqrt`).

The algebra matches the expected sensitivity decomposition conditional on valid margin certificates and correctly rounded Polars reductions. **Integration with Polars and upstream grouping remains Partial.** In particular, upstream [issue #3134](https://github.com/opendp/opendp/issues/3134) is open with proposed [PR #3155](https://github.com/opendp/opendp/pull/3155) addressing group-by permutation/ordering stability; that is a known cross-component issue, not a novel `expr_sum` finding.

### Float relaxation

For binary32/binary64 the `Accumulator` implementation sets `max_depth=max_length.saturating_sub(1)` and computes an upward-rounded `2E` using `sum_relaxation` in [`traits/sum.rs`](https://github.com/opendp/opendp-audit/blob/main/source/rust/src/traits/sum.rs.md). With `n=max_length`, `M=max(|L|,|U|)` and unit roundoff `u`, the exact rational model uses `E=[(n−1)u/(1−(n−1)u)]nM`. It rejects `(n−1)u ≥ 1` and `nM + E > MAX_FINITE`, then converts the relaxation upward to the accumulator width.

The [independent standard-library exact-rational model](https://github.com/opendp/opendp-audit/blob/main/tools/tests/test_polars_sum_roundoff_model.py) checks a representative matrix of random bounded binary32/binary64 values under rounded left, right, and pairwise-tree addition; it also checks an example where the *same multiset* summed in different orders produces 0 and 1. The `2E` relaxation exceeds this difference. These arithmetic checks do **not** run native OpenDP/Polars and do not establish the actual Polars aggregation depth; the float sensitivity property remains `Partial`.

### Integer overflow

For `i32`/`i64`/`u32`/`u64` accumulator types, `Accumulator::relaxation` calls `int_sum_size_limit((L,U))`, rejecting any `max_length` greater than the maximum safe length, and returns zero relaxation otherwise. The size helper uses arbitrary-precision `IBig` to compute the tightest size cap from `MAX_FINITE / U` when `U>0` and `MIN_FINITE / L` when `L<0`, then saturates to `usize`. Thus every prefix or regrouped partial sum of at most `max_length` bounded integer values is representable, and no floating relaxation is necessary. Smaller input integers (`i8,i16`) are promoted to an `i64` accumulator before bounds checks. The independent reference model checks representative size caps and all valid tested prefixes, **not** compiled Polars execution.

### Disposition and limits

No new, independently substantiated defect was identified in this scoped sum arithmetic review; existing upstream #3134 and proposed fix #3155 cover broader ordered/unordered group-by concerns, so no duplicate issue was opened. The analytical model is not a verification of Polars chunking order, output schema, native overflow behavior, or the rounding-direction trait implementations.

## Next checks

- Execute version-matched native Rust/Polars tests using artificially fragmented chunks and shuffled rows, verifying `output_domain.member`, no exceptions, the exact output dtype and measured sensitivity against `map` at both zero and nonzero input distances.
- Trace `InfCast<RBig>` and `InfSqrt` at boundary sizes and test the Polars backend's maximum addition depth and float overflow behavior.
- Revisit the group-by integration after [PR #3155](https://github.com/opendp/opendp/pull/3155) merges or changes, without duplicating existing #3134.
