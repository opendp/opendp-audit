---
schema_version: 1
source: rust/src/transformations/quantile_score_candidates/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/quantile_score_candidates/mod.rs`

## Scope and assumptions

- **Scope:** Score evaluation in `score_candidates`, its advertised postcondition, the `LInfDistance` stability bound returned by `score_candidates_map`, and the separate total-order precondition checked by `check_candidates`. Follow the public constructor and non-deprecated Polars discrete scorer only where needed for reachability.
- **Invariant:** For non-NaN ordered data, strictly ascending candidates, `0 <= alpha_num <= alpha_den`, positive `alpha_den`, and a safe count cap `l`, each score equals `abs((alpha_den - alpha_num) * min(count_lt, l) - alpha_num * min(count_gt, l))`. For two datasets at multiset symmetric distance `d`, every candidate score differs by at most `d * max(alpha_num, alpha_den - alpha_num)`. For datasets of the same fixed size, the bound tightens to `(d // 2) * alpha_den`.
- **Assumptions:** Valid integer scoring constants are produced by `score_candidates_constants`; integer multiplication and histogram counts remain within `u64`; candidate and input ordering is total and comparisons are consistent. In the fixed-size case the input datasets have equal lengths and the `SymmetricDistance` or `InsertDeleteDistance` is at least their multiset difference.
- **Pinned upstream:** [Rust scorer and map](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/quantile_score_candidates/mod.rs), [score postcondition proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/quantile_score_candidates/score_candidates.tex), [map proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/quantile_score_candidates/score_candidates_map.tex), and [private quantile caller](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/private_quantile/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `score_candidates` | correctness/rank-score | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Score evaluation and proof mismatch](#score-evaluation-and-proof-mismatch) |
| `score_candidates_map` | privacy/stability-bound | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Stability assessment](#stability-assessment) |
| `check_candidates` | correctness/candidate-total-order | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Singleton NaN witness](../../../../../investigations/quantile-candidate-singleton-nan.md); [issue #45](https://github.com/opendp/opendp-audit/issues/45) |

## Analysis

### Score evaluation and proof mismatch

The Rust code builds two histograms of candidate-boundary intervals. Their prefix sums recover the number of records strictly less than each candidate (`lt`) and the number less than or equal to it (`le`); `gt = n - le`. It then returns `((alpha_den - alpha_num) * min(lt, l)).abs_diff(alpha_num * min(gt, l))`. This agrees with the rank-distance score documented in the constructor proof, before sign inversion for minimum selection.

However, the **theorem/postcondition of `score_candidates.tex`** states `abs(alpha_den * min(count_lt, l) - alpha_num * min(count_gt, l))`, missing the subtraction of `alpha_num` from the first coefficient. Minimal counterexample: `alpha_num=1`, `alpha_den=2`, `l=1`, `x=[0]`, `candidates=[1]`. Rust computes `1`; the published postcondition specifies `2`. Therefore the proof does not establish its stated postcondition for the current implementation. The issue also appears in the formula in the constructor proof, even though its earlier derivation yields the correct rank-distance formula. See the [cross-file investigation](../../../../../investigations/quantile-score-proof-coefficient.md).

**Executed evidence:** The standard-library [finite model tests](../../../../../tools/tests/test_quantile_score_model.py) translate the Rust histogram algorithm and independently compute the expected count formula for all 40 datasets of length 0 through 3 over `{-1,0,1}`, 5 integer alpha fractions, and 3 count caps (600 cases). The models agree in all 600 cases. The one-record discrepancy with the proof theorem is explicitly asserted. These tests do **not** run the upstream Rust implementation.

### Stability assessment

For one inserted or deleted record, the true `lt` or `gt` count for a fixed candidate increases/decreases by at most one. The cap `min(count, l)` is 1-Lipschitz; the resulting absolute score changes by at most `alpha_den - alpha_num` for a record below the candidate, or at most `alpha_num` for a record above. Summing over insertions/deletions yields the unsized bound. For two datasets of equal length, their multiset symmetric difference is `2k` and one can pair the `k` removals with `k` insertions; each replacement changes the score by at most the sum of those two constants, namely `alpha_den`, yielding `(d // 2) * alpha_den` when `d` bounds their multiset symmetric difference.

The finite model exhaustively compares **24,000 ordered dataset pairs** (40 by 40 datasets, five alpha fractions, three caps). The score difference for all three candidates stays within the unsized bound, and all equal-size pairs meet the tighter bound. `make_quantile_score_candidates` constructs these maps, and `make_private_quantile` feeds the score vector into `make_noisy_max` with `negate=true` to prefer smaller rank distances.

**Status `Partial`:** This finite check and elementary bound argument do not independently verify the full upstream numeric-contract proof for every possible `u64` count, all supported atomic types, or downstream noisy-selection arithmetic. No counterexample to the implementation's stability map was identified in the reviewed model. The incorrect proof postcondition should be repaired independently of any claim of a privacy defect.

### Candidate total-order validation

**Finding:** `check_candidates` validates nonemptiness, then checks only `candidates.windows(2)`. A one-element floating-point `NaN` set has zero length-2 windows, so the helper returns `Ok(())` even though that candidate is not totally ordered. This contradicts the stated postcondition and its proof theorem. The public `make_quantile_score_candidates` and the non-deprecated Polars `make_expr_discrete_quantile_score` path both call the validator; the Polars path also checks nullity separately, but `NaN` is not a null. The shared helper's gap is a **low-severity candidate validation/proof-contract issue**, not a demonstrated privacy-bound underestimate. [Upstream PR #3243](https://github.com/opendp/opendp/pull/3243) is open and unmerged; its patch fixes this exact singleton-NaN gap, so the upstream disposition is **Pending PR**.

**Executed evidence:** The standard-library [source-model regression](../../../../../tools/tests/test_quantile_candidate_singleton_nan.py) checks the singleton witness, ordinary valid/invalid cases, and 10,000 deterministic float candidate sequences. Only singleton `NaN` disagreed with a reference nonempty/strictly ascending/total-order contract in this finite model. The test is **not compiled OpenDP Rust or Polars**. See the [cross-file investigation](../../../../../investigations/quantile-candidate-singleton-nan.md) and [audit issue #45](https://github.com/opendp/opendp-audit/issues/45), closed after the pending fix PR was identified.

**Limitations:** End-to-end `dp_quantile` runtime behavior for an all-NaN public candidate set was not tested. The broader Polars pipeline is reserved under [audit task #42](https://github.com/opendp/opendp-audit/issues/42). This row is `Audited` only for the shared validator's total-order contract; it does not certify other paths.

## Next checks

- Correct the first coefficient in `score_candidates.tex`'s postcondition (and the equivalent truncated-score equation in `make_quantile_score_candidates.tex`) to `alpha_den - alpha_num`, then reconcile the histogram proof text with its `lt`/`le` variables.
- Expand compiled Rust tests to cover the one-record proof witness and score/sensitivity properties at edge alpha values, large count caps and candidate equality boundaries.
- Review the integer-approximation path through `score_candidates_constants`, and independently verify the downstream `make_noisy_max` privacy calibration; neither is fully covered here.
- **Upstream disposition: Unreported.** [OpenDP issue #2075](https://github.com/opendp/opendp/issues/2075) is a general proof-review task that does not mention this specific coefficient mismatch; it is related context, not an equivalent defect report. No matching corrective PR was identified. The discrepancy is now filed as [audit issue #9](https://github.com/opendp/opendp-audit/issues/9); upstream disposition remains **Unreported**.
