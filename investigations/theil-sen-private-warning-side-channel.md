---
schema_version: 1
upstream_commit: a010591f55b1713c926f8e355091471634480307
updated: 2026-11-23
status: Partial
---

# Theil–Sen pairwise prediction emits an observable private-data-dependent NumPy warning

## Invariant and threat model

OpenDP's `make_private_theil_sen` constructs a DP measurement by composing a randomized pairwise-prediction transformation with private quantile selection. Execution should not disclose information about the input database through Python warnings, stderr, or exception channels outside the private measurement result. For a valid adjacent pair of input databases, a warning triggered deterministically on only one of the databases is an observable privacy side channel.

The scope is the existing Python implementation on upstream `a010591f55b1713c926f8e355091471634480307`, with two valid finite `float64` records, `runs=1`, `x_cuts=[0.25,0.75]` and a positive private-quantile noise scale. A user can register a standard Python `warnings.catch_warnings` handler or observe default stderr warnings. In a repeated-query setting, Python's default once-per-location warning filter can mute later repetitions, but a fresh process or `simplefilter("always")` preserves the distinguishing signal.

## Affected symbols and source audits

- [`pairwise_predict` and `make_private_theil_sen`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/sklearn/linear_model/_make_private_theil_sen/__init__.py): computes `dx,dy=(p2-p1).T`, evaluates `dy/dx` before excluding `dx == 0`, and uses `pairwise_predict` inside `make_pairwise_predict`'s callback chained to private quantiles.
- [`LinearRegression.fit`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/sklearn/linear_model/__init__.py) invokes the same `self.measurement`, making this a normal public estimator path.
- [Existing upstream Theil–Sen tests](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/test/extras/test_linear_regression_numpy.py) test continuous normal covariates but not a repeated-feature-value pair or warnings.
- [Source coverage](../source/python/src/opendp/extras/sklearn/linear_model/_make_private_theil_sen/__init__.py.md).

## Reasoning and evidence

### Deterministic neighboring-database witness

For a domain `dp.numpy.array2_domain(size=2, num_columns=2, T=float)` and `dp.symmetric_distance()`, these two records are at symmetric distance `2` (one replacement), and are finite, valid members:

```python
import numpy as np

x = np.array([[0., 0.], [0., 1.]], dtype=np.float64)
x_prime = np.array([[0., 0.], [1., 1.]], dtype=np.float64)
cuts = np.array([0.25, 0.75], dtype=np.float64)
```

For `x`, all pairings have `dx=0` and `dy != 0`; evaluating `dy/dx` emits NumPy's `RuntimeWarning: divide by zero encountered in divide`. For `x_prime`, `dx=±1`, so no such warning occurs. Random shuffle of the two rows changes signs but not whether the warning arises.

The preceding operation is outside the private quantile mechanism. The final `points.T[dx != 0]` filter removes degenerate predictions **after** the warning has been emitted, so it does not suppress the independent warning channel.

**Executed standalone witness (NumPy 2.3.5, not an OpenDP native integration):** Reproduced the source `pairwise_predict` body, wrapped the call in `warnings.catch_warnings(record=True)` with `warnings.simplefilter("always")`, and tested seeds `0,1,2` for both inputs. Every seed emitted exactly one `divide by zero encountered in divide` warning for `x`, while `x_prime` emitted none. Outputs were shapes `(0,2)` and `(1,2)` respectively; neither call raised an exception.

Example:

```python
import numpy as np
import warnings

for arg in (x, x_prime):
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        np.random.seed(0)
        out = pairwise_predict(arg, cuts)
        print(out.shape, [str(w.message) for w in seen])
# (0, 2) ['divide by zero encountered in divide']
# (1, 2) []
```

**Evidence limitation:** Native OpenDP was not installed in the local container, so warning propagation through the actual `make_user_transformation` callback and `LinearRegression.fit` release has not been observed end-to-end. The source contains no `np.errstate` in the affected callback, and ordinary Python/NumPy execution shows the independent warning.

### Existing remediation in open PR

The upstream [Theil–Sen refactor PR #2845](https://github.com/opendp/opendp/pull/2845) is **open, not merged** as of this review. Its revision `d5349c44f4d532bafa0e8dc5cbb5eeb11ccf96f1` replaces the callback with `pairwise_slopes`, calculates a `valid = dx != 0` mask, divides only `dy[valid] / dx[valid]`, places calculations inside `with np.errstate(all="ignore")`, and keeps only finite slopes. This specifically addresses the observed warning channel. PR #2845 also changes the public estimator API, so integration tests must account for the new `SklearnFit` format.

Merged [PR #3046](https://github.com/opendp/opendp/pull/3046) addressed pairwise *stability bounds*, not warnings; no equivalent standalone issue was found in open/closed upstream or audit issues. We therefore do **not** file a duplicate candidate-defect issue while a directly relevant upstream fix PR exists.

## Findings

- **Source-level finding:** Current `main` emits an observable private-data-dependent warning before DP postprocessing on an elementary adjacent input pair. The raw NumPy callback warning is independently reproduced.
- **Upstream disposition:** **Pending PR** [#2845](https://github.com/opendp/opendp/pull/2845). No new candidate defect filed because an existing PR specifically fixes the observed behavior.
- **Potential impact:** Privacy side channel via Python warning handlers/stderr; requires confirmation of propagation during native OpenDP release. Not a proof that the *randomized returned coefficients* violate their declared privacy map.
- **Audit task:** [#133](https://github.com/opendp/opendp-audit/issues/133).

## Unresolved questions

1. Run `make_private_theil_sen` on the two-row adjacent input pair under `warnings.catch_warnings` and confirm observable warning propagation through OpenDP's FFI callback and Python estimator.
2. Add a regression to PR #2845 requiring no warning and no data-dependent exception across zero denominator, under/overflow, and nonfinite predictions.
3. Revisit disposition once PR #2845 merges; mark the affected source row stale on relevant merge and close any reopened tracking if the fix is verified.
