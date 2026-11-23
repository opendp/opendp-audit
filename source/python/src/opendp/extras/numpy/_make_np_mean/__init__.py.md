---
schema_version: 1
source: python/src/opendp/extras/numpy/_make_np_mean/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/numpy/_make_np_mean/__init__.py`

## Scope and assumptions

- **Audit scope:** `make_private_np_mean` on public `size=0` and `size>0` domains, optional norm clamping, finite zero-row summation and postprocessing. This is an availability/totality and narrow privacy-budget-source review, not a proof of all numerical mean releases.
- **Invariants:** The mean of zero rows is undefined; either the constructor rejects zero-sized domains before creating an executable measurement, or it documents an appropriate defined output. Data-independent errors at publicly empty inputs do not establish DP leakage. For positive `size`, the noise scale for the sum is `size * scale` and a final division by `size` is postprocessing.
- **Assumptions:** `numpy.array2_domain` with `size=0`, `num_columns=2`, float32 or float64, `norm=1`, `p=1` or `p=2`, and `nan=False`. Public `scale` is positive. NumPy 2.3.5 is used for the source-equivalent model; native OpenDP bindings were not executed.
- **Pinned source:** [mean constructor](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_mean/__init__.py), [NumPy domain](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/__init__.py), [sum](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_sum/__init__.py), [clamp](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_clamp/__init__.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_private_np_mean` | correctness/empty-sized-mean-totality | Audited | `a010591f55b1713c926f8e355091471634480307` | [Zero-size constructor and division](#zero-size-constructor-and-division), [candidate defect #160](https://github.com/opendp/opendp-audit/issues/160), [executed model](../../../../../../../tools/tests/test_numpy_private_mean_zero_size_model.py). |
| `make_private_np_mean` | privacy/sized-mean-noise-calibration | Partial | `a010591f55b1713c926f8e355091471634480307` | [Privacy and accounting boundary](#privacy-and-accounting-boundary), [cross-file investigation](../../../../../../../investigations/numpy-private-mean-empty-sized-domain.md). |

## Analysis

### Zero-size constructor and division

`array2_domain(size=0,num_columns=2,norm=1,p=2,nan=False,T=float)` is valid: the NumPy domain's size validator requires a **nonnegative** integer and membership accepts an array with zero rows. The mean constructor rejects only `size is None` and therefore permits `size=0`. It selects Gaussian/zCDP for `p=2` (or Laplace/pure DP for `p=1`), composes `make_private_np_sum` at noise scale `scale*0=0`, and appends an unconditional postprocessor `lambda sums: np.array(sums)/size`.

The empty two-column NumPy input has axis-zero sum `[0.,0.]`, while the final division is `0/0`. On NumPy 2.3.5, this yields `[nan,nan]` with a `RuntimeWarning: invalid value encountered in divide`. The optional `norm` clamp handles empty matrices with shape-preserving empty-axis arithmetic, so it does not prevent the failure. Both f32/f64 and p1/p2 yield this output in the source-equivalent model.

**Evidence:** [Cross-file investigation](../../../../../../../investigations/numpy-private-mean-empty-sized-domain.md) and [five standalone unittest methods](../../../../../../../tools/tests/test_numpy_private_mean_zero_size_model.py). **Executed:** NumPy 2.3.5 source-equivalent sums, empty clamp operations, postprocessing and warning capture. **Not executed:** native OpenDP FFI or the actual Laplace/Gaussian sampler; zero-scale noise being a deterministic zero shift is derived from its source contract, not observed here.

**Finding:** New [correctness issue #160](https://github.com/opendp/opendp-audit/issues/160), unreported in targeted upstream/audit issue and PR searches. The constructor should reject `size==0` before constructing any measurement; the domain itself can remain permissive because an empty dataset is meaningful for other aggregations.

### Privacy and accounting boundary

For a public, fixed zero-size input domain, every admitted dataset is empty. The bad output and warning therefore do not distinguish private datasets; **no privacy leak** or privacy-accounting underestimate is demonstrated. The `size*scale` sum-noise multiplier and final `/size` postprocessing are coherent for positive public `size` under ideal arithmetic, provided `make_np_sum` and its noise mechanism obey their independently reviewed bounds. A full proof of numeric bounds, conversion and the sampler is outside this audit.

Historical [upstream issue #3153](https://github.com/opendp/opendp/issues/3153) concerned the distinct **unspecified public column count** and has been resolved by the `num_columns` requirement in `make_np_sum`. The previously recorded [#131](https://github.com/opendp/opendp-audit/issues/131), [#141](https://github.com/opendp/opendp-audit/issues/141) and [#143](https://github.com/opendp/opendp-audit/issues/143) concern other sum numerical and bound failures, not this empty mean precondition.

## Next checks

Run a native OpenDP regression with an empty, fixed-width `array2_domain(size=0)`, both `norm=None` with an already bounded domain and `norm=1` with clamping, and both `p` choices. After patching, construction should raise `ValueError` for size zero; size-one and larger means should remain functional. Revisit privacy calibration only if behavior or noise mechanism changes. [Audit task #158](https://github.com/opendp/opendp-audit/issues/158).
