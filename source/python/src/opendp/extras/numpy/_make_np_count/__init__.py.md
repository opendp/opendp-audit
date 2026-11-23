---
schema_version: 1
source: python/src/opendp/extras/numpy/_make_np_count/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/numpy/_make_np_count/__init__.py`

## Scope and assumptions

- **Audit scope:** Non-deprecated `make_np_count`, the generated `then_np_count`, `make_private_np_count`, and `then_private_np_count` wrappers, for known/unknown row count and known/unknown column count. This covers row-count correctness and source-level `SymmetricDistance` stability, **not** the distributional proof of the downstream scalar noise mechanism.
- **Invariants:** (1) With unknown row count, `count(X)` is the number of rows, independent of row values, row order, and number of columns, with `|count(X)-count(Y)| <= d_sym(X,Y)`. (2) With fixed public row count `n`, the output is always `n` and sensitivity is zero. (3) An admitted empty input of public size zero yields the defined count zero, unlike the related private-mean case. (4) Unspecified public width cannot be inferred from the deterministic count itself.
- **Assumptions:** Each input is an admitted two-dimensional NumPy array with its declared public dimensions; `SymmetricDistance` counts row insertions/deletions, and rows within a comparison have an interpretable common schema. The source requires `contrib` and, for the generated private wrapper, a supported Laplace or Gaussian privacy measure. No native OpenDP or FFI runtime was available.
- **Pinned source:** [count constructor](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_count/__init__.py), [NumPy domain](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/__init__.py), [private wrapper](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/_utilities.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_np_count` | privacy/count-symmetric-stability | Audited | `a010591f55b1713c926f8e355091471634480307` | [Row-count map and exhaustive multiset model](#row-count-map-and-exhaustive-multiset-model); [test](../../../../../../../tools/tests/test_numpy_count_stability_model.py). |
| `make_np_count` | privacy/count-width-independence | Audited | `a010591f55b1713c926f8e355091471634480307` | [Width and row-order independence](#width-and-row-order-independence); no width disclosure analogous to previous sum/mean issue. |
| `make_np_count` | correctness/sized-count-and-empty-domain | Audited | `a010591f55b1713c926f8e355091471634480307` | [Public size and empty rows](#public-size-and-empty-rows). |
| `make_private_np_count` | privacy/noise-wrapper-composition | Partial | `a010591f55b1713c926f8e355091471634480307` | [Private wrapper boundary](#private-wrapper-boundary); native Laplace/Gaussian FFI and sampler unverified. |

## Analysis

### Row-count map and exhaustive multiset model

For `size=None`, the transformation's function is `lambda x: x.shape[0]` and its map is `lambda d_in: d_in`. Let `c_X(r)` and `c_Y(r)` be row multiplicities. Then `|count(X)-count(Y)| = |sum_r(c_X(r)-c_Y(r))| <= sum_r |c_X(r)-c_Y(r)| = d_sym(X,Y)`. This is a direct combinatorial proof independent of the row values, even when rows repeat.

An independent [stdlib multiset-model regression](../../../../../../../tools/tests/test_numpy_count_stability_model.py) exhaustively enumerates all multisets of up to four rows over Boolean records with widths 0, 1, 2, and 3, and checks **250,175 ordered dataset pairs** for the identity stability inequality. This is an independently executed model, **not** the native OpenDP transformation.

### Width and row-order independence

The implementation does **not** require `num_columns`, but unlike `make_np_sum`, it releases only the row count. A dataset with two, five, or zero columns and the same number of rows has the same deterministic count. No output shape, dtype, or deterministic value reveals its number of columns. The count is unchanged by permutations of rows or substitutions of row values; only adding/removing rows changes it.

**Distinction:** Historical [upstream issue #3153](https://github.com/opendp/opendp/issues/3153) concerned `make_private_np_sum` and `make_private_np_mean`, which previously returned vectors whose **length** revealed an unconstrained input width. That root cause does not apply to the scalar count. This analysis does not assert that arbitrary varying-schema LazyFrames or ndarrays are necessarily at a finite distance; it establishes that no width disclosure occurs from the count output even if a variable-width domain is provided.

### Public size and empty rows

If the domain declares `size=n`, the function returns the public constant `n`, ignoring private row contents, and the map returns **0** for any queried distance. This is sound for any admitted carrier, since `array2_domain` checks `len(X)==n`. In particular, the domain allows public `size=0` and admitted `X` with shape `(0,k)`; `make_np_count` returns the well-defined count `0` and map zero. This contrasts with the unrelated [private mean issue #160](https://github.com/opendp/opendp-audit/issues/160), which performs an undefined division by zero for the same publicly empty domain.

**Executed:** Source-equivalent standard-library row and metric model and, where NumPy is available, `np.zeros((n,k),dtype)` row-axis checks with n=0..4 and k=0..4 for f32/f64/i64. **Not executed:** native OpenDP `Domain.member`, `make_np_count`, FFI, or noise mechanism.

### Private wrapper boundary

`make_private_np_count` is generated by `with_privacy(make_np_count)`, which chains the count transformation to a scalar Laplace or Gaussian noise mechanism. No intermediate array, row value, column key, or width is directly passed to the noise mechanism; it receives an integer count. The source-level map is zero for fixed public size and identity for unsized input. The actual privacy loss depends on the independently audited scalar noise mechanism and its distance conversion, which were **not re-executed** here.

## Disposition and next checks

**No new privacy or correctness defect identified** for the scoped count invariants on upstream `main` `a010591f55b1713c926f8e355091471634480307`. Targeted searches of audit and upstream issues found no specific `make_np_count` report; the scalar-count path does not reproduce the former sum/mean width bug or the empty-mean failure. No candidate defect issue was filed.

The remaining work is a native OpenDP regression confirming that zero-sized and unspecified-width domains construct successfully, that the returned count and `map` match the stated values, and that the FFI-generated private wrapper handles both supported privacy measures. This report certifies only the named narrow source-level properties, not a complete proof of the noise distribution.

[Bounded audit task #164](https://github.com/opendp/opendp-audit/issues/164).
