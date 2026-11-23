---
schema_version: 1
source: python/src/opendp/extras/sklearn/linear_model/_make_private_theil_sen/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/sklearn/linear_model/_make_private_theil_sen/__init__.py`

## Scope and assumptions

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

## Analysis

### `pairwise_predict` — `privacy/warning-side-channel`

**Conclusion:** The actual NumPy operation `dy/dx` is executed before `dx != 0` filtering. For input `[[0,0],[0,1]]`, division by zero emits a warning; adjacent input `[[0,0],[1,1]]` does not. A warnings handler observes the distinction without accessing the randomized DP output. The behavior is independent of the two-record shuffle.

**Evidence:** The [investigation](../../../../../../../../investigations/theil-sen-private-warning-side-channel.md) contains the executed standalone NumPy 2.3.5 witness for three random seeds and analyzes the upstream pending refactor.

**Limitations:** Native OpenDP execution and full FFI warning propagation not established. This coverage does not certify the transformation's probabilistic coupling or the private quantile's privacy map.

**Upstream disposition:** Existing open [PR #2845](https://github.com/opendp/opendp/pull/2845) replaces the callback with a zero-denominator mask before division and `np.errstate(all="ignore")`. It is a pending fix, not merged on reviewed `main`. No duplicate candidate-defect issue filed.

## Next checks

Execute native warning capture for the public `LinearRegression.fit` path and require warning-free `pairwise_slopes` behavior after PR #2845 merges.
