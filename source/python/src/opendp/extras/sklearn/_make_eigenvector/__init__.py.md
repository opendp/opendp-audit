---
schema_version: 1
source: python/src/opendp/extras/sklearn/_make_eigenvector/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/sklearn/_make_eigenvector/__init__.py`

## Scope and assumptions

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

## Analysis

The `make_private_eigenvector` constructor checks `input_desc.p == 2` and `input_metric == symmetric_distance`, but does not check `unit_epsilon` for nonnegativity or finiteness. Its callback directly returns `d_in / 2 * unit_epsilon`; consequently `unit_epsilon=-0.2` returns `-0.2` at distance 2, with no constructor-time rejection from the Rust `_make_measurement` wrapper or `Measurement::new`. The entrypoint `then_private_eigenvector` exposes the same constructor.

For `C0=diag(1,0)` and `C1=diag(0,1)`, negative epsilon gives distinct `A` matrices and nonidentical Bingham densities. An independent NumPy/SciPy calculation gives a positive log likelihood ratio `0.05` at one unit vector despite the negative reported bound. The rejection-sampling acceptance expression remains numerically meaningful for this concrete example. See the [investigation](../../../../../../../investigations/sklearn-eigenvector-negative-epsilon.md) for the quantitative witness, explicit execution limits, and reproduction sketch.

The `make_private_eigenvectors` function forwards individual `unit_epsilons` to `then_private_eigenvector` in adaptive composition. Whether other constructors reject these values before invocation, and precise end-to-end composition exploitability, are not established here.

**Finding:** Confirmed source-level negative privacy accounting, reported in [#112](https://github.com/opendp/opendp-audit/issues/112). No native OpenDP tests were run. `Audited` above applies narrowly to the absence of a parameter guard, not the sampler's general correctness.

## Next checks

- Run a native-library Python regression for `make_private_eigenvector(-0.2)` and `.map(2)`, then test construction-time rejection after patch.
- Check the sign/finite-value validation of structured `PCAEpsilons` and `make_private_eigenvectors` paths.
- Exercise multi-measurement composition to establish whether negative loss can be exploited to pass budget checks.
