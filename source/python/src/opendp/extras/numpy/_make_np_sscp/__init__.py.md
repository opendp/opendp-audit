---
schema_version: 1
source: python/src/opendp/extras/numpy/_make_np_sscp/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/numpy/_make_np_sscp/__init__.py`

## Scope and assumptions

- **Audit scope:** `make_np_sscp`'s declared output-domain membership for rank-deficient floating-point Gram matrices. Separately trace the current `_sscp_domain` membership predicate and the pending symmetric-matrix refactor, without revisiting previously reported nonzero-origin and provenance-sensitivity bugs.
- **Invariant:** Every `X` admitted by the transformation input domain must produce `C=X.T@X` which is admitted by its declared output domain; otherwise the transformation's codomain certificate is incorrect under the concrete numerical implementation.
- **Assumptions:** Non-NaN float32/float64 `numpy.array2_domain(norm=1,p=2,size=1,num_columns=2)`; zero-centered row `[0.5,0.7]` with Euclidean norm less than 1; NumPy 2.3.5 LAPACK eigenvalue behavior. This module requires `contrib` and `idealized-numerics`, whose ideal arithmetic model is a separate caveat.
- **Pinned source:** [`make_np_sscp`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_sscp/__init__.py), [NumPy matrix domain](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/__init__.py), [cross-file investigation](../../../../../../../investigations/numpy-sscp-gram-psd-roundoff.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_np_sscp` | correctness/sscp-output-domain-closure | Audited | `a010591f55b1713c926f8e355091471634480307` | [Rank-one numerical output](#rank-one-numerical-output); [investigation](../../../../../../../investigations/numpy-sscp-gram-psd-roundoff.md); [model](../../../../../../../tools/tests/test_sscp_gram_psd_rounding_model.py). |
| `make_np_sscp` | privacy/numerical-metric-conservatism | Partial | `a010591f55b1713c926f8e355091471634480307` | [Privacy and upstream disposition](#privacy-and-upstream-disposition); neither the rounded Gram matrix's metric distance nor the end-to-end PCA release was verified. |

| `make_np_sscp` | correctness/sscp-float32-overflow | Audited | `a010591f55b1713c926f8e355091471634480307` | [Bounded float32 overflow](#bounded-float32-overflow-and-warning); [issue #156](https://github.com/opendp/opendp-audit/issues/156) — genuine valid inputs can yield nonfinite SSCP output. |
| `make_np_sscp` | privacy/pre-noise-warning | Partial | `a010591f55b1713c926f8e355091471634480307` | [Bounded float32 overflow](#bounded-float32-overflow-and-warning); standalone data-dependent NumPy warning/error reproduced, native OpenDP propagation not checked. |

## Analysis

### Rank-one numerical output

The transformation accepts a bounded float NumPy matrix and returns `lambda arg: arg.T @ arg`, declaring an `_sscp_domain` with the same public norm, feature count and size. For `X=np.array([[0.5,0.7]], dtype=np.float64)`, `size=1`, `p=2`, `norm=1`, the input norm is approximately `0.8602325267`, so this is an **admitted input**, not an invalid precondition.

NumPy 2.3.5 computes the symmetric, finite matrix `C=[[0.25,0.35],[0.35,0.48999999999999994]]`; `np.linalg.eigvals(C)` has a smallest eigenvalue `-5.551115123125783e-17`. The `_sscp_domain` predicate rejects `C` solely because `np.any(np.linalg.eigvals(C)<0)` is true. The float32 version of the same row similarly produces a small negative eigenvalue. Thus **the function can return a value that is not in its declared codomain**, contrary to the transformation's source-level carrier/domain contract.

**Executed:** Standalone NumPy matrix multiplication and eigenvalue check on both float dtypes, with binary-exact control and asymmetric/nonfinite negative controls in [regression](../../../../../../../tools/tests/test_sscp_gram_psd_rounding_model.py). **Not executed:** OpenDP's native `Domain.member` or `make_np_sscp` through FFI; under a different NumPy/LAPACK backend the precise pair may not trigger the negative eigenvalue.

### Privacy and upstream disposition

This is a numerical **false-negative domain membership** counterexample, complementary to the existing [audit #115](https://github.com/opendp/opendp-audit/issues/115) reporting SSCP **false-positive** membership against public norm/size metadata. The present observation does not prove a privacy-accounting underestimation: the ordinary pipeline may never check output membership dynamically and the idealized-numerics feature intentionally abstracts away rounding. Any downstream metric calibration relying on the invalid domain certificate requires independent analysis.

**Pending upstream resolution:** [Open draft PR #3281](https://github.com/opendp/opendp/pull/3281) replaces `_sscp_domain` with a finite symmetric matrix domain that deliberately removes its PSD eigenvalue check. The new domain admits this rounded `C`, and the PR changes SSCP privacy accounting to use a nuclear-norm metric. Its code is unmerged on pinned `main`. Since the root cause is addressed by an existing corrective PR, no duplicate candidate issue was opened for this finding.

### Bounded float32 overflow and warning

The same transformation also has a **separate** `float32` range defect unrelated to the rank-one PSD roundoff described above. With `array2_domain(norm=1e21, p=2, size=1, num_columns=2, nan=False, T=f32)`, the scaled `_rows_within_norm` input predicate accepts each of `x0=[[1e10,0]]` and `x1=[[1e20,0]]` as a one-row, two-column `float32` array. These datasets differ in one row (symmetric distance at most 2).

The source uses ordinary `lambda arg: arg.T @ arg` with no dtype widening or overflow handling. Standalone NumPy 2.3.5 execution gives a **finite** Gram matrix for `x0`, and `[[inf,0],[0,0]]` for `x1`. The latter violates `_sscp_domain`'s `np.isfinite` membership requirement. NumPy emits `RuntimeWarning: overflow encountered in matmul` only for `x1`; when configured with `np.errstate(over="raise")`, it raises `FloatingPointError` only for `x1`.

**Privacy relevance:** `make_private_np_eigendecomposition` composes this SSCP transformation **before** noise. If its warning or exception escapes the native callback, a caller observing Python warnings/errors obtains a deterministic private-data distinguisher. This is **Partial** until captured in a compiled OpenDP measurement, not a proven native DP failure. The output-domain contradiction is confirmed by source-equivalent NumPy arithmetic.

**Pending PR:** [#3281](https://github.com/opendp/opendp/pull/3281) replaces the matrix domain/metric but leaves `arg.T @ arg` in the input `float32` dtype. Its `row_norm_sq` finite check uses a Python float; `(1e21)**2 = 1e42` remains finite there, but squaring `1e20` overflows `float32`. Thus that PR does **not** fix this counterexample. The older [audit #115](https://github.com/opendp/opendp-audit/issues/115) and the rank-one counterexample above are distinct from this overflow issue.

**Evidence:** [Issue #156](https://github.com/opendp/opendp-audit/issues/156), [cross-file investigation](https://github.com/opendp/opendp-audit/blob/main/investigations/numpy-sscp-float32-overflow-warning.md), [standalone four-test regression](https://github.com/opendp/opendp-audit/blob/main/tools/tests/test_numpy_sscp_float32_overflow_model.py). The native FFI/callback and full PCA release were not executed.

## Next checks

Run pinned native OpenDP membership/invocation on `X=[[0.5,0.7]]` for float32 and float64. After PR #3281 merges, exercise the same rows on the new symmetric-matrix output domain and separately audit the new nuclear-norm stability map under finite-precision arithmetic.
