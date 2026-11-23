---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Polars DP median delegates to quantile scoring at alpha = 1/2

## Invariant and threat model

The non-deprecated `dp_median` shim must compose the same private measurement as `dp_quantile(alpha=0.5)` with equal public candidates, noise scale, output measure, input metric and optional global scale. It must not bypass null/NaN validation, score sensitivity accounting, private candidate-index selection, or public candidate-value postprocessing.

For the median score, a record strictly below a candidate increases the less-than count, a record strictly above increases the greater-than count, and equal records change neither count. The correct alpha-half score is therefore `|#(x<c)-#(x>c)|`, with one-record insert/delete sensitivity at most 1 and one-record replacement sensitivity at most 2 (before any capping). The finite model tests these numerical properties, **not** the actual distribution of the DP release.

## Affected symbols and source audits

- [`make_expr_dp_median` and `DPMedianShim`](../source/rust/src/measurements/make_private_expr/expr_dp_median/mod.rs.md); [pinned median constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_dp_median/mod.rs).
- [`make_expr_discrete_quantile_score`, `validate`, and `match_discrete_quantile_score`](../source/rust/src/transformations/make_stable_expr/expr_discrete_quantile_score/mod.rs.md); [pinned scorer](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_discrete_quantile_score/mod.rs).
- [Private quantile composition](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_dp_quantile/mod.rs), [private-expression dispatcher](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/mod.rs), and [shim matcher and builder](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/mod.rs).
- [Shared integer score and stability map](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/quantile_score_candidates/mod.rs), [existing score investigation](quantile-score-proof-coefficient.md), and [candidate ordering investigation](quantile-candidate-singleton-nan.md).
- [Executable finite Python model](../tools/tests/test_dp_median_delegation_model.py).

## Source and mathematical reasoning

### Median alias and privacy-chain preservation

The dispatcher detects `DPMedianShim` and invokes `make_expr_dp_median`. Its `match_shim` call yields `[input,candidates,scale]` (filling omitted public trailing positions with null literals), after which it calls `apply_plugin` to construct a `DPQuantileShim` with four inputs `[input,lit(0.5f64),candidates,scale]`. It calls `input.make_private(...,global_scale)` with the exact prior domain, input metric, output measure and optional global scale.

The quantile constructor recursively stabilizes the original data input, computes a public fill value from the candidate-series median, fills null/NaN values, creates a discrete-score plugin, privately selects the minimizing-score index and applies a public candidate-series index lookup. No separate budget or unchecked release is introduced by the median alias. This is a source-level control-flow trace, not native execution or an independent DP proof of the callee.

### Alpha = 1/2 score identity

The shared `score_candidates_constants` represents 0.5 exactly as `alpha_num=1`, `alpha_den=2` for ordinary group size bounds. Consequently the implemented score formula

`| (alpha_den-alpha_num) * min(lt,limit) - alpha_num * min(gt,limit) |`

reduces, with cap at least dataset length, to `|lt-gt|`. Here `lt=#(x<c)` and `gt=#(x>c)`; records equal to `c` count in neither term. Adding/removing one record changes at most one count by one, so score changes by at most one. Replacing one record is one deletion and one insertion, giving an upper bound of two.

For group-level score sensitivity the implementation's `score_candidates_map` uses `max(alpha_num,alpha_den-alpha_num)=1` per unbounded record change, or `alpha_den=2` per fixed-length replacement; it returns a vector `LInf` score bound together with the unchanged affected-group `L0` bound. These are the same parameters as the median alias.

### Executed reference model

Four tests in [`test_dp_median_delegation_model.py`](../tools/tests/test_dp_median_delegation_model.py) passed locally using only the Python standard library:

- **24,211** ordered datasets and nonempty candidate subsets (all 31 nonempty subsets of the five-value alphabet `{-2,-1,0,1,2}`, datasets of length 0 through 4) matched a direct independent median-score expression against a faithful histogram source model.
- **24,180** one-record insertions satisfied a maximum per-candidate score change of one.
- **66,650** one-record fixed-length replacements satisfied a maximum per-candidate score change of two.
- An explicit tied-data case `[1,1,1]` against candidates `[0,1,2]` produced `[3,0,3]`, excluding ties from both strict counts.

The model does not invoke the native Rust `DPMedianShim`, `DPQuantileShim`, Polars planner, floating-point casts, random noise, or released private candidates. It also does not test truncated scores where a large dataset exceeds the size cap, or candidate/null/NaN validation in the compiled library.

### Existing known defects and deduplication

- [Audit issue #9](https://github.com/opendp/opendp-audit/issues/9) remains open for the proof theorem's missing `alpha_num` coefficient. The current score implementation and the bounded model use the correct `alpha_den-alpha_num` coefficient; the proof artifact remains inconsistent.
- A **singleton NaN candidate** passes the shared `check_candidates` adjacency test, violating its total-order premise; [audit #45](https://github.com/opendp/opendp-audit/issues/45) was closed because **unmerged upstream PR #3243** already addresses that case. This audit does **not** claim the upstream fix is merged.
- Broad DP-quantile candidate, score and indexing audit tasks #40, #41, and #42 are closed. The present source-level review is confined to the missing median alias and discrete-score expression coverage.

## Findings and disposition

**No new defect confirmed** in the median alias's alpha-one-half delegation or the finite uncapped score sensitivity model. Existing shared candidate-validation and proof issues retain their respective upstream/audit tracking; no duplicate defect issue was created.

Overall verification **Partial**: the actual OpenDP/Polars plugin runtime, serializable FFI shims, full floating-point/group-margin domain behavior and complete privacy proof remain unverified by this bounded investigation.

## Next decisive checks

Execute native OpenDP at the pinned revision with both `dp_median(candidates,scale)` and `dp_quantile(alpha=0.5,candidates,scale)` on equivalent input plans. Compare inferred field types, null/NaN filling, rewritten plugin arguments, privacy maps, and sampled releases; rerun on upstream PR #3243 after it merges.
