---
schema_version: 1
source: rust/src/transformations/quantile_score_candidates/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/quantile_score_candidates/mod.rs`

## Scope and assumptions

- **Scope:** Score evaluation in `score_candidates`, its advertised postcondition, and the `LInfDistance` stability bound returned by `score_candidates_map`. Follow the caller through `make_quantile_score_candidates` and `make_private_quantile` only as necessary to understand how the sensitivity bound is used.
- **Invariant:** For non-NaN ordered data, strictly ascending candidates, `0 <= alpha_num <= alpha_den`, positive `alpha_den`, and a safe count cap `l`, each score equals `abs((alpha_den - alpha_num) * min(count_lt, l) - alpha_num * min(count_gt, l))`. For two datasets at multiset symmetric distance `d`, every candidate score differs by at most `d * max(alpha_num, alpha_den - alpha_num)`. For datasets of the same fixed size, the bound tightens to `(d // 2) * alpha_den`.
- **Assumptions:** Valid integer scoring constants are produced by `score_candidates_constants`; integer multiplication and histogram counts remain within `u64`; candidate and input ordering is total and comparisons are consistent. In the fixed-size case the input datasets have equal lengths and the `SymmetricDistance` or `InsertDeleteDistance` is at least their multiset difference.
- **Pinned upstream:** [Rust scorer and map](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/quantile_score_candidates/mod.rs), [score postcondition proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/quantile_score_candidates/score_candidates.tex), [map proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/quantile_score_candidates/score_candidates_map.tex), and [private quantile caller](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/private_quantile/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `score_candidates` | correctness/rank-score | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Score evaluation and proof mismatch](#score-evaluation-and-proof-mismatch) |
| `score_candidates_map` | privacy/stability-bound | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Stability assessment](#stability-assessment) |

## Analysis

### Score evaluation and proof mismatch

The Rust code builds two histograms of candidate-boundary intervals. Their prefix sums recover the number of records strictly less than each candidate (`lt`) and the number less than or equal to it (`le`); `gt = n - le`. It then returns `((alpha_den - alpha_num) * min(lt, l)).abs_diff(alpha_num * min(gt, l))`. This agrees with the rank-distance score documented in the constructor proof, before sign inversion for minimum selection.

However, the **theorem/postcondition of `score_candidates.tex`** states `abs(alpha_den * min(count_lt, l) - alpha_num * min(count_gt, l))`, missing the subtraction of `alpha_num` from the first coefficient. Minimal counterexample: `alpha_num=1`, `alpha_den=2`, `l=1`, `x=[0]`, `candidates=[1]`. Rust computes `1`; the published postcondition specifies `2`. Therefore the proof does not establish its stated postcondition for the current implementation. The issue also appears in the formula in the constructor proof, even though its earlier derivation yields the correct rank-distance formula. See the [cross-file investigation](../../../../../investigations/quantile-score-proof-coefficient.md).

**Executed evidence:** The standard-library [finite model tests](../../../../../tools/tests/test_quantile_score_model.py) translate the Rust histogram algorithm and independently compute the expected count formula for all 40 datasets of length 0 through 3 over `{-1,0,1}`, 5 integer alpha fractions, and 3 count caps (600 cases). The models agree in all 600 cases. The one-record discrepancy with the proof theorem is explicitly asserted. These tests do **not** run the upstream Rust implementation.

### Stability assessment

For one inserted or deleted record, the true `lt` or `gt` count for a fixed candidate increases/decreases by at most one. The cap `min(count, l)` is 1-Lipschitz; the resulting absolute score changes by at most `alpha_den - alpha_num` for a record below the candidate, or at most `alpha_num` for a record above. Summing over insertions/deletions yields the unsized bound. For two datasets of equal length, their multiset symmetric difference is `2k` and one can pair the `k` removals with `k` insertions; each replacement changes the score by at most the sum of those two constants, namely `alpha_den`, yielding `(d // 2) * alpha_den` when `d` bounds their multiset symmetric difference.

The finite model exhaustively compares **24,000 ordered dataset pairs** (40 by 40 datasets, five alpha fractions, three caps). The score difference for all three candidates stays within the unsized bound, and all equal-size pairs meet the tighter bound. `make_quantile_score_candidates` constructs these maps, and `make_private_quantile` feeds the score vector into `make_noisy_max` with `negate=true` to prefer smaller rank distances.

**Status `Partial`:** This finite check and elementary bound argument do not independently verify the full upstream numeric-contract proof for every possible `u64` count, all supported atomic types, or downstream noisy-selection arithmetic. No counterexample to the implementation's stability map was identified in the reviewed model. The incorrect proof postcondition should be repaired independently of any claim of a privacy defect.

## Next checks

- Correct the first coefficient in `score_candidates.tex`'s postcondition (and the equivalent truncated-score equation in `make_quantile_score_candidates.tex`) to `alpha_den - alpha_num`, then reconcile the histogram proof text with its `lt`/`le` variables.
- Expand compiled Rust tests to cover the one-record proof witness and score/sensitivity properties at edge alpha values, large count caps and candidate equality boundaries.
- Review the integer-approximation path through `score_candidates_constants`, and independently verify the downstream `make_noisy_max` privacy calibration; neither is fully covered here.
- [Upstream issue #2075](https://github.com/opendp/opendp/issues/2075) remains an open proof-review issue relevant to this scope. No new issue or PR was opened under the current user restrictions.
