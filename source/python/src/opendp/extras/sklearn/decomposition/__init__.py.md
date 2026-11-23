---
schema_version: 1
source: python/src/opendp/extras/sklearn/decomposition/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/sklearn/decomposition/__init__.py`

## Scope and assumptions

- **Audit scope:** Scalar-`unit_epsilon` splitting in `make_private_pca`, its `PCA._prepare_fitter` caller, and the helper `_split_pca_epsilon_evenly` at the lower accepted feature-count boundary. Traced the intended zero eigenvector-release path to `make_private_eigenvectors`; did not validate end-to-end PCA calibration or sampling.
- **Invariant:** For publicly valid constructor arguments satisfying the documented feature-count check, budget allocation must not raise an unintended arithmetic exception. The zero-eigenvector case should be handled or intentionally rejected with a clear precondition.
- **Assumptions:** `input_domain` is a sized `NPArray2Domain` with `num_columns=1`, L2-compatible geometry, positive scalar epsilon (e.g., `1.0`), and either a public origin or an origin estimated by the algorithm. No private data is required to trigger the reported behavior.
- **Pinned source:** [OpenDP `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` decomposition implementation](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/sklearn/decomposition/__init__.py), [eigendecomposition construction](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/sklearn/_make_eigendecomposition/__init__.py), [eigenvector construction](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/sklearn/_make_eigenvector/__init__.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `sklearn.decomposition._split_pca_epsilon_evenly` | correctness/zero-eigenvector-budget | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Unconditional zero divisor](#analysis); [issue #122](https://github.com/opendp/opendp-audit/issues/122) |
| `sklearn.decomposition.make_private_pca` | correctness/one-feature-construction | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Valid `num_columns=1` reaches zero release count](#analysis); [issue #122](https://github.com/opendp/opendp-audit/issues/122) |
| `sklearn.decomposition.PCA._prepare_fitter` | correctness/one-feature-wrapper | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Scalar epsilon forwarded unchanged in kind](#analysis); constructor indirectly affected; sklearn import not executed |
| `sklearn.decomposition.make_private_pca` | privacy/budget-calibration | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | No undercharging shown; general `PCAEpsilons` and multicomponent accounting not checked in this pass |

## Analysis

`make_private_pca` accepts `input_desc.num_columns >= 1`. For scalar `unit_epsilon`, it chooses `num_components = num_columns` when absent and calculates `num_eigvec_releases = min(num_components, input_desc.num_columns - 1)`. When `num_columns=1`, this is `min(1,0)=0`. The call to `_split_pca_epsilon_evenly(unit_epsilon, 0, estimate_mean=...)` unconditionally executes `per_evec_epsilon = per_query_epsilon / num_eigvec_releases`, raising `ZeroDivisionError` for any finite positive scalar epsilon. The failure is before measurement construction and independent of private data. It occurs for `estimate_mean=True` and `False`.

The sklearn `PCA._prepare_fitter` path passes `self.epsilon / self.n_changes` (a scalar float for conventional parameters) to `make_private_pca`, so the same edge case is present for `n_features=1`.

The downstream `make_private_eigenvectors` implementation initializes `P=I` and `theta` empty, has a loop over the supplied epsilon sequence, and explicitly handles a final one-dimensional projection without a private eigenvector release. Thus the zero-release case is not inherently nonsensical, but whether the empty adaptive compositor accepts zero queries and all other one-dimensional PCA behavior work in a native run remains **unverified**.

**Executed check:** An independent standalone Python reconstruction of the exact epsilon-splitting arithmetic, `PCAEpsilons` dataclass, and `_smaller` function was run with NumPy. It raised `ZeroDivisionError: float division by zero` for one feature and returned valid-looking splits for two and three features. This was *not* an import or execution of the installed OpenDP package, and it did not execute its Rust/Python measurement machinery.

**Finding:** [Audit issue #122](https://github.com/opendp/opendp-audit/issues/122), **low-severity correctness/usability**. No privacy breach, data-dependent exception, or budget undercharge is claimed. Search of open and closed audit/upstream issues and PRs found no equivalent. [Upstream PR #3281](https://github.com/opendp/opendp/pull/3281) touches eigenvector internals but not this splitting function.

## Next checks

- Add native regression for `make_private_pca` with `num_columns=1`, scalar epsilon, both known and unknown origin, including whether zero-length adaptive composition is accepted.
- Handle `num_eigvec_releases=0` before dividing (and, if one-dimensional PCA is intended, distribute budget only over actual private queries); alternatively, document and validate a minimum of two features.
- Independently audit `PCAEpsilons` value validation and the multicomponent privacy budget. Those properties were not verified in this pass.
