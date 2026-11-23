---
schema_version: 1
source: python/src/opendp/extras/sklearn/linear_model/_make_private_logistic_regression/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/sklearn/linear_model/_make_private_logistic_regression/__init__.py`

## Scope and assumptions

- **Audit scope:** Non-deprecated `per_example_gradients`, `log_regression_train` and `make_private_logistic_regression`. Verify numerical row-separability of gradients, the actual L2 sensitivity after per-row clipping, and wiring to adaptive composition. The overall fitted classifier's end-to-end privacy distribution, other sklearn estimators, and all native Rust proofs are excluded.
- **Invariants:** Under add/remove `SymmetricDistance`, inserting one aligned feature/target record must change at most one output row of the transformation with `stability_map=lambda b_in:b_in`. After norm-`R` clipping, `make_np_sum` must change by at most `R` for one insertion before Gaussian noise. In adaptive training, each private gradient release must consume one allocated budget before exposure.
- **Assumptions:** Features are an unsized `numpy.array2_domain(T=float,num_columns=8)`; targets are a matching unsized float vector; public `fit_intercept=False`, public gradient clipping radius `sqrt(8)`, finite public/current model weight vector `theta`. Independent reproduction ran NumPy 2.3.5/SciPy 1.17.0/OpenBLAS 0.3.30 (SkylakeX). Actual NumPy BLAS reduction order and row-position/shape-dependent rounding are **not** assumed idealized.
- **Pinned sources:** [logistic gradient/fit](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/sklearn/linear_model/_make_private_logistic_regression/__init__.py), [clamp](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_clamp/__init__.py), [sum](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_sum/__init__.py), [adaptive composition](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/combinators/sequential_composition/adaptive/mod.rs), [upstream logistic tests](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/test/extras/test_logistic_regression.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `per_example_gradients` | privacy/rowwise-gradient-stability | Audited | `a010591f55b1713c926f8e355091471634480307` | [BLAS batch-shape counterexample](#blas-batch-shape-counterexample), [cross-file investigation](../../../../../../../../investigations/logistic-gradient-batch-shape-privacy.md), [audit #142](https://github.com/opendp/opendp-audit/issues/142). |
| `log_regression_train` | privacy/clipped-gradient-sum-calibration | Audited | `a010591f55b1713c926f8e355091471634480307` | [Conditional sensitivity underestimate](#conditional-sensitivity-underestimate), [independent test](../../../../../../../../tools/tests/test_logistic_gradient_batch_blas_model.py). |
| `make_private_logistic_regression` | privacy/iterative-budget-composition | Partial | `a010591f55b1713c926f8e355091471634480307` | [Adaptive budget wiring](#adaptive-budget-wiring); complete estimator and native Gaussian distribution unverified. |

## Analysis

### BLAS batch-shape counterexample

The implementation computes `z = np.nan_to_num(X @ theta[:d] + intercept)`, followed by the per-record residual `expit(z) - y` and multiplication into gradient rows. Mathematically, every `X[i] @ theta` is a function of `X[i]` alone. The actual batched NumPy/OpenBLAS computation is **not numerically row-separable**, because the reduction algorithm depends on batch shape and row position.

With `fit_intercept=False` and finite public/current weights `theta = [1e16, -1e16, -10, 3, -3, 0, -1, 10]`, let `D0.X` have three identical all-ones eight-feature rows and `D0.y` be all zeros. Let `D1` insert one row with eight zero features and target zero. The new and old datasets are at symmetric distance 1. On the verified OpenBLAS build, `X0 @ theta = [2, 2, -4]`, but `X1 @ theta = [-4, -4, -4, 0]`. Thus **two unchanged existing rows change their gradients**; even within `D0`, three identical feature vectors give different computed logits. This violates the stated row-by-row `SymmetricDistance` map of 1 under the actual finite-precision execution.

**Executed:** Source-equivalent NumPy/SciPy arithmetic was run in Python 3.13, NumPy 2.3.5, SciPy 1.17.0, OpenBLAS 0.3.30. The counterexample is pinned in [standalone regression](../../../../../../../../tools/tests/test_logistic_gradient_batch_blas_model.py); test skips, rather than claiming verification, on BLAS kernels where this exact cancellation witness does not reproduce. This is **not** native OpenDP execution. Existing upstream tests for ordinary row replacement and insertion were inspected; they do not exercise this cancellation-induced BLAS dispatch switch.

### Conditional sensitivity underestimate

The sum change in the gradient vectors is `||sum(grad(D0))-sum(grad(D1))||2 = 4.880795325243335`. Each row's gradient norm is at most approximately 2.492 in `D0` and 0.051 in `D1`. With public `clip_norm=sqrt(8)≈2.8284271247461903`, the downstream `make_np_clamp` accepts all gradient rows unchanged, as its numerical scaled-domain predicate verifies membership; there is no clipping to repair the issue.

With unsized gradient output domain and zero origin, `make_np_sum.map(1)` claims L2 sensitivity **2.8284271247461903**, while the actual computed sum changes by **4.880795325243335**, approximately **1.726 times greater**. The sum map would be sufficient only if the upstream gradient transformation's output rowwise distance map were valid, which this exact witness refutes.

For an ideal Gaussian release at `sigma=clip_norm`, the per-step claimed `rho=0.5` but the conditional actual shift would require `rho≈1.488885`, about **2.98 times** the claimed privacy parameter. This is a **conditional composed-step privacy-calibration witness** at a specified current model weight vector, not evidence that the initial `theta=0` step is affected or that the complete random iterative estimator's unconditional zCDP guarantee was broken.

### Adaptive budget wiring

`make_private_logistic_regression` validates known-size adjacency `d_in` parity, constructs a per-step zCDP budget with `binary_search_param` and `make_adaptive_composition`, and uses a list of that fixed `rho_per_step` for `max_iter` iterations. Within `log_regression_train`, every iteration constructs `gradient >> make_np_clamp >> make_private_np_sum` and calibrates its scale with `binary_search_chain(d_in=d_in,d_out=d_mid)`, then queries the adaptive compositor.

The pinned [Rust adaptive composer](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/combinators/sequential_composition/adaptive/mod.rs) checks the query's reported map against the remaining budget and consumes the budget entry before invoking the private measurement. Thus the source-level budget gating appears present; **the new defect arises from the upstream gradient stability map**, not an omitted budget entry. This review does not certify the full Rust composition proof or the complete native Python/FFI path. Numerical output at extreme public hyperparameters remains unverified.

## Findings and next checks

**Finding:** [audit #142](https://github.com/opendp/opendp-audit/issues/142) records a reproducible floating-point, BLAS-dependent rowwise-stability failure and downstream conditional Gaussian sensitivity underestimate. **Upstream disposition:** Unreported on `a010591f55b1713c926f8e355091471634480307`, no matching existing fix PR found in targeted searches. [Upstream PR #3204](https://github.com/opendp/opendp/pull/3204) changes sklearn mixins but does not change this gradient implementation. **Verification:** Reproduced in standalone NumPy/SciPy; **native OpenDP unverified**.

This lower-level numerical failure is relevant to the concrete runtime even though the estimator requires `idealized-numerics`, whose mathematical abstraction ignores rounding. The claim must not be extended to end-to-end exploitable privacy loss without a constructed reachable subsequent-iteration transcript.

Next: replace `X @ theta` with an explicitly row-local, deterministic reduction; test insertion and reordering across BLAS implementations and adversarial cancellation; run native OpenDP `make_user_transformation`→clamp→private sum and assess reachable full-model likelihood ratios.
