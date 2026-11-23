---
schema_version: 1
source: python/src/opendp/extras/mbi/_aim/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/mbi/_aim/__init__.py`

## Scope and assumptions

- **Audit scope:** `_make_aim_scores`'s float64 score computation and L-infinity stability map, and downstream `_make_aim_select`'s use of `then_noisy_max`. Review the public noise-penalty dependency from `get_scale`. The full MBI optimizer, Rust sampler correctness, and other AIM configuration paths were not audited.
- **Invariant:** For two permitted input marginal dictionaries separated by declared distance `d_in`, the `LInfDistance(f64)` distance between computed score vectors cannot exceed `_make_aim_scores.stability_map(d_in)`; subsequent selection must be calibrated to that true distance.
- **Assumptions:** One added row changes each one-way count marginal in L1 by 1; public `Count.weight=1`, public model projections are finite, and finite binary64 penalty `P=2**54+8`. Histograms contain small `int32` counts, with two cells per marginal. All arithmetic tests below use independent NumPy, not the OpenDP runtime.
- **Pinned sources:** [AIM score constructor](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_aim/__init__.py), [MBI scale helper](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_utilities/__init__.py), [selection sampler/map](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/measurements/noisy_top_k/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `_make_aim_scores` | privacy/aim-score-stability | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Analysis](#analysis); [investigation](../../../../../../../investigations/aim-score-penalty-rounding-privacy.md) and [audit #125](https://github.com/opendp/opendp-audit/issues/125). |
| `_make_aim_select` | privacy/selection-calibration | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Analysis](#analysis); composition uses `then_noisy_max` to consume the underestimated score stability. |

## Analysis

### `_make_aim_scores` — `privacy/aim-score-stability`

**Conclusion:** The purported L-infinity stability bound ignores binary64 amplification of a small count change after subtraction of a large *public* expected-noise penalty.

For candidate `q` with unit weight, the function evaluates

```python
np.linalg.norm((exact - synth).flatten(), 1) - expectations[q.by] * prod(exact.shape)
```

but the stability map bounds the *exact* integer-count L1 change: `max(d_in[q.by][1] * q.weight for q in queries)`. These can diverge in floating-point arithmetic. Set a public penalty `P=float(2**54 + 8)`. Let public synthetic one-way marginals be `A=[1.,1.]`, `B=[2.,0.]` (each sums to 2), and let two neighboring raw datasets yield `D0: A=[2,0], B=[2,0]`, `D1: A=[3,0], B=[2,1]`; `D1` adds one record with `(A=0,B=1)` to `D0`. For the two candidate scores, `score(D0)=[-P,-P]`, `score(D1)=[-P+4,-P]`, so the actual score L-infinity distance is 4 although the map is 1.

The public penalty is not necessarily arbitrary: in the source's formula, each marginal has two cells and `expectation=P/2=2**53+4`; with pure DP, marginal L1 sensitivity 1 and `d_measure=1/expectation`, `get_scale(...)` yields the desired finite expectation. AIM permits positive `measure_split` values that small. This parameter reachability was checked algebraically and in a Python model, not in native OpenDP.

### `_make_aim_select` — `privacy/selection-calibration`

**Conclusion:** With two candidate scores and pure DP selection scale 2, nonmonotonic `LInfDistance` input implies a claimed `epsilon=2*1/2=1` through `then_noisy_max`. The permute-and-flip probability of selecting B is `1/2` on `D0` and `exp(-4/2)/2` on `D1`, so an event has log-likelihood ratio 2. The underlying privacy-map formula is sourced from [the Rust selection implementation](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/measurements/noisy_top_k/mod.rs).

**Evidence:** Standalone NumPy 2.3.5 source-equivalent score computation and an analytic two-candidate selection distribution. See [regression model](../../../../../../../tools/tests/test_aim_score_rounding_model.py). The full OpenDP native/MBI model construction and release were **not** executed.

**Limitations:** A concrete constructed public `mbi.MarkovRandomField` and complete `AIM.make_marginals` integration remain to be executed. This is a source-level, conditional privacy-counterexample; the ordinary default penalty scale is much smaller. The separate [MST matrix-norm issue #117](https://github.com/opendp/opendp-audit/issues/117) does not cover the floating-point stability defect.

## Next checks

1. Native MBI integration test creating the stated consistent public model, two neighboring datasets, and AIM candidate selection with a sufficiently small permitted `measure_split`.
2. Conservatively bound floating-point score error, or compute the score with exact/higher precision and ensure safe conversion to `f64` before selecting.
3. Check other public offsets and model-projection precision paths for analogous score-stability amplification.
