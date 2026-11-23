---
schema_version: 1
source: python/src/opendp/extras/numpy/_norm.py
updated: 2026-11-23
---

# `python/src/opendp/extras/numpy/_norm.py`

## Scope and assumptions

- **Scope:** The non-deprecated `_rows_within_norm` helper used for NumPy `array2_domain` membership and `make_np_clamp` output validation. Focus on the arithmetic interface between a centered array and the rowwise scaled-norm predicate; `p=1,2`, one-column integer witnesses.
- **Invariant:** A row satisfying the claimed real-valued Lp bound must be admitted and a row violating the bound must not be admitted. The helper evaluates only the already-centered `x`; preserving the true difference `data - origin` is its **caller's** responsibility.
- **Assumptions:** NumPy 2.3.5 arithmetic. Scalar Lp radius `R=1` or `0`. No claim that the helper itself can distinguish different exact integers after they have been rounded to identical doubles.
- **Pinned source:** [`_norm.py`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_norm.py), [caller `array2_domain`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/__init__.py), and [model test](../../../../../../tools/tests/test_numpy_integer_origin_membership_model.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `opendp.extras.numpy._norm._rows_within_norm` | correctness/scaled-norm-membership | Audited | `a010591f55b1713c926f8e355091471634480307` | [Source-level scaled predicate and signed-int64 witness](#analysis); [cross-file investigation](../../../../../../investigations/numpy-integer-origin-membership-sensitivity.md) |
| `opendp.extras.numpy._norm._rows_within_norm` | privacy/caller-centered-array-precondition | Partial | `a010591f55b1713c926f8e355091471634480307` | [Caller loses integer offsets before invoking this helper](#analysis); cannot prove real input-domain membership using only the rounded centered array. |

## Analysis

The helper computes `scale = max(abs(x))` rowwise (at least zero), replaces zero scale by one, then compares `np.linalg.norm(x/scale,ord=p)` to `norm/scale` while requiring `np.isfinite(x)`. This avoids the simple unscaled squared-norm underflow and is correct for the **floating-point centered array it actually receives** in the deterministic one-dimensional witness.

However, `array2_domain._member` calls `_rows_within_norm(x - origin, norm, p)` where `x` can be `int64` and `origin` has been cast to `float64`. At exact integer center `2**60`, both integer inputs `2**60-64` and `2**60+128` are converted to `float64(2**60)` before subtraction. The helper therefore receives `[[0.0]]` in both cases and faithfully reports both as inside radius `1`, despite their actual distances 64 and 128. The lossy operation originates at the **caller**, not this helper. [Full cross-file witness](../../../../../../investigations/numpy-integer-origin-membership-sensitivity.md).

**Executed:** Source-equivalent NumPy 2.3.5 predicate on both records, tested `p=1`, `p=2`, `norm=0`, and a control row outside the rounding interval; all tests confirm the accepted/rejected behavior. Native OpenDP `Domain.member` and `make_np_sum` were **not executed**. No independent numerical error in `_rows_within_norm` for the already-rounded centered data is claimed.

## Next checks

Correct or reject lossy int/float centering before calling the helper; add native domain membership regressions for `int64` origins at large powers of two and near integer-carrier extrema. Extend review to other caller arithmetic and multi-column rounding only after the direct domain false-positive is fixed.
