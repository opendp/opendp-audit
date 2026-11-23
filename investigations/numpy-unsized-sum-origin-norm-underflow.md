---
schema_version: 1
upstream_commit: 7acfb2cdcee7d39fc26a6ade7edac15249c52f4b
updated: 2026-11-23
status: Partial
---

# Unsized NumPy sum: nonzero L2 origin underflows to zero in stability map

## Invariant and threat model

For an unbounded-size dataset, `make_np_sum` takes a two-dimensional NumPy array whose rows lie in an Lp ball with public radius `R` and center `O`; under `SymmetricDistance`, adding/removing a row must change the output sum's Lp norm by at most `R + ||O||p` for a single edit. This upper bound must be reflected **conservatively in the machine-number stability map** that is used to calibrate a private sum. The input domain's norm membership and the sensitivity calculation must agree on which vectors are admitted.

The intended public configuration can have extremely small but finite nonzero values. A single allowed insertion/removal must not be charged less than the resulting deterministic sum difference. This is a lower-level, direct NumPy extras path requiring `contrib` and `idealized-numerics`; it does not establish a flaw in ordinary fixed-size PCA mean estimation.

## Affected symbols and source audits

- [`array2_domain` and `NPArray2Domain`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/__init__.py) allow a positive or zero `norm`, nonzero one-dimensional `origin`, and `size=None`. Membership tests `_rows_within_norm(x-origin, norm, p)`.
- [`_rows_within_norm`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/_norm.py) avoids squaring-underflow via per-row scaling: `row_norm = np.linalg.norm(centered / scale, ord=p)`, compared to `norm/scale`. Both empty arrays and rows with exact centered offsets are accepted.
- [`make_np_sum`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/_make_np_sum/__init__.py) uses **unscaled** `np.linalg.norm(origin, ord=p)` in its unsized-domain stability map and computes `arg.sum(axis=0)`. Its [existing source report](../source/python/src/opendp/extras/numpy/_make_np_sum/__init__.py.md) has been amended with a distinct coverage key.
- [`with_privacy`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/_utilities.py) chains `then_gaussian(scale)` to L2 sum transformations when the requested measure is `ZeroConcentratedDivergence`.

The source [proof](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/_make_np_sum/make_np_sum.tex) uses the real-number inequality `||v||2 <= R + ||O||2` and explicitly ignores machine arithmetic under `idealized-numerics`. The *mathematical inequality* is correct; the concrete implementation of `||O||2` is not a conservative estimate.

## Reasoning and evidence

All numbers are exactly representable or conventional finite float64 inputs. Let `R=1e-200`, `O=[1e-200]`, `p=2`, `T=f64`, `num_columns=1`, `nan=False`, `size=None`. Define adjacent datasets:

```python
import numpy as np
D0 = np.empty((0, 1), dtype=np.float64)
D1 = np.array([[2e-200]], dtype=np.float64)
origin = np.array([1e-200], dtype=np.float64)
norm = 1e-200
```

For the single row of `D1`, `D1-origin=[[1e-200]]`. The domain's scaled norm calculation normalizes the centered row to 1, obtains `row_norm=1`, and compares it against `norm/scale=1`: it is **admitted**. For `D0`, the empty membership mask also succeeds. The arrays therefore differ by one insertion under `SymmetricDistance`.

The callback sums the row axis, giving `make_np_sum(D0)=[0]` and `make_np_sum(D1)=[2e-200]`. The actual L2 difference in one dimension is `2e-200`.

But NumPy 2.3.5's ordinary `np.linalg.norm(origin, 2)` returns `0.0`: squaring `1e-200` underflows to zero even though the input coordinate is normal. The constructor then sets `bound = norm + 0 = 1e-200`; its `map(1)` does not cover the actual `2e-200` output difference.

An even more pronounced mathematical witness uses `norm=0`, `O=[1e-200]`, and `D1=[[1e-200]]`: the radius-zero ball admits that row, yet `map(1)=0` for a positive output difference. The positive-radius case is preferable for checking nondegenerate configurations.

With `sigma=1e-200`, ideal additive Gaussian noise applied independently to the one-dimensional sum has its zCDP parameter `rho=Delta²/(2 sigma²)`. The reported sensitivity gives `rho=1/2`; the actual shift gives `rho=2`. Compute as `(Delta/sigma)**2/2` to avoid underflow in the independent calculation. This is a **conditional privacy-calibration consequence** assuming a correctly instantiated Gaussian mechanism using that scale, not a sampled native privacy-ratio demonstration.

**Executed independently:** NumPy 2.3.5 reproductions of origin-norm underflow, scaled membership for both neighboring arrays, sum outputs, and algebraic Gaussian zCDP; a Python standalone regression is committed at [`tools/tests/test_numpy_sum_origin_norm_model.py`](../tools/tests/test_numpy_sum_origin_norm_model.py). **Not executed:** native OpenDP FFI `Domain.member`, `Transformation.map`, Gaussian noise invocation, or complete DP measurement. Formal `idealized-numerics` assumptions must not be silently treated as a machine arithmetic proof.

## Findings

**Reproduced source-level stability-map counterexample; native end-to-end impact unverified.** Tracked by [audit #131](https://github.com/opendp/opendp-audit/issues/131), from [task #130](https://github.com/opendp/opendp-audit/issues/130). This is not the existing [integer dtype issue #123](https://github.com/opendp/opendp-audit/issues/123), the [SSCP origin issue #2952](https://github.com/opendp/opendp/issues/2952), or the [closed clamp underflow issue #2953](https://github.com/opendp/opendp/issues/2953). Targeted searches found no already merged or pending fix for the unsized NumPy *sum's* origin L2 norm.

## Unresolved questions

1. Execute native OpenDP regression at pinned SHA: `array2_domain` with the values above; check membership of both datasets; `make_np_sum.map(1)`; and the actual sum outputs.
2. Verify `make_private_np_sum` at `sigma=1e-200` and its runtime path for tiny scales. Noise-sampler numerical behavior is not covered by this audit.
3. Repair the map using scaled/numerically robust origin L2 norm and conservative upward rounding, including treatment of subnormal or overflow edge values. Add regression for `R=0`, `R>0` and `O=0`.
4. Consider implications of `idealized-numerics` source proofs that explicitly ignore machine arithmetic; avoid claiming more than the actual implementation provides.
