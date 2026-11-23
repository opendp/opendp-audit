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

## Analysis

### Rank-one numerical output

The transformation accepts a bounded float NumPy matrix and returns `lambda arg: arg.T @ arg`, declaring an `_sscp_domain` with the same public norm, feature count and size. For `X=np.array([[0.5,0.7]], dtype=np.float64)`, `size=1`, `p=2`, `norm=1`, the input norm is approximately `0.8602325267`, so this is an **admitted input**, not an invalid precondition.

NumPy 2.3.5 computes the symmetric, finite matrix `C=[[0.25,0.35],[0.35,0.48999999999999994]]`; `np.linalg.eigvals(C)` has a smallest eigenvalue `-5.551115123125783e-17`. The `_sscp_domain` predicate rejects `C` solely because `np.any(np.linalg.eigvals(C)<0)` is true. The float32 version of the same row similarly produces a small negative eigenvalue. Thus **the function can return a value that is not in its declared codomain**, contrary to the transformation's source-level carrier/domain contract.

**Executed:** Standalone NumPy matrix multiplication and eigenvalue check on both float dtypes, with binary-exact control and asymmetric/nonfinite negative controls in [regression](../../../../../../../tools/tests/test_sscp_gram_psd_rounding_model.py). **Not executed:** OpenDP's native `Domain.member` or `make_np_sscp` through FFI; under a different NumPy/LAPACK backend the precise pair may not trigger the negative eigenvalue.

### Privacy and upstream disposition

This is a numerical **false-negative domain membership** counterexample, complementary to the existing [audit #115](https://github.com/opendp/opendp-audit/issues/115) reporting SSCP **false-positive** membership against public norm/size metadata. The present observation does not prove a privacy-accounting underestimation: the ordinary pipeline may never check output membership dynamically and the idealized-numerics feature intentionally abstracts away rounding. Any downstream metric calibration relying on the invalid domain certificate requires independent analysis.

**Pending upstream resolution:** [Open draft PR #3281](https://github.com/opendp/opendp/pull/3281) replaces `_sscp_domain` with a finite symmetric matrix domain that deliberately removes its PSD eigenvalue check. The new domain admits this rounded `C`, and the PR changes SSCP privacy accounting to use a nuclear-norm metric. Its code is unmerged on pinned `main`. Since the root cause is addressed by an existing corrective PR, no duplicate candidate issue was opened for this finding.

## Next checks

Run pinned native OpenDP membership/invocation on `X=[[0.5,0.7]]` for float32 and float64. After PR #3281 merges, exercise the same rows on the new symmetric-matrix output domain and separately audit the new nuclear-norm stability map under finite-precision arithmetic.
