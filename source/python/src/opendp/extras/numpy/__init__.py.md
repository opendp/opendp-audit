---
schema_version: 1
source: python/src/opendp/extras/numpy/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/numpy/__init__.py`

## Scope and assumptions

- **Audit scope:** `_sscp_domain` and its nested `_member` predicate, limited to the declared L2 row-norm and fixed dataset-size semantics for positive-semidefinite matrices. Other NumPy domains, the floating-point robustness of eigensolvers, and arbitrary `p` are not reviewed.
- **Invariant:** If a domain advertises `C=X.T @ X` with `n` rows of norm at most `R`, each admitted matrix must satisfy the necessary bound `trace(C) <= n R^2` and `rank(C) <= n`. A downstream constructor must not use a metadata bound that domain membership fails to enforce.
- **Assumptions:** `R=1`, `n=1`, `p=2`, `T=float` and `num_features=2`; all test matrices are finite exact diagonal binary64 values.
- **Pinned source:** [NumPy domain implementation](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/__init__.py), [eigenvalue stability map](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/sklearn/_make_eigenvalues/__init__.py), [Laplace wrapper](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/_utilities.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `_sscp_domain` | privacy/sscp-norm-membership | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Source trace and counterexample](#analysis); [cross-file investigation](../../../../../../investigations/sscp-domain-membership-and-eigenvalue-privacy.md) and [audit #115](https://github.com/opendp/opendp-audit/issues/115). |

## Analysis

### `_sscp_domain` — `privacy/sscp-norm-membership`

**Conclusion:** For fixed `size` and finite L2 `norm`, the domain's `_member` predicate does not enforce the advertised SSCP trace bound. It checks NumPy type/dtype, squareness, feature count, finiteness, symmetry, and nonnegative eigenvalues, but does not use the descriptor's `norm`, `p`, or `size`.

**Evidence:** With `norm=1`, `size=1`, `num_features=2`, the matrices `C0=diag(0,0)` and `C1=diag(16,0)` pass each inspected membership predicate. Yet `trace(C1)=16 > 1*1^2`, so `C1` is not an SSCP of any admissible one-row dataset. The downstream `make_eigenvalues` applies `np.linalg.eigvalsh` while reporting stability `d_in*norm**2`. At input distance two this map yields 2, but these two matrices have eigenvalue vectors at L1 distance 16. See the [investigation](../../../../../../investigations/sscp-domain-membership-and-eigenvalue-privacy.md) for metric interpretation, Laplace composition, and limitations.

**Executed:** A standalone NumPy 2.3.5 model of the membership predicates, matrix eigenspectra, and trace calculations; four local unittest cases in [regression model](../../../../../../tools/tests/test_sscp_domain_membership_model.py) passed. **Not executed:** OpenDP's `Domain.member`, native `make_eigenvalues`, or the Laplace measurement. A compiled/runtime reproducer remains necessary.

**Limitations:** Ordinary `make_np_sscp` applied to valid bounded raw data produces matrices satisfying the intended bound; this audit does not establish a privacy loss in the standard PCA pipeline. It establishes the membership contract defect and its possible direct-constructor privacy consequence. Enforcing only trace is a necessary but not necessarily sufficient domain repair, particularly when `rank(C) > size`.

**Related:** [Audit #115](https://github.com/opendp/opendp-audit/issues/115) tracks the membership defect. [Audit #110](https://github.com/opendp/opendp-audit/issues/110) concerns the separate projection contract; upstream [#2952](https://github.com/opendp/opendp/issues/2952) concerns nonzero origins in `make_np_sscp`.

## Next checks

Run a pinned OpenDP Python integration proving the actual `domain.member(C1)`, `make_eigenvalues(...).map(2)`, and output difference. Examine all downstream constructors trusting the `NPSSCPDomain` descriptor and require enforceable bounds or explicit trusted-provenance preconditions.
