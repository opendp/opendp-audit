---
schema_version: 1
source: python/src/opendp/extras/sklearn/_make_eigendecomposition/__init__.py
updated: 2026-11-26
---

# `python/src/opendp/extras/sklearn/_make_eigendecomposition/__init__.py`

## Scope and assumptions

- **Scope:** The public `num_components` parameter of `make_private_np_eigendecomposition`, its effect on the returned eigenvectors, the `then_private_eigenvectors` callee, and the higher-level PCA wrapper. This is **not** an audit of the Bingham sampler, eigenvalue sensitivity, or the full privacy proof.
- **Invariant:** An explicitly requested number of eigenvectors should determine or constrain the number of released eigenvector columns, or invalid combinations with epsilon allocations should be rejected.
- **Assumptions:** A valid fixed-size, three-feature, L2-bounded NumPy array domain and symmetric-distance metric; positive epsilon allocations; successful numerical execution of the underlying sampler.
- **Reviewed upstream:** [constructor](https://github.com/opendp/opendp/blob/4549351bcd3a877412d8b6fdf41500372d241705/python/src/opendp/extras/sklearn/_make_eigendecomposition/__init__.py), [eigenvector callee](https://github.com/opendp/opendp/blob/4549351bcd3a877412d8b6fdf41500372d241705/python/src/opendp/extras/sklearn/_make_eigenvector/__init__.py), [PCA caller](https://github.com/opendp/opendp/blob/4549351bcd3a877412d8b6fdf41500372d241705/python/src/opendp/extras/sklearn/decomposition/__init__.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_private_np_eigendecomposition` | correctness/component-count | Audited | `4549351bcd3a877412d8b6fdf41500372d241705` | [Unused parameter and counterexample](#unused-parameter-and-counterexample); [candidate defect #169](https://github.com/opendp/opendp-audit/issues/169). |

## Analysis

### Unused parameter and counterexample

The constructor validates `num_components >= 1` when supplied and defaults an absent value to `input_desc.num_columns`. It does not reference the resulting local value in the subsequent SSCP construction, eigenvalue measurement, eigenvector measurement, or final composition. The eigenvector call passes only `eigvecs_epsilons`.

The [`make_private_eigenvectors` callee](https://github.com/opendp/opendp/blob/4549351bcd3a877412d8b6fdf41500372d241705/python/src/opendp/extras/sklearn/_make_eigenvector/__init__.py) samples one direction for each supplied epsilon and, if the remaining subspace has dimension one, appends its final basis vector as postprocessing. Thus, for three features:

- `num_components=1`, `eigvecs_epsilons=[0.1, 0.1]`: two directions are sampled and the third is appended, so the vector matrix has three columns, not one.
- `num_components=3`, `eigvecs_epsilons=[0.1]`: one direction is sampled, leaving two dimensions, so the vector matrix has one column, not three.

Both combinations satisfy the constructor's explicit `num_components` check and the callee's maximum number of epsilon allocations. No caller/callee code path reconciles them. The intended number of released directions is therefore governed by the supplied epsilon list rather than the documented parameter.

**Impact:** Low-severity correctness and data minimization; the observed API mismatch alone is **not** evidence of a privacy-accounting underestimate, because the measurement composes the actual releases and their supplied epsilon allocations. In the high-level PCA wrapper, requested components independently influence the length of the epsilon list, partly masking this defect. The lower-level public constructor still accepts an inconsistent specification.

**Evidence actually reviewed:** Current pinned source and upstream draft [PR #2844](https://github.com/opendp/opendp/pull/2844) and [PR #3281](https://github.com/opendp/opendp/pull/3281) diffs. Neither removes or implements the lower-level argument. Searches of current and historical upstream/audit issues found no equivalent tracked defect. A native OpenDP run was **not performed** because the `opendp` package was unavailable in the local runtime.

## Finding and next checks

[Audit defect #169](https://github.com/opendp/opendp-audit/issues/169) records the confirmed source-level mismatch. Add a native output-shape regression using a three-feature domain and inconsistent component count/epsilon allocations. Resolve by either honoring `num_components` or deleting the redundant public argument and documenting epsilon-list-driven behavior. Separately audit budget validity and numerical implementation; those properties were outside this review.
