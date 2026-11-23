---
schema_version: 1
upstream_commit: a010591f55b1713c926f8e355091471634480307
updated: 2026-11-23
status: Partial
---

# Batch-shape-dependent logistic gradients invalidate one-record sensitivity

## Invariant and threat model

OpenDP's non-deprecated DP logistic regression constructs private gradient steps for a `SklearnFit` dataset under `SymmetricDistance`. Its internal `make_user_transformation` advertises a 1-Lipschitz rowwise map. Each input record `(X[i], y[i])` should produce an independent gradient row so one insertion or deletion changes only one gradient row. Subsequent per-row L2 clipping and summation then use the claimed one-row sensitivity to calibrate Gaussian noise. A difference in any previously existing record's gradient after inserting a different row breaks the intermediate invariant, and a sum-distance larger than the clipping radius breaks the end-to-end step's sensitivity claim.

This audit considers finite binary64 arithmetic in actual NumPy/OpenBLAS and a fixed finite model parameter `theta`. It does **not** establish an unconditional privacy breach in the full iterative logistic estimator, which first sets `theta=0` and later chooses it adaptively from previous private releases. OpenDP explicitly requires the `idealized-numerics` feature; its ideal arithmetic reasoning does not cover this source-dependent BLAS reduction discrepancy.

## Affected symbols and source audits

- [`per_example_gradients` and `log_regression_train`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/sklearn/linear_model/_make_private_logistic_regression/__init__.py), with [source audit](../source/python/src/opendp/extras/sklearn/linear_model/_make_private_logistic_regression/__init__.py.md).
- [`make_np_clamp`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_clamp/__init__.py) and [`_rows_within_norm`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_norm.py) for the clipping output domain and its numerical membership test.
- [`make_np_sum`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_sum/__init__.py) for unsized L2 sum map `lambda d_in:d_in*norm` when the zero origin is used. This is **not** the unrelated [nonzero-origin norm underflow bug #131](https://github.com/opendp/opendp-audit/issues/131).
- [Rust adaptive composition](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/combinators/sequential_composition/adaptive/mod.rs) for fixed per-iteration zCDP budgets and query checking.
- [Upstream logistic test suite](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/test/extras/test_logistic_regression.py) tests simple row-replacement stability but not adversarial cancellation across batch-shape-dependent BLAS kernels.

## Reasoning and executed evidence

The following source-equivalent program was executed in Python 3.13.5 with NumPy 2.3.5, SciPy 1.17.0, OpenBLAS 0.3.30 on x86-64 SkylakeX:

```python
import numpy as np
from scipy.special import expit

theta = np.array([1e16, -1e16, -10., 3., -3., 0., -1., 10.])
X0 = np.ones((3, 8))
X1 = np.vstack([X0, np.zeros((1, 8))])
y0, y1 = np.zeros(3), np.zeros(4)

def gradients(X, y):
    # The tested case requires no imputation; fit_intercept=False.
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    z = np.nan_to_num(X @ theta, nan=0.0)
    return (expit(z) - y)[:, None] * X, z

G0, z0 = gradients(X0, y0)
G1, z1 = gradients(X1, y1)
assert np.array_equal(z0, [2., 2., -4.])
assert np.array_equal(z1, [-4., -4., -4., 0.])

radius = np.sqrt(8.)
assert (np.linalg.norm(G0, axis=1) < radius).all()
assert (np.linalg.norm(G1, axis=1) < radius).all()

sensitivity = np.linalg.norm(G0.sum(axis=0) - G1.sum(axis=0))
assert sensitivity > radius
```

The actual sum of gradient rows is `[1.7795803659178562] * 8` for `D0`, and `[0.05395862988627467] * 8` for `D1`. The Euclidean distance is **4.880795325243335**, whereas the zero-origin unsized-sum stability map at one input change is **2.8284271247461903**. The sensitivity factor is about **1.7256**.

The trigger is not a change of input records already present: `X0 = X1[:3]` and `y0 = y1[:3]`. The new fourth row is zero and yields a zero gradient. The source uses a whole-matrix multiply `X @ theta`, and BLAS shape-dependent summation changes the computed first two original logits from `2` to `-4`. In fact, within `D0`, the three identical rows produce distinct logits `[2,2,-4]`; this is definitive evidence of failure of *row-by-row numerical semantics* in that environment.

The per-row gradients are strictly bounded by `radius` (largest gradient norm around **2.4913**); therefore the clipping function's source `_rows_within_norm` predicate retains every row exactly. The `make_np_sum` input is truly a matrix of bounded float64 gradient vectors, and no nonzero origin or integer overflow is involved.

### Conditional privacy implication

For the Gaussian-noise step with standard deviation `sigma=radius`, the declared zero-origin sum sensitivity gives ideal zCDP bound `rho = radius²/(2*sigma²) = 0.5`. At the specific conditional public/current parameter vector `theta`, the observed pair of deterministic means is farther apart: the necessary bound would be `rho = observed²/(2*sigma²)≈1.488885`. The ratio between necessary and claimed rho is approximately 2.98. These values are algebraic Gaussian-accounting calculations, **not** observed stochastic privacy loss from the native OpenDP sampler.

The first iteration's `theta=0` does not trigger this witness. For later iterations, `theta` depends on earlier private noisy releases. Whether a positive-probability reachable range of `theta` yields a full-estimator privacy violation remains an unresolved proof obligation. This audit demonstrates an invalid **per-step stability certificate** under concrete floating-point arithmetic, not a successful attack on an end-to-end fitted classifier.

### Verification details

**Executed:** The above NumPy/SciPy gradient and sum arithmetic in the available Python environment, direct inspection of row norms and analytic zCDP; a [portable-source-aware standalone regression](../tools/tests/test_logistic_gradient_batch_blas_model.py) records the exact witness while marking it skipped on BLAS implementations where this cancellation vector does not cause the same effect.

**Not executed:** OpenDP native Rust/Python FFI; a private Gaussian release; full `make_private_logistic_regression`, Context API fitting, and formal privacy proof. Only the conditional source-equivalent numerical invariant has been reproduced. Version/platform dependence is documented to avoid implying universal kernel behavior.

## Findings

**New reproducible conditional privacy-sensitive numerical defect:** [audit #142](https://github.com/opendp/opendp-audit/issues/142). Work claim and scope: [#140](https://github.com/opendp/opendp-audit/issues/140).

Targeted open and closed searches found no equivalent upstream or audit issue. [Upstream #3113](https://github.com/opendp/opendp/pull/3113) introduced logistic regression and merged October 2026. [Open PR #3204](https://github.com/opendp/opendp/pull/3204) refactors sklearn mixins but does not alter the affected implementation file, so the defect remains present on upstream `main` at `a010591f55b1713c926f8e355091471634480307`.

## Unresolved questions

1. **Native integration:** construct a `SklearnFit` domain with unknown row count and eight feature columns; create the same `gradient >> clamp >> make_private_np_sum` chain at public/current `theta`, verify `map(1)` and deterministic gradient output on the affected BLAS platform.
2. **Reachability:** demonstrate an open neighborhood of late-iteration `theta` values reachable after a private first iteration where this effect persists; quantify an unconditional privacy accounting violation, if any. Otherwise clearly delimit the problem to intermediate certificates and idealized arithmetic assumptions.
3. **Repair:** perform a genuinely per-row reduction with a fixed deterministic arithmetic order independent of input batch size/row position, rather than relying on batched BLAS to preserve this property.
4. **Regression:** add tests for large cancellation, different batch sizes, row reorderings, both intercept settings and multiple BLAS backends. Avoid requiring identical outputs across platforms where their numerical kernels differ; enforce the rowwise relationship locally on each supported platform.
