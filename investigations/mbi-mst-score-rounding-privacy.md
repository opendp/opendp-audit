---
schema_version: 1
upstream_commit: 7acfb2cdcee7d39fc26a6ade7edac15249c52f4b
updated: 2026-11-23
status: Partial
---

# MST public-model rounding exceeds certified score sensitivity

## Invariant

`_make_mst_scores` maps a dictionary of pairwise count tables into a score vector whose `LInfDistance(f64)` is bounded by `max(distance[1] for distance in d_in.values())`. This map is correct in exact arithmetic when each score is an induced matrix 1-norm discrepancy. The actual mechanism evaluates `float(np.linalg.norm(exact - synth, 1))`, where `exact` is an `int32` private histogram and `synth` is a `float64` public MBI model projection. Rounding during their subtraction and norm reduction is not covered by the map.

The downstream `_make_mst_select` privatizes these scores with `make_noisy_max`, so a score-distance underestimate can underestimate selection privacy loss.

## Affected source

- [`_make_mst_scores` and `_make_mst_select`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_mst/__init__.py)
- [`make_stable_marginals`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_utilities/__init__.py) produces `int32` tables and per-clique L0/L1/L∞ bounds
- [Pure-DP permute-and-flip](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/measurements/noisy_top_k/mod.rs) yields the conditional selection probability ratio
- [Audit issue #135](https://github.com/opendp/opendp-audit/issues/135) and [regression](../tools/tests/test_mst_public_model_rounding.py)

## Reproduced counterexample

Three binary columns `A,B,C` with `D0=[(0,0,0)]*4` and `D1=D0+[(0,0,1)]`. Each pairwise count table `AB`, `AC`, `BC` changes by one count in one cell. Therefore the score map claims sensitivity 1.

Let the public joint synthetic model have all its mass at `(0,0,0)` with total `T=float(2**55+16)`. Its pairwise projections are all `[[T,0],[0,0]]`, so they are nonnegative and mutually consistent.

The implementation computes `scores(D0)=[T,T,T]` and `scores(D1)=[T-8,T,T]`: L∞ difference 8 versus certified 1. This was first reproduced using source-equivalent NumPy 2.3.5 and subsequently confirmed by **actual OpenDP native score transformation** with a real MBI `MarkovRandomField`. The native projection derived from finite log-potentials has a small extra JAX normalization error (about 96 counts at this magnitude), which does not change the `[-8,0,0]` score difference.

Even at small public model totals, score maps are not exactly sound: for a one-cell public projection `[[0.1,0],[0,0]]`, a count change 4 to 5 produces `4.9-3.9=1.0000000000000004 > 1` in NumPy. This smaller witness alone is **not** claimed to break the full noisy-max epsilon accounting because the general nonmonotone `LInfDistance` privacy map includes an extra factor of two.

## Conditional privacy accounting

At top-1 permute-and-flip noise scale `s=4`, `MaxDivergence` declares `epsilon=2*1/s=0.5`. All three candidates tie on D0; on D1 candidate AB is eight lower than the other two.

The algorithm samples a uniformly random candidate order and accepts each candidate with probability `exp((score-max)/scale)`. Consequently:

- `Pr[AB|D0]=1/3`
- `Pr[AB|D1]=exp(-8/4)/3=exp(-2)/3`
- `ln(Pr[AB|D0]/Pr[AB|D1])=2 > 0.5`

This is a counterexample to privacy accounting for the *internal scorer-to-selector composition*, conditional on the public synthetic model being a permitted `mbi.MarkovRandomField` state.

## Verification and limitations

**Executed locally:** Three source-equivalent NumPy unit tests covering neighboring count dictionaries, compatible synthetic projections, and the analytic selection likelihood.

**Executed natively:** [Successful OpenDP + MBI integration CI](https://github.com/opendp/opendp-audit/actions/runs/45254507499) used `opendp==0.16.0a20261122001`, `mbi==2.0.0`, NumPy `2.3.5`, and JAX binary64. The [test](../tools/integration/mbi_public_model_score_native.py) constructs an MBI `MarkovRandomField` with finite log-potentials `0` on state `000` and `-1000` on every other state, an **empty stored marginals vector** and the public total `float(2**55+16)`. MBI's actual variable-elimination implementation derives all pairwise projections, rather than returning injected marginals. The projections are mutually compatible and near `T`; JAX normalization incurs roughly 96 count units of rounding at this scale.

Actual OpenDP `TypedDictDomain.member` checks passed on both neighbors. Invoking the native `_make_mst_scores` gave `[-8,0,0]`, while `t_scores.map(d_in)` returned 1. Composing with `then_noisy_max(scale=4)` reported `epsilon=0.5`. Crucially, the actual `_make_mst_select` constructor with `num_selections=1` and `d_out=0.5` also constructed, `map(d_in)` returned `0.5`, and it successfully sampled an edge. The finite-model, actual-selector evidence confirms the **internal privacy-map counterexample**.

**Not executed:** A complete `make_contingency_table` call or its model re-estimation pipeline. That outer workflow might constrain public model totals. Thus the verified impact is an internal score/selection measurement that incorrectly certifies privacy; the deployed high-level release path remains an unresolved reachability question.

## Deduplication and mitigation

- [Issue #117](https://github.com/opendp/opendp-audit/issues/117) observes that `np.linalg.norm(matrix, 1)` means induced matrix 1-norm rather than entrywise L1. In *exact arithmetic*, that distinction makes the L1 stability bound conservative. The new rounding issue is different and persists even if that utility issue is fixed with a floating-point flattened norm.
- [Issue #125](https://github.com/opendp/opendp-audit/issues/125) records an analogous score-rounding failure in **AIM**, not this MST selection route.

Recommended follow-up: validate high-level `make_contingency_table` model reachability and redesign the score computation or its certified stability map to bound numerical arithmetic, including cancellation and reductions. Never rely on the exact-arithmetic Lipschitz constant without a floating-point error analysis.
