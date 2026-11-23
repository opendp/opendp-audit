---
schema_version: 1
source: python/src/opendp/extras/sklearn/_make_eigenvector/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/sklearn/_make_eigenvector/__init__.py`

## Scope and assumptions

- **Additional independent audit scope:** Contractivity and mutable snapshot of `make_np_sscp_projection`, distinct from the existing negative-epsilon review; traced to SSCP and eigenvalue stability.

- **Audit scope:** `make_private_eigenvector` public `unit_epsilon` validation, privacy callback, and the ability of the Bingham sampler to depend on private input with negative epsilon; `make_private_eigenvectors` examined only to trace entrypoint exposure.
- **Invariants:** Valid `MaxDivergence` privacy maps must be nonnegative and conservative. Parameter values that undermine this guarantee must be rejected before a Measurement is returned.
- **Assumptions:** Bounded nonzero-norm SSCP data, two features, finite negative epsilon. Input metric is `SymmetricDistance`. This review does not re-prove the Bingham sampler for positive epsilon or the semantics of SSCP projection stability.
- **Reviewed source:** upstream [`7acfb2cdcee7d39fc26a6ade7edac15249c52f4b`](https://github.com/opendp/opendp/commit/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b), [implementation](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/sklearn/_make_eigenvector/__init__.py), [Rust internal measurement adapter](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/internal/mod.rs), [core measurement constructor](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/core/mod.rs). `make_np_sscp_projection` is separately claimed in [task #107](https://github.com/opendp/opendp-audit/issues/107).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `sklearn._make_eigenvector.make_private_eigenvector` | privacy/parameter-validation | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Negative epsilon is not rejected](#analysis); [defect #112](https://github.com/opendp/opendp-audit/issues/112) |
| `sklearn._make_eigenvector.make_private_eigenvector` | privacy/distribution-bound | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Distribution witness](#analysis); [cross-file investigation](../../../../../../../investigations/sklearn-eigenvector-negative-epsilon.md) |
| `sklearn._make_eigenvector.make_private_eigenvectors` | privacy/entrypoint-budget-validation | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Entries passed to nested eigenvector constructors](#analysis) |

| `sklearn._make_eigenvector.make_np_sscp_projection` | privacy/projection-contractivity | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Unchecked operator norm](#projection-contractivity-and-mutability); [defect #110](https://github.com/opendp/opendp-audit/issues/110) |
| `sklearn._make_eigenvector.make_np_sscp_projection` | correctness/projection-snapshot | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Mutable reference capture](#projection-contractivity-and-mutability); [upstream PR #3281](https://github.com/opendp/opendp/pull/3281) |

## Analysis

The `make_private_eigenvector` constructor checks `input_desc.p == 2` and `input_metric == symmetric_distance`, but does not check `unit_epsilon` for nonnegativity or finiteness. Its callback directly returns `d_in / 2 * unit_epsilon`; consequently `unit_epsilon=-0.2` returns `-0.2` at distance 2, with no constructor-time rejection from the Rust `_make_measurement` wrapper or `Measurement::new`. The entrypoint `then_private_eigenvector` exposes the same constructor.

For `C0=diag(1,0)` and `C1=diag(0,1)`, negative epsilon gives distinct `A` matrices and nonidentical Bingham densities. An independent NumPy/SciPy calculation gives a positive log likelihood ratio `0.05` at one unit vector despite the negative reported bound. The rejection-sampling acceptance expression remains numerically meaningful for this concrete example. See the [investigation](../../../../../../../investigations/sklearn-eigenvector-negative-epsilon.md) for the quantitative witness, explicit execution limits, and reproduction sketch.

The `make_private_eigenvectors` function forwards individual `unit_epsilons` to `then_private_eigenvector` in adaptive composition. Whether other constructors reject these values before invocation, and precise end-to-end composition exploitability, are not established here.

**Finding:** Confirmed source-level negative privacy accounting, reported in [#112](https://github.com/opendp/opendp-audit/issues/112). No native OpenDP tests were run. `Audited` above applies narrowly to the absence of a parameter guard, not the sampler's general correctness.

### Projection contractivity and mutability

**Scoped invariant:** `make_np_sscp_projection` is one-stable only when the matrix `P` has operator norm at most one; the returned function must not change if the caller later mutates their parameter. The [pinned implementation](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/sklearn/_make_eigenvector/__init__.py) checks only `P.shape[1]` against the input dimension, carries forward SSCP row-norm metadata, evaluates `P @ cov @ P.T`, and returns `lambda d_in: d_in`. It neither checks `||P||_2` nor copies `P`.

For one-row, one-feature bounded datasets `X=[[0.]]` and `X'=[[1.]]` (row norm at most one), their SSCP matrices are `C=0` and `C'=1`. At `P=[[2.]]`, projection maps them to 0 and 4, while reporting unit stability. With a subsequent `make_eigenvalues` transformation, the advertised sensitivity for one replacement at symmetric input distance two is `2 * 1**2 = 2`, below the actual output change four. In general `||P(C-C')P.T||_* <= ||P||_2**2 ||C-C'||_*`. The constructor does not certify the bound `||P||_2 <= 1`.

**Independent execution:** Standalone Python/NumPy matrix operations verified the change is one with `P=[[1.]]` and four after mutating that same `P` array to `[[2.]]`. The OpenDP package was not installed, so this is **not** an executed OpenDP regression or an end-to-end DP attack.

**Threat-model limitation:** `P` is documented as a projection whose singular values are at most one, and the built-in PCA caller constructs identity/null-space projection matrices. This is a conditional invalid stability certificate when the underscored helper is given a matrix violating the stated precondition, not evidence that default PCA releases are unsafe. The mutable-array variant can start from a *valid* `P` and then violate its contract after construction.

**Disposition:** [Issue #110](https://github.com/opendp/opendp-audit/issues/110) tracks the missing contractivity check. [Open upstream PR #3281](https://github.com/opendp/opendp/pull/3281) adds `np.array(P, copy=True)` to prevent aliasing, but explicitly documents that operator-norm contractivity remains an unchecked precondition. The [cross-file investigation](../../../../../../../investigations/pca-sscp-projection-contractivity.md) records the full reasoning and next proof obligations. **Status: Partial** for the cross-file privacy property and **Audited** for the mutable capture demonstrated directly in this file.

## Next checks

- Execute a native OpenDP regression for expansive `P=2I`; decide whether the underscored helper's documented norm bound must be checked or may remain caller-trusted, and verify PR #3281's snapshot fix.

- Run a native-library Python regression for `make_private_eigenvector(-0.2)` and `.map(2)`, then test construction-time rejection after patch.
- Check the sign/finite-value validation of structured `PCAEpsilons` and `make_private_eigenvectors` paths.
- Exercise multi-measurement composition to establish whether negative loss can be exploited to pass budget checks.
