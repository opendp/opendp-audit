---
schema_version: 1
upstream_commit: a010591f55b1713c926f8e355091471634480307
updated: 2026-11-23
status: Partial
---

# NumPy private mean accepts a public zero-row domain and divides by zero

## Scope and claimed invariant

A private mean is meaningful only if the row count is positive. The non-deprecated `make_private_np_mean` API requires a publicly sized `array2_domain` but does not require the declared size to be greater than zero. This review traces the constructor, optional row clamp, sum/noise composition, and final postprocessing for the accepted `size=0` case.

The relevant property is **constructor-time totality**: if the mean is undefined for a valid domain, the constructor should fail before invoking the private mechanism, not produce a NaN vector from an execution. This is a correctness/availability issue, **not a demonstrated privacy leak**.

## Pinned source and control flow

1. [`numpy.array2_domain`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/__init__.py) calls `_check_nonnegative_int(size, "size")`, permitting zero. Its carrier member predicate accepts an empty NumPy array with shape `(0,num_columns)`.
2. [`make_private_np_mean`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_mean/__init__.py) rejects only `size is None`. It computes `privacy_measure` from public `p`, builds `make_private_np_sum(...,scale*size)`, and appends `_new_pure_function(lambda sums: np.array(sums)/size)`.
3. [`make_np_sum`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_sum/__init__.py) sums axis zero. For an empty matrix of known width, that is a finite vector of zeros. [`with_privacy`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/_utilities.py) selects the Laplace or Gaussian mechanism, both of which receive public `scale*0=0`.
4. [`make_np_clamp`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_clamp/__init__.py) also accepts empty rows: its reduction uses `initial=0` and the other axis-one operations return empty matrices. Thus supplying `norm` does not reject the zero-size domain.

## Executed reproduction

Source-equivalent NumPy 2.3.5, both `float32` and `float64`, and both `p=1` and `p=2`, yields:

```python
import numpy as np
import warnings

X = np.empty((0, 2), dtype=np.float64)
assert np.array_equal(X.sum(axis=0), np.array([0., 0.]))
with warnings.catch_warnings(record=True) as recorded:
    warnings.simplefilter("always")
    result = np.array(X.sum(axis=0)) / 0
assert np.isnan(result).all()  # [nan, nan]
assert any("invalid value encountered in divide" in str(w.message)
           for w in recorded)
```

The [independent model](../tools/tests/test_numpy_private_mean_zero_size_model.py) reproduces the exact final arithmetic, optionally traverses the empty NumPy clamping primitives for both p values, checks zero noise-scale construction algebra, and confirms ordinary nonempty mean postprocessing is finite. The observed NumPy result is `[nan,nan]` plus `RuntimeWarning: invalid value encountered in divide`.

**Executed:** NumPy 2.3.5 source-equivalent computation with warnings captured. **Not executed:** installed OpenDP, the native FFI, the actual zero-scale sampler, or full `Measurement.invoke`. The statement that the sampler returns a zero shift at scale zero follows the source's intended noise contracts and is not a runtime observation of the full library.

## Privacy implications and overlap

Since the input domain enforces **public `size=0`**, it contains only one dataset for the fixed public width. The invalid result and warning are consequently data-independent and cannot by themselves distinguish private neighbors. The reviewed code selects the same pure-DP/zCDP mechanism based on public `p`; no parameter-underestimation or unexpected privacy budget cancellation was established. The related NumPy sum defects [#131](https://github.com/opendp/opendp-audit/issues/131), [#141](https://github.com/opendp/opendp-audit/issues/141), [#143](https://github.com/opendp/opendp-audit/issues/143), and resolved upstream [#3153](https://github.com/opendp/opendp/issues/3153) concern different properties.

[New correctness issue #160](https://github.com/opendp/opendp-audit/issues/160) records the constructor's missing positive-size precondition and offers a straightforward repair. Targeted open/closed issue and PR searches found no coverage of this specific zero-row mean case.

## Proposed repair and tests

After the existing `if size is None` check in `make_private_np_mean`, reject `size == 0` with an explicit `ValueError` before noise calibration. Add integration tests for `size=0` with/without `norm`, both `p=1,2`, and positive-size controls. Do not change the permissive zero-size semantics of `array2_domain` globally; it is a meaningful domain for other transformations.

[Audit task #158](https://github.com/opendp/opendp-audit/issues/158).
