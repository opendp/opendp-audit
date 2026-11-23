---
schema_version: 1
upstream_commit: 7acfb2cdcee7d39fc26a6ade7edac15249c52f4b
updated: 2026-11-23
status: Partial
---

# AIM score-penalty rounding and private marginal selection

## Invariant and threat model

The OpenDP AIM mechanism adaptively selects marginals using differentially private selection on a vector of finite binary64 scores. A score is the difference between a private marginal's L1 discrepancy from a **public** synthetic marginal and the expected error of a future noise release. Its declared L-infinity stability must bound the actual score-vector distance in the floating-point execution, not merely the real-number L1 discrepancy.

The threat is a one-record change in the input dataset under unbounded-DP adjacency, where two one-way marginal dictionaries differ by one count in each marginal. A very large but permitted public expected-noise penalty can lead to representational rounding, making adjacent score vectors farther apart than their privacy map reports. The model and penalty are public; the selection itself remains private and is the prospective leak.

## Affected symbols and source audits

- [`_make_aim_scores` and `_make_aim_select`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_aim/__init__.py): score evaluation, L-infinity map, subsequent `then_noisy_max` composition. [AIM source audit](../source/python/src/opendp/extras/mbi/_aim/__init__.py.md).
- [`Count`, `get_scale`, `_noise_sensitivity`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_utilities/__init__.py): requires finite positive weight and translates a marginal L1 sensitivity to future noise scale.
- [`make_noisy_top_k` and `permute_and_flip`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/measurements/noisy_top_k/mod.rs): pure-DP L-infinity score vector sensitivity and two-candidate selection behavior.

This is distinct from [MST's induced matrix norm problem #117](https://github.com/opendp/opendp-audit/issues/117), which changes a utility ranking objective rather than magnifying floating-point sensitivity.

## Reasoning and evidence

Choose two binary columns `A`, `B`, with a public joint synthetic model whose one-way projections are

```text
A: [1.0, 1.0]
B: [2.0, 0.0]
```

The two projections are compatible because they both sum to two; a joint table with one mass at `(A0,B0)` and one at `(A1,B0)` realizes both.

Let private `D0` consist of two rows `(A0,B0)`, and `D1` additionally contain one row `(A0,B1)`. Then

```text
           D0 counts     D1 counts     exact L1 score
 A           [2,0]         [3,0]            2 -> 3
 B           [2,0]         [2,1]            0 -> 1
```

Both marginal output distances are one. With unit `Count.weight`, the `_make_aim_scores` map reports `d_out=1`.

Set a finite public penalty `P=float(2**54 + 8)`. Because each candidate has two cells, expected noise magnitude per cell is `E=P/2=2**53+4`. For `MaxDivergence` and L1 marginal sensitivity one, `get_scale(output_measure, d_measure=1/E, sensitivity=1)=E`; the formula permits this expectation through a small strictly-positive `measure_split`. In particular, all the values `P`, `E`, and `1/E` are finite. This is parameter *formula* reachability; actual AIM budget-search success is not tested.

The function's actual binary64 calculations produce:

```text
                    D0                 D1
 score(A)           -P                 -P+4
 score(B)           -P                 -P
```

The discrepancy of four instead of one arises from rounding of `2-P` and `3-P` at a spacing of four in `f64`; `2-P` is an exact midpoint that rounds back to `-P`, whereas `3-P` rounds toward `-P+4`. The L-infinity distance is 4, exceeding the declared 1.

Under the current pure-DP `then_noisy_max` with `scale=2`, the nonmonotonic map accounts `epsilon=2*d_in/scale=1`. `permute_and_flip` with two candidates and score gap `g` chooses the inferior one with probability `exp(-g/scale)/2`. The event `output=B` thus has probability `1/2` under `D0` and `exp(-2)/2` under `D1`, so `ln(Pr[B|D0]/Pr[B|D1])=2 > 1`. This establishes a conditional failure of the advertised privacy map for the composed two-candidate selection construction.

**Executed:** Standalone Python/NumPy 2.3.5 reproduced the exact source expression and four-unit score change, and Python mathematics evaluated the conditional selection ratio; the assertions also live in [regression tests](../tools/tests/test_aim_score_rounding_model.py). This does **not** execute the native OpenDP constructors, C FFI, MBI MarkovRandomField, or full AIM flow. No timing side channel or sampler failure is required by the hypothetical counterexample.

## Findings

**Source-level reproduced score-stability counterexample with conditional downstream privacy-accounting impact.** Filed [audit #125](https://github.com/opendp/opendp-audit/issues/125), associated with [task #124](https://github.com/opendp/opendp-audit/issues/124). This is distinct from [upstream #2789](https://github.com/opendp/opendp/issues/2789), which concerns numerical precision of *privacy budget comparisons*, and from earlier AIM PRs #2905/#2906 and [#3108](https://github.com/opendp/opendp/pull/3108), which do not bound score-subtraction rounding.

The exposed issue is not a demonstrated privacy breach in a default high-level AIM run. It requires tiny positive selection/measurement budget settings and completion of the native construction proof obligation.

## Unresolved questions

1. Native end-to-end regression: instantiate the stated public MBI model, construct source `_make_aim_scores` and `_make_aim_select` at the pinned revision, and check the map and score outputs.
2. Establish that all required AIM nested budget searches and model compatibility constraints permit the chosen public `measure_split`, with the exact penalty retained.
3. Examine conservative `float64` error bounds for subtraction, overflow/underflow, and `model.project` values, then select an implementable mitigation that does not understate sensitivity.
4. Review final upstream PRs for a fix before resolving #125.
