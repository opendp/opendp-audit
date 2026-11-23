---
schema_version: 1
upstream_commit: 7acfb2cdcee7d39fc26a6ade7edac15249c52f4b
updated: 2026-11-23
status: Partial
---

# SSCP membership and private eigenvalue sensitivity

## Invariant and threat model

The extrinsic `_sscp_domain(norm=R, p=2, size=n, num_features=k)` describes `k x k` SSCP matrices `C = X.T @ X`, where `X` is an `n x k` dataset whose row L2 norms do not exceed `R`. Every such `C` is PSD and must satisfy

```text
trace(C) = sum_i ||X_i||_2^2 <= n R^2;
rank(C) <= n.
```

The audited property is **whether domain membership enforces the necessary range of the norm-bounded, fixed-size input representation before a direct downstream private eigenvalue constructor trusts the descriptor**. The threat is a lower-level caller supplying an SSCP matrix directly, not the usual pipeline that first validates bounded raw rows and computes `X.T @ X`.

## Affected symbols and source audits

- [`_sscp_domain` / nested `_member` (7acfb2cdcee7d39fc26a6ade7edac15249c52f4b)](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/__init__.py): checks shape, dtype, finite, symmetry, PSD, but never accesses `norm`, `p`, `size` inside membership. [Source report](../source/python/src/opendp/extras/numpy/__init__.py.md).
- [`make_eigenvalues` (7acfb2cdcee7d39fc26a6ade7edac15249c52f4b)](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/sklearn/_make_eigenvalues/__init__.py): accepts `NPSSCPDomain` with a declared `size`, computes `eigvalsh`, and maps `d_in` to `d_in * norm**2` under `SymmetricDistance` and output `L1Distance`.
- [`with_privacy` (7acfb2cdcee7d39fc26a6ade7edac15249c52f4b)](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/_utilities.py): `make_private_eigenvalues` chains this transformation into `then_laplace(scale)` under `MaxDivergence`.
- [`make_np_sscp` (7acfb2cdcee7d39fc26a6ade7edac15249c52f4b)](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/_make_np_sscp/__init__.py): computes `X.T @ X` from row-bounded input; an ordinary valid source does not generate the out-of-range example below.
- Tracked in [audit #115](https://github.com/opendp/opendp-audit/issues/115). Separate [#110](https://github.com/opendp/opendp-audit/issues/110) concerns a noncontractive projection rather than domain membership.

## Reasoning and evidence

Choose `R=1`, `n=1`, `k=2`, `p=2`, `T=float`; define two exactly representable `float64` matrices:

```python
import numpy as np
C0 = np.zeros((2, 2), dtype=np.float64)
C1 = np.diag([16.0, 0.0])
```

Both are finite, symmetric, PSD, and of the expected dtype and shape. Thus both pass **every explicit membership check** in the current `_sscp_domain`. But `trace(C1)=16 > n R^2=1`; it is not `X.T @ X` from a one-row, unit-norm dataset. Its implicit generating row would need norm 4.

The direct lower-level `make_eigenvalues` transformation computes

```text
eigvalsh(C0) = [0, 0]
eigvalsh(C1) = [0, 16]
L1 output distance = 16
stability_map(2) = 2 * 1**2 = 2.
```

For a row-multiset `SymmetricDistance` on the 2-row matrix carriers, `C0` and `C1` differ by a single row replacement, so the distance is at most 2; even the looser bound 4 for any two matrices of two rows yields a reported 4, below 16. **Metric caveat:** the proof of `make_eigenvalues` is intended for underlying row-level datasets whose SSCPs are supplied, not for arbitrary raw matrices. The domain's acceptance of matrices with no admissible underlying dataset is precisely the missing precondition. This finding does not assume these invalid matrices can be generated through a correctly configured `make_np_sscp` transformation.

Under ideal independent `Laplace(scale=1)` noise on the two eigenvalues, the event `Y[1] <= 0` has probability `1/2` at `C0` and `exp(-16)/2` at `C1`. Their ratio is `exp(16)`, whereas the chained map would use the underestimated sensitivity 2. This is a distribution-level **conditional** argument; the installed native OpenDP chain and sampler were not executed.

**Executed locally:** an independent NumPy 2.3.5 calculation of all visible matrix membership predicates, eigenspectra, trace, and sensitivity equation, together with four standard-library/optional NumPy tests in [model test](../tools/tests/test_sscp_domain_membership_model.py); all four passed. No native OpenDP invocation was executed. The witness matrices and scalar computations are exact in binary floating point.

## Findings

**Source-confirmed domain contract violation with an independently reproduced counterexample.** The missing membership constraint is unreported in targeted open/closed upstream issue and PR searches at the reviewed revision. Its possible privacy consequence requires **direct lower-level construction** from an `NPSSCPDomain`; the normal bounded-input `make_np_sscp` flow is not shown vulnerable. Keep this separate from the projection amplification in [audit #110](https://github.com/opendp/opendp-audit/issues/110) and nonzero origin in [upstream #2952](https://github.com/opendp/opendp/issues/2952).

## Unresolved questions

1. Execute a pinned OpenDP integration for `domain.member(C1)`, `make_eigenvalues(...).map(2)`, and the actual function output. Assess any unexpected extrinsic-domain or metric limitations.
2. Decide whether to enforce necessary `trace(C) <= size*norm**2` and `rank(C) <= size` constraints with numerical tolerances, or redesign the API so a direct `NPSSCPDomain` cannot claim trusted latent dataset bounds that membership cannot validate.
3. Review all direct consumers (`make_private_eigenvalues`, `make_private_eigenvector`, and projection helpers) after selecting a repair, including the distinction between directly supplied SSCP matrices and outputs of bounded `make_np_sscp`.
