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

## Additional native verification: large public model, ordinary noise penalty

[Native integration test](../tools/integration/mbi_public_model_score_native.py) and [successful CI run](https://github.com/opendp/opendp-audit/actions/runs/45254507499) verify a *separate arithmetic witness for the same score-stability defect*. The run used the published OpenDP `0.16.0-nightly.20261122.1` wheel, `mbi==2.0.0`, NumPy `2.3.5`, and JAX binary64.

Build an **actual `mbi.MarkovRandomField`** over three binary attributes `A,B,C`, with public total `T=float(2**55+16)`. Its finite log-potentials are `0` at state `000` and `-1000` on all other states. The stored marginals vector is empty, so the **MBI variable-elimination oracle** computes public projections from the potentials. They are mutually consistent, concentrated in the zero cell, and within `~100` of `T` due to JAX normalization rounding. No inconsistent injected marginals are used.

Take two neighboring private inputs: `D0` with four `(A=0,B=0,C=0)` records and `D1` adding one `(A=0,B=1,C=0)` record. Their `A`, `B` one-way count tables change by entrywise L1 distance 1. Set both expectations to 2.0: the score penalty is just `P=2*2=4`, achievable with `MaxDivergence` `d_measure=0.5` and sensitivity 1 (no extreme privacy-budget setting). The *actual native OpenDP* scorer yields:

```text
                     D0            D1        D1-D0
A score              S             S-16       -16
B score              S             S            0
Declared LInf sensitivity: 1
Actual LInf sensitivity: 16
```

Here `S` is the roughly `3.602879701896408e16` public-model discrepancy after JAX normalization, not a manually assigned score.

The native `_make_aim_scores` transformation accepts both input dictionaries, returns those scores, and `map(d_in)` returns 1. The native scorer composed with `then_noisy_max(scale=4)` reports **epsilon=0.5**, whereas the worst-case two-candidate output event has exact permute-and-flip log likelihood ratio **4.0** based on these realized score vectors. Furthermore, the library's own **`_make_aim_select`**, called with `d_out=d_measure=0.5`, constructed successfully, `map(d_in)=0.5`, and its actual randomized selection produced a valid clique. The internal scorer/selector privacy-map counterexample is therefore **native verified**.

**Limit:** This test directly invokes the internal selection constructor; the full `make_contingency_table` pipeline, including estimation/reconstruction from previous DP marginals and its public-model reachability constraints, was not executed. The large but finite public model total is the remaining high-level question. The original *large expected-noise penalty* witness above is independently valid under its source-equivalent formula, but only the *large model with ordinary penalty* witness has been fully executed through native OpenDP/MBI.

## Public AIM algorithm release and observable DP violation

A subsequent [successful native release CI](https://github.com/opendp/opendp-audit/actions/runs/45255535102) exercised the supported `AIM.make_marginals` method with the same consistent MBI model, not merely `_make_aim_select`. Its input is three binary `UInt32` columns bounded to `[0,1]`, under `FrameDistance<SymmetricDistance>` with `d_in=[Bound(per_group=1)]`. The two native Polars frames have four `000` rows and those four plus one `010` row, with identical public schemas.

The test uses `AIM(queries=[Count(("A",)),Count(("B",))], rounds=1, measure_split=0.5)`, `d_out=1.0`. The only custom component is a deterministic estimator returning the same precomputed public `MarkovRandomField`, **independent of private input**; this is permitted by OpenDP's `honest-but-curious` callback contract, with the feature explicitly enabled. The actual compiled `measurement.map(d_in)` returns `epsilon=1.0`. Both neighboring real `measurement(pl.LazyFrame(...))` invocations completed, and their returned `Marginals.cliques()` each contains exactly one of the private candidate cliques `A` and `B`.

The selection uses a public expected-noise penalty `P=4` (`d_measure≈0.5`), not the extreme penalty from the original analysis. The real one-way score vectors are tied on the four-row input, then the `A` score decreases by 16 under one-row insertion, while `B` stays fixed. The private selector is calibrated to approximately `epsilon_select=0.5` at scale `s≈4`; its observable `A` event probabilities are `1/2` versus `exp(-16/s)/2`, giving log likelihood ratio `16/s≈4`. This exceeds the whole advertised `epsilon=1.0` of the public `AIM.make_marginals` measurement. The selected clique remains observable in the released `Marginals` structure even after noisy counting; later estimator postprocessing cannot hide that event.

This is a **native successful-release counterexample for the public AIM algorithm method**, with analytic event probability from actual native scores and the inspected Rust permute-and-flip algorithm. It is not merely a floating-point model or an assertion about an unreachable intermediate. The outer `Context.contingency_table` workflow and its model-re-estimation path remain untested and could constrain model totals.

[Native release regression](../tools/integration/mbi_large_model_algorithm_release_native.py) · [CI](https://github.com/opendp/opendp-audit/actions/runs/45255535102) · [audit #125](https://github.com/opendp/opendp-audit/issues/125).

## Findings

**Native verified public AIM algorithm release-path privacy violation, plus a separate source-level large-penalty witness.** Filed [audit #125](https://github.com/opendp/opendp-audit/issues/125), associated with [task #124](https://github.com/opendp/opendp-audit/issues/124). This is distinct from [upstream #2789](https://github.com/opendp/opendp/issues/2789), which concerns numerical precision of *privacy budget comparisons*, and from earlier AIM PRs #2905/#2906 and [#3108](https://github.com/opendp/opendp/pull/3108), which do not bound score-subtraction rounding.

The native full `AIM.make_marginals` release counterexample with an ordinary penalty of 4 no longer requires tiny positive budget settings; it does require a large public synthetic-model total and the permitted honest-but-curious custom estimator. Only the outer `Context.contingency_table` wrapper's default model-fitting path remains unverified.

## Unresolved questions

1. Validate `Context.contingency_table` model-reuse/fitting constraints with a large MBI model; the standalone public `AIM.make_marginals` measurement now constructs and releases natively.
2. For the separate original huge-penalty witness, establish that all required AIM nested budget searches permit the very small public `measure_split`.
3. Examine conservative `float64` error bounds for subtraction, overflow/underflow, and `model.project` values, then select an implementable mitigation that does not understate sensitivity.
4. Review final upstream PRs for a fix before resolving #125.
