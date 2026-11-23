---
schema_version: 1
upstream_commit: a010591f55b1713c926f8e355091471634480307
updated: 2026-11-23
status: Partial
---

# Rank-deficient NumPy SSCP outputs fail their declared PSD domain

## Scope and invariant

The current `make_np_sscp` transformation accepts a non-NaN bounded NumPy matrix `X`, computes `C = X.T @ X` and advertises an `_sscp_domain` output. In ideal real arithmetic `C` is symmetric positive semidefinite, but floating-point matrix multiplication and eigenvalue algorithms are not exact. **Every actual successful transform output must belong to the declared output domain** if the domain metadata is subsequently trusted.

This review covers only that **output-domain closure** invariant, not calibration of eigenvalue/eigenvector measurements, covariance matrix stability, or the unrelated input-domain *false positives* tracked in [audit #115](https://github.com/opendp/opendp-audit/issues/115). OpenDP guards this NumPy path with `idealized-numerics`; the finding is a concrete numerical discrepancy from its idealized reasoning rather than a proved DP attack.

## Source trace

- [`array2_domain`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/__init__.py) admits float64 and float32 arrays of correct `size=1`, `num_columns=2`, `norm=1`, `p=2`, `nan=False` when the scaled row-L2 predicate passes.
- [`make_np_sscp`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_sscp/__init__.py) exposes `lambda arg: arg.T @ arg` and constructs `_sscp_domain(num_features=2,norm=1,p=2,size=1,T=...)`.
- [`_sscp_domain._member`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/__init__.py) checks type/dtype, square shape/dimension, finiteness and exact equality `x == x.T`; it then rejects whenever `np.any(np.linalg.eigvals(x) < 0)` is true. There is **no tolerance** for the small negative eigenvalue introduced by numerical rounding.

## Executed witness

Using NumPy 2.3.5 in the available Python environment, take the legitimate one-row input:

```python
import numpy as np

X = np.array([[0.5, 0.7]], dtype=np.float64)
assert np.linalg.norm(X[0], 2) < 1.0

C = X.T @ X
assert np.array_equal(C, C.T)
assert np.isfinite(C).all()

lam = np.linalg.eigvals(C)
print(C, lam)
# [[0.25, 0.35], [0.35, 0.48999999999999994]]
# [-5.551115123125783e-17, 0.74]
assert (lam < 0).any()  # Current _sscp_domain rejects this C.
```

The same `X` with `dtype=np.float32` yields a negative smallest eigenvalue near `-1.2082023e-9` under the observed NumPy/LAPACK implementation. For both types, `X` is strictly inside the public radius 1. Every other output membership check passes, and only the exact PSD test rejects it. A control `X=[[0.5,0.5]]` produces an exactly rank-one binary-representable Gram matrix that both type domains accept.

This is not a crafted invalid `_sscp_domain` input: `C` is **exactly the output of the transformation** when given a valid `array2_domain` carrier. The numerical violation can occur for ordinary small positive inputs, not just overflow, huge values or NaNs.

[Independent regression model](../tools/tests/test_sscp_gram_psd_rounding_model.py) checks input radius and output shape, both float dtypes, strict eigenvalue admission, a positive control and rejection of asymmetric/nonfinite matrices. It skips the particular negative-eigenvalue assertions if a different backend computes no negative eigenvalue.

**Executed:** Standalone NumPy 2.3.5 `X.T @ X` / `np.linalg.eigvals` and modeled domain membership. **Not executed:** Native OpenDP `make_np_sscp` / `Domain.member`, full PCA or downstream DP release. The actual FFI transform may not test its output domain dynamically; this review establishes an invalid *declared codomain* for the concrete floating-point function, not an observed exception or privacy loss in every invocation.

## Existing pending upstream fix

Open [draft PR #3281](https://github.com/opendp/opendp/pull/3281) replaces the old `_sscp_domain` with `_symmetric_matrix_domain`, retaining finite/symmetric shape checks but **removing exact PSD and latent norm/size membership constraints**. The same PR changes `make_np_sscp` to use a nuclear-norm output metric, and its [`test_ext_domains_numpy.py` patch](https://github.com/opendp/opendp/pull/3281/files) explicitly verifies that negative-eigenvalue symmetric matrices are admissible. This addresses the root of the codomain false-negative identified here for the specific symmetric matrix output.

**Status:** Pending PR; not on upstream `main` `a010591f55b1713c926f8e355091471634480307`. It is not necessary to open a duplicate candidate defect issue; the same old-domain design is tracked in audit [#115](https://github.com/opendp/opendp-audit/issues/115), albeit for the opposite inclusion direction. The PR's full sensitivity proof and numerical behavior remain to be checked after merge.

## Residual risk and next checks

1. Native integration at the pinned upstream SHA: construct `array2_domain(norm=1,p=2,size=1,num_columns=2,nan=False,T=float)`, compose `make_np_sscp`, invoke with `[[0.5,0.7]]`, and call its `output_domain.member` on the resulting Gram matrix. Confirm the precise FFI warning/false return. Repeat with `f32`.
2. Verify draft PR #3281's new symmetric domain admits these matrices and that its output metric and stability maps are numerically conservative for rounded `X.T @ X`.
3. If retaining strict PSD requirements elsewhere, use a sound conservative tolerance/projection and account for its effect on domain, output metric, downstream sensitivity and data-dependent errors.
4. Check any consumer that implicitly relies on the old `_sscp_domain.member` to accept **every** successful `make_np_sscp` result. No downstream leak is established here.

**Disposition:** Source-model counterexample reproduced, pending resolution in PR #3281; correctness/contract, not a demonstrated privacy vulnerability. [Audit task #154](https://github.com/opendp/opendp-audit/issues/154).
