---
schema_version: 1
upstream_commit: a010591f55b1713c926f8e355091471634480307
updated: 2026-11-23
status: Partial
---

# NumPy integer row membership rounds away public-origin offsets

## Invariant and threat model

`array2_domain(norm=R, p=1 or 2, origin=O, T=i64, size=1)` claims its members have per-row real-valued Lp distance at most `R` from `O`. `make_np_sum` trusts that constraint: for a fixed dataset size, a replacement (symmetric distance `d_in=2`) is certified to change the sum by at most `2R`. A false-positive domain membership check can allow inputs whose true sum separation exceeds the certified stability by orders of magnitude. This is a direct **membership-contract** counterexample in ordinary representable integers; the conditional privacy implication relies on reaching a valid downstream noise calibration.

All relevant Python APIs are non-deprecated but bounded NumPy sum features are `contrib`/`idealized-numerics` gated. The underlying mathematical proof assumes true membership in an ideal real-valued Lp ball; this investigation checks the actual NumPy membership predicate instead.

## Affected symbols and pinned sources

- [`array2_domain` / `NPArray2Domain`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/__init__.py): converts an ndarray `origin` with integer dtype to float; its `_member` computes `centered = x - origin` with NumPy's promoted arithmetic. [Source audit](../source/python/src/opendp/extras/numpy/__init__.py.md).
- [`_rows_within_norm`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_norm.py): evaluates a numerically scaled Lp membership predicate on the **already rounded** centered array; it cannot recover integer offsets lost during the subtraction. [Source audit](../source/python/src/opendp/extras/numpy/_norm.py.md).
- [`make_np_sum`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_sum/__init__.py): computes `arg.sum(axis=0)` on original `i64` inputs while its sized stability map uses `d_in // 2 * 2 * norm`. [Source audit](../source/python/src/opendp/extras/numpy/_make_np_sum/__init__.py.md); [proof](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_sum/make_np_sum.tex).
- [`ExtrinsicDomain.descriptor`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/mod.py) returns a deep copy. The issue is **not caller mutation of the descriptor**; `array2_domain`'s constructed `_member` has the mixed-dtype operation intrinsically.
- [Regression model](../tools/tests/test_numpy_integer_origin_membership_model.py) checks the exact source NumPy expression and scaled predicate.

## Reproduced witness

Let the public center be exactly representable `O=2**60` and the public radius be `R=1.0`. Use `size=1`, `num_columns=1`, `T=i64`, `nan=False`, `p=1`. Create the origin from `np.array([O], dtype=np.int64)`; the constructor converts it to float64. Consider two inputs:

```python
import numpy as np

O = 1 << 60
origin = np.array([O], dtype=np.int64).astype(float)
x0 = np.array([[O - 64]], dtype=np.int64)
x1 = np.array([[O + 128]], dtype=np.int64)
assert (x0 - origin)[0, 0] == 0.0
assert (x1 - origin)[0, 0] == 0.0
assert (x1.sum(axis=0) - x0.sum(axis=0))[0] == 192
```

`int64 - float64` promotes integer coordinates to double precision **before** subtracting. Near `2**60`, both distinct integer endpoints round to the exact float representation `O`. The real centered absolute differences are respectively **64 and 128**, both exceeding the advertised radius 1. Nonetheless, `_rows_within_norm(x-origin, R, 1)` evaluates an all-zero centered array and returns true for **both**. The same holds with `p=2`; the intended Lp norm in one dimension equals the absolute difference.

The arrays are each shaped `(1,1)`, have supported `int64` dtype, and differ by a one-row substitution (`SymmetricDistance=2`). NumPy `sum(axis=0)` returns their exact original `int64` coordinates, **without wraparound**: output distance **192**. But the sized `make_np_sum` map formula reports `(2//2) * 2 * 1.0 = 2.0`. Thus the source-level stability upper bound is too small by **96×**. When `norm=0.0`, which the domain allows, these same out-of-ball rows are still admitted by the rounded predicate while the reported map is zero.

This is **not** an instance of the [unsized L2 origin norm underflow](https://github.com/opendp/opendp-audit/issues/131) (all values here are large and the size is fixed), [int64 sum wraparound](https://github.com/opendp/opendp-audit/issues/143) (the sum does not overflow), or [float32 accumulator overflow](https://github.com/opendp/opendp-audit/issues/141).

## Verification and privacy implications

**Executed:** Standalone NumPy 2.3.5 reproduction using exactly the `array2_domain` origin cast and `_member` subtraction, plus the identical `_rows_within_norm` scaled predicate; confirmed both false-positive memberships, exact distinct sums, and the 96-fold gap in the map formula. Also checked `p=2`, zero radius, and a sufficiently distant row that the predicate rejects. The standalone `unittest` source model is committed in [`tools/tests`](../tools/tests/test_numpy_integer_origin_membership_model.py).

**Not executed:** Native `array2_domain.member` via OpenDP FFI, `make_np_sum.map(2)`, `make_private_np_sum`, or the Laplace/Gaussian noise sampling. Not an observed privacy-ratio experiment.

**Critical qualification:** The separate [audit #143](https://github.com/opendp/opendp-audit/issues/143) notes `make_np_sum` may return a Python **float** stability distance to an **integer** output metric, causing a callback conversion failure instead of reaching private release. The defect here is nevertheless independently established in the **domain acceptance criterion**; a downstream pipeline that trusts this bound without such an accidental type error would undercalibrate. We do not assert a successful private mechanism releases undercalibrated noise on the current implementation without a native test.

## Deduplication and disposition

Searched both upstream/audit issues (open and closed) and upstream PRs for `array2_domain`, `origin`, `int64`, `rounding`, `membership`. No equivalent report or implemented fix was found at the pinned SHA. [Candidate defect #145](https://github.com/opendp/opendp-audit/issues/145), marked `privacy`, tracks the independent membership bug. [Audit task #144](https://github.com/opendp/opendp-audit/issues/144) coordinates this bounded review.

## Next decisive checks

1. Install/build current OpenDP and execute `array2_domain(... T=i64).member(x0)` and `.member(x1)` with the witness; confirm both currently return true.
2. Evaluate `make_np_sum.map(2)` and its private chain; report and resolve any `i64`/Python-float callback conversion failure separately from the membership issue.
3. Replace lossy integer-to-float centering in `array2_domain` with an exact or provably conservative comparison, or reject unsupported integer-origin/norm combinations. Test near powers of two and the `int64`/ `uint64` upper boundaries.
