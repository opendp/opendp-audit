---
schema_version: 1
source: rust/src/traits/sum.rs
updated: 2026-11-23
---

# `rust/src/traits/sum.rs`

## Scope and assumptions

- **Audit scope:** Exact-rational finite-precision error and overflow bounds used by the non-deprecated Polars `expr_sum` transformation: `round_up`, `sum_magnitude`, `sum_error` and `sum_relaxation`. The Polars native aggregation kernel and directed conversions in the separate `InfCast` implementation were not re-executed.
- **Invariants:** Accept only finite ordered floating-point bounds. For maximum group length `n`, finite maximum magnitude `M` and depth `d=n-1`, the error bound is `E = (du/(1-du)) nM` with unit roundoff `u=epsilon/2`. Refuse `du >= 1` and refuse possible intermediate overflow `nM + E > MAX_FINITE`. Convert `2E` conservatively to the output float via upward rounding. The model must not claim native behavior verified.
- **Assumptions:** IEEE-754 binary32/binary64 additions with correctly rounded operations and gradual underflow; no intermediate overflow beyond the checked source guard; input values lie within public finite bounds; Polars group reductions perform only ordinary additions and have no depth exceeding `n−1`. The mathematical Higham bound is applied under those assumptions; the Polars kernel and runtime version were not independently checked.
- **Pinned sources:** [`traits/sum.rs`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/sum.rs), [`expr_sum`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_sum/mod.rs), [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_sum/test.rs), and [audit #75](https://github.com/opendp/opendp-audit/issues/75).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `traits::sum::sum_magnitude` | correctness/finite-ordered-input-bounds | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Bounds checks](#bounds-checks) |
| `traits::sum::sum_error` | correctness/exact-rational-roundoff-bound | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Rounding analysis](#rounding-analysis) |
| `traits::sum::sum_relaxation` | correctness/float-overflow-exclusion | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Intermediate overflow](#intermediate-overflow) |
| `traits::sum::round_up` | correctness/conservative-float-conversion | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Directed relaxation conversion](#directed-relaxation-conversion) |

## Analysis

### Bounds checks

`sum_magnitude` rejects non-finite lower/upper bounds and `lower > upper`, then returns `max(abs(lower),abs(upper))`. This is sufficient to bound the absolute magnitude of every admitted non-null, non-NaN float record. `expr_sum` independently rejects columns whose domain allows null or NaN and requires closed numeric bounds. A caller's malformed or unbounded values fail at transformation construction, not when privately evaluating rows.

### Rounding analysis

`sum_error` computes `u` as an exact rational conversion of `T::epsilon()/2`. For a sum of at most `n` values of absolute magnitude at most `M` with maximum addition depth `d`, it sets `h = d u`, rejects `h >= 1` and returns the exact rational

`E = (h/(1-h)) · n · M`.

This is the Higham (`gamma_d`) absolute-error form using the conservative inequality that the sum of absolute inputs is at most `nM`. The source uses arbitrary-precision `RBig` for multiplication and division; it does **not** round the intermediate error bound down to binary floating point. For `n <= 1` or `M=0`, it returns zero without requiring a positive-depth bound. The Polars `Accumulator` implementation selects `max_depth = max_length.saturating_sub(1)`, which upper-bounds the number of binary additions along any reduction path for a group of `n` values.

The [independent exact-rational reference test](https://github.com/opendp/opendp-audit/blob/main/tools/tests/test_polars_sum_roundoff_model.py) compares a rounded left-fold, right-fold and pairwise tree against the exact rational sum for seeded finite binary32 and binary64 examples. It also checks that permutation of the same records can change a floating-point result even at zero unordered input distance. That model does **not** execute Polars or prove every group kernel satisfies the source assumptions. Thus the full implementation-level bound remains `Partial`.

### Intermediate overflow

`sum_relaxation` obtains the exact rational `E` and rejects a potential overflowing group if `nM + E > T::MAX_FINITE`. The left-hand side bounds the magnitude of any partial sum with at most `n` records plus its rounding error, provided the assumptions above hold. The check is conservative: for example, a two-element group with public bounds `[-T::MAX_FINITE,T::MAX_FINITE]` is rejected even if an individual dataset happens to cancel. That is appropriate because admitting data-dependent overflow would enable distinguishing events.

The returned relaxation is `2E`, reflecting the triangle inequality between any two rounded representations of the same ideal group sum, each with error at most `E`. This additive term is necessary even when the unordered multiset of input rows is unchanged; arbitrary reordering can alter floating-point summation results.

### Directed relaxation conversion

`round_up<T>` calls `T::inf_cast` on the exact rational bound and rejects nonfinite outputs. The `InfCast` implementation was not traced end-to-end in this scoped audit, so upward rounding is a **dependency**, not an independently verified native property. The native `expr_sum` tests inspected include `f32` depth threshold `n=2^24+1`, zero relaxation at size 1, and overflow rejection for maximum finite bounds at size 2.

**Disposition:** No novel arithmetic defect established by the source trace or independent exact-rational reference model. This is not an end-to-end proof of the native Polars aggregation path.

## Next checks

- Verify that the pinned Polars aggregation kernel uses only correctly rounded native float additions and has maximal depth at most `max_length−1`, including chunked, null-free and grouped inputs.
- Cross-check `InfCast<RBig>` conversion direction and extreme underflow/overflow boundaries against compiled Rust.
- Validate the integrated `expr_sum` stability map with same-multiset permutations and bounded neighboring groups; an existing broader [upstream group-by issue #3134](https://github.com/opendp/opendp/issues/3134) is open with [PR #3155](https://github.com/opendp/opendp/pull/3155), and should not be duplicated.
