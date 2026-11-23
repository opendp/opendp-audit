---
schema_version: 1
source: python/src/opendp/extras/sklearn/linear_model/_make_private_theil_sen/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/sklearn/linear_model/_make_private_theil_sen/__init__.py`

## Scope and assumptions

- **Additional scope:** Public NumPy PRNG seeding and one-record stability of the random pair-matching function; separate from the earlier warning-channel property. See the [seeded-shuffle investigation](../../../../../../../../investigations/theilsen-seeded-shuffle-stability.md).
- **Audit scope:** `pairwise_predict` and the `make_pairwise_predict` / `make_private_theil_sen` call chain for pre-noise warnings related to degenerate pairs, with current code and open refactor PR compared.
- **Invariant:** The data-dependent behavior of a private release is restricted to the claimed randomized output, not also conveyed through Python warning handlers or stderr.
- **Assumptions:** Finite float input with exactly two rows, one substitution under symmetric distance, two public reference points. Native OpenDP not run; standard NumPy warning behavior reproduced.
- **Source links:** [current main](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/sklearn/linear_model/_make_private_theil_sen/__init__.py); [open fix PR #2845](https://github.com/opendp/opendp/pull/2845); [cross-file investigation](../../../../../../../../investigations/theil-sen-private-warning-side-channel.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `opendp.extras.sklearn.linear_model._make_private_theil_sen.pairwise_predict` | privacy/warning-side-channel | Audited | `a010591f55b1713c926f8e355091471634480307` | Reproduced private-dependent warning for two adjacent two-row datasets; [investigation](../../../../../../../../investigations/theil-sen-private-warning-side-channel.md), [pending fix #2845](https://github.com/opendp/opendp/pull/2845). |
| `opendp.extras.sklearn.linear_model._make_private_theil_sen.make_pairwise_predict` | privacy/callback-warning-propagation | Partial | `a010591f55b1713c926f8e355091471634480307` | Executes affected callback once per run before private quantile; native OpenDP callback and stderr not yet tested. |
| `opendp.extras.sklearn.linear_model._make_private_theil_sen.make_private_theil_sen` | privacy/noise-chain-warning-isolation | Partial | `a010591f55b1713c926f8e355091471634480307` | Chained private-quantile measurements cannot retroactively suppress warnings emitted during pairwise preprocessing. Full release path requires native integration testing. |
| `opendp.extras.sklearn.linear_model._make_private_theil_sen.pairwise_predict` | privacy/seeded-shuffle-row-stability | Audited | `a010591f55b1713c926f8e355091471634480307` | [Seeded-shuffle witness](#seeded-shuffle-row-stability), [investigation](../../../../../../../../investigations/theilsen-seeded-shuffle-stability.md). |
| `opendp.extras.sklearn.linear_model._make_private_theil_sen.make_pairwise_predict` | privacy/nondeterministic-transformation-contract | Partial | `a010591f55b1713c926f8e355091471634480307` | [Stability-map boundary](#seeded-shuffle-row-stability), [upstream #2928](https://github.com/opendp/opendp/issues/2928). |

## Analysis

### `pairwise_predict` — `privacy/warning-side-channel`

**Conclusion:** The actual NumPy operation `dy/dx` is executed before `dx != 0` filtering. For input `[[0,0],[0,1]]`, division by zero emits a warning; adjacent input `[[0,0],[1,1]]` does not. A warnings handler observes the distinction without accessing the randomized DP output. The behavior is independent of the two-record shuffle.

**Evidence:** The [investigation](../../../../../../../../investigations/theil-sen-private-warning-side-channel.md) contains the executed standalone NumPy 2.3.5 witness for three random seeds and analyzes the upstream pending refactor.

**Limitations:** Native OpenDP execution and full FFI warning propagation not established. This coverage does not certify the transformation's probabilistic coupling or the private quantile's privacy map.

**Upstream disposition:** Existing open [PR #2845](https://github.com/opendp/opendp/pull/2845) replaces the callback with a zero-denominator mask before division and `np.errstate(all="ignore")`. It is a pending fix, not merged on reviewed `main`. No duplicate candidate-defect issue filed.

### Seeded shuffle row stability

**Reproduced finite counterexample:** The unsized `make_pairwise_predict` transformation with `runs=1` advertises `map(1)=2` but calls globally seeded `np.random.shuffle`. Let `X=[(i,i*i) for i=1..10]` and `Y=X+[(11,121)]`; they differ by one insertion under symmetric distance. Reset NumPy 2.3.5's public `seed(42)` before each `pairwise_predict` invocation with cuts `[0,2]`. The five old and five new predictions are disjoint: **actual output symmetric distance 10**, versus mapped **2**. On a same-size record replacement, the output distance is 2 and the fixed-size map is 2. All values are finite, and there are no degenerate-pair warnings.

This is a failure of a **pointwise deterministic stability interpretation conditioned on an externally controlled NumPy PRNG**. Uniform secret independent shuffle may support a stochastic coupling argument, but the OpenDP transformation contract does not formally specify this. The witness does **not** demonstrate unconditional DP loss in the complete private Theil-Sen estimator.

**Evidence:** [Full investigation](../../../../../../../../investigations/theilsen-seeded-shuffle-stability.md), [standalone source-equivalent regression](../../../../../../../../tools/tests/test_theilsen_seeded_shuffle_model.py). Executed in NumPy 2.3.5; native OpenDP/FFI and downstream private quantiles unverified.

**Deduplication:** [Upstream #2928](https://github.com/opendp/opendp/issues/2928) already covers randomized transformations and undefined coupling semantics. [Upstream #2950](https://github.com/opendp/opendp/issues/2950) covers the earlier insertion/odd-length truncation problem. [Open PR #2845](https://github.com/opendp/opendp/pull/2845) replaces the global NumPy shuffle with `get_np_csprng().shuffle`, addressing the public-seed control but not itself proving a framework-level coupling. No duplicate audit defect issue is warranted.

## Next checks

Execute native warning capture for the public `LinearRegression.fit` path and require warning-free `pairwise_slopes` behavior after PR #2845 merges.
