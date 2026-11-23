---
schema_version: 1
upstream_commit: 7acfb2cdcee7d39fc26a6ade7edac15249c52f4b
updated: 2026-11-23
status: Partial
---

# PCA SSCP projection contractivity and privacy calibration

## Invariant and threat model

A public projection `P` used in `C \mapsto PCP^T` can preserve a nuclear norm (or a row-norm-based SSCP) sensitivity bound only when its spectral norm is at most one: `||P(C-C')P^T||_* <= ||P||_2^2 ||C-C'||_*`. On reviewed `main`, `make_np_sscp_projection` carries forward the source SSCP domain's row-norm descriptor and returns the identity stability map without checking this condition or snapshotting the supplied array. If a consumer supplies `P` with spectral norm greater than one, a downstream privacy map may understate sensitivity.

This is a **conditional helper misuse** finding, not evidence that the built-in PCA estimator violates DP: its built-in call path constructs `P` as an identity or the transpose of a null-space basis, which is intended to be contractive. The helper lives in an underscored Python module, and its docstring already states the norm precondition.

## Affected symbols and source audits

- [`make_np_sscp_projection` (pinned)](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/sklearn/_make_eigenvector/__init__.py) and [source report](../source/python/src/opendp/extras/sklearn/_make_eigenvector/__init__.py.md): `lambda cov: P @ cov @ P.T`; `lambda d_in: d_in`; validates only matrix width.
- [`make_np_sscp` (pinned)](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/_make_np_sscp/__init__.py): computes `X.T @ X`, preserves input `SymmetricDistance` and supplies an SSCP descriptor with the original row norm.
- [`make_eigenvalues` (pinned)](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/sklearn/_make_eigenvalues/__init__.py): applies eigenvalues and the map `d_in * input_desc.norm**2`.
- [`make_private_eigenvectors` (pinned)](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/sklearn/_make_eigenvector/__init__.py): generates contractive `P` internally, narrowing exposure in default PCA.
- [Open PR #3281](https://github.com/opendp/opendp/pull/3281): changes matrix distance to nuclear norm and snapshots `P`, but explicitly leaves `||P||_2 <= 1` unchecked as a precondition.

## Reasoning and evidence

Take fixed-size one-row datasets `X=[[0.0]]` and `X'=[[1.0]]` under public per-row `L2` norm bound one, giving `C=X.T@X=[[0]]` and `C'=[[1]]`. One replacement costs `d_in=2` under symmetric distance. Let `P=[[2.0]]`; then `P@C@P.T=[[0]]` and `P@C'@P.T=[[4]]`. The projection map still reports distance two, and the downstream eigenvalue map at norm one reports a sensitivity bound of `2 * 1**2 = 2`, whereas the true output difference is four.

Equivalently, `||P||_2^2=4` amplifies the SSCP difference by four; a claim of unit stability cannot hold for this input.

**Independent executed check:** In a standalone Python interpreter with NumPy, multiplying these 1×1 matrices at `P=[[1]]` yielded projected difference 1, then mutating the same array to `P=[[2]]` yielded 4. The test exercised matrix algebra only. It did **not** instantiate or execute OpenDP, which was not installed in the runtime.

**Aliasing on current main:** the lambda captures the supplied mutable array `P`; no `copy()` is made. Hence even a valid `P=np.eye(1)` at construction can become invalid if its caller mutates it afterward. PR #3281 uses `np.array(P, copy=True)`, so this variant is **pending a fix**. That PR nevertheless documents the operator-norm check as an unverified precondition.

**Search/dedup:** Searched open and closed issues and PRs for SSCP, projection, PCA, and the helper symbol. [Upstream issue #2952](https://github.com/opendp/opendp/issues/2952) is a distinct fixed nonzero-origin defect.

## Findings

[Audit candidate #110](https://github.com/opendp/opendp-audit/issues/110): unchecked contraction precondition means the transformation can understate downstream noise requirements if the helper is directly used with an expansive matrix. Verification is source-level and mathematical, with no end-to-end installed OpenDP reproduction. Status is **Partial**, pending trust-boundary clarification, package-level test, and possible correction.

## Unresolved questions

- Is the internal `make_np_sscp_projection` helper intentionally allowed to rely on caller-checked preconditions, or should its `contrib` API reject expansive matrices?
- Run native regression for `P=2I` and verify construction/claimed map on current `main`; repeat after PR #3281.
- A safe remedy is either a certified upper bound on `||P||_2^2` in the map, or input rejection for operators exceeding one; snapshot the matrix (already proposed in #3281).
- Full end-to-end privacy loss and numerical SVD validation were not reviewed.
