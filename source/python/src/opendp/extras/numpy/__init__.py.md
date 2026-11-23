---
schema_version: 1
source: python/src/opendp/extras/numpy/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/numpy/__init__.py`

## Scope and assumptions

- **Additional independent scope:** Numerical false-negative membership in `_sscp_domain._member` for rank-deficient Gram matrices actually returned by `make_np_sscp`. Distinct from previously reported **false-positive** membership against `norm` and `size`. [Cross-file roundoff investigation](../../../../../../investigations/numpy-sscp-gram-psd-roundoff.md); pending PR #3281 would remove the strict PSD check.

- **Audit scope:** `_sscp_domain` and its nested `_member` predicate, limited to the declared L2 row-norm and fixed dataset-size semantics for positive-semidefinite matrices. Other NumPy domains, the floating-point robustness of eigensolvers, and arbitrary `p` are not reviewed.
- **Invariant:** If a domain advertises `C=X.T @ X` with `n` rows of norm at most `R`, each admitted matrix must satisfy the necessary bound `trace(C) <= n R^2` and `rank(C) <= n`. A downstream constructor must not use a metadata bound that domain membership fails to enforce.
- **Assumptions:** `R=1`, `n=1`, `p=2`, `T=float` and `num_features=2`; all test matrices are finite exact diagonal binary64 values.
- **Pinned source:** [NumPy domain implementation](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/__init__.py), [eigenvalue stability map](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/sklearn/_make_eigenvalues/__init__.py), [Laplace wrapper](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/_utilities.py).

- **Additional audit scope:** `array2_domain` real-valued Lp radius enforcement when `T=i64` and `origin` is large. A false-positive membership may be trusted by sized `make_np_sum`, yielding a sensitivity misstatement. This is distinct from `_sscp_domain` and no longer relies on the latter's matrix-specific assumptions.
- **Additional pinned sources:** [array2 constructor](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/__init__.py), [scaled Lp helper](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_norm.py), [sized sum](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_sum/__init__.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `_sscp_domain` | privacy/sscp-norm-membership | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Source trace and counterexample](#analysis); [cross-file investigation](../../../../../../investigations/sscp-domain-membership-and-eigenvalue-privacy.md) and [audit #115](https://github.com/opendp/opendp-audit/issues/115). |
| `_sscp_domain._member` | correctness/sscp-output-domain-closure | Audited | `a010591f55b1713c926f8e355091471634480307` | [Rank-one floating-point Gram matrix false negative](#sscp-rank-one-gram-matrix-numerical-false-negatives); [investigation](../../../../../../investigations/numpy-sscp-gram-psd-roundoff.md). |

| `opendp.extras.numpy.array2_domain` | privacy/integer-origin-membership-rounding | Audited | `a010591f55b1713c926f8e355091471634480307` | [Source-equivalent int64 false-positive membership witness](#array2-domain-large-integer-origin-false-positives), [investigation](../../../../../../investigations/numpy-integer-origin-membership-sensitivity.md), and [privacy issue #145](https://github.com/opendp/opendp-audit/issues/145) |

## Analysis

### `_sscp_domain` — `privacy/sscp-norm-membership`

**Conclusion:** For fixed `size` and finite L2 `norm`, the domain's `_member` predicate does not enforce the advertised SSCP trace bound. It checks NumPy type/dtype, squareness, feature count, finiteness, symmetry, and nonnegative eigenvalues, but does not use the descriptor's `norm`, `p`, or `size`.

**Evidence:** With `norm=1`, `size=1`, `num_features=2`, the matrices `C0=diag(0,0)` and `C1=diag(16,0)` pass each inspected membership predicate. Yet `trace(C1)=16 > 1*1^2`, so `C1` is not an SSCP of any admissible one-row dataset. The downstream `make_eigenvalues` applies `np.linalg.eigvalsh` while reporting stability `d_in*norm**2`. At input distance two this map yields 2, but these two matrices have eigenvalue vectors at L1 distance 16. See the [investigation](../../../../../../investigations/sscp-domain-membership-and-eigenvalue-privacy.md) for metric interpretation, Laplace composition, and limitations.

**Executed:** A standalone NumPy 2.3.5 model of the membership predicates, matrix eigenspectra, and trace calculations; four local unittest cases in [regression model](../../../../../../tools/tests/test_sscp_domain_membership_model.py) passed. **Not executed:** OpenDP's `Domain.member`, native `make_eigenvalues`, or the Laplace measurement. A compiled/runtime reproducer remains necessary.

**Limitations:** Ordinary `make_np_sscp` applied to valid bounded raw data produces matrices satisfying the intended bound; this audit does not establish a privacy loss in the standard PCA pipeline. It establishes the membership contract defect and its possible direct-constructor privacy consequence. Enforcing only trace is a necessary but not necessarily sufficient domain repair, particularly when `rank(C) > size`.

**Pending upstream resolution:** [PR #3281](https://github.com/opendp/opendp/pull/3281) (draft, base `sklearn-pca`, head `01cd7460894ebfade7066750e9a4b9313278cf42`) removes the problematic latent bounds by replacing `_sscp_domain` with a general finite symmetric matrix domain and nuclear-norm metric. `make_eigenvalues` then has an identity stability map; the counterexample matrices are distance 16 instead of 2. This covers the reported root cause but has not merged into `main`.

**Related:** [Audit #115](https://github.com/opendp/opendp-audit/issues/115) tracks the membership defect. [Audit #110](https://github.com/opendp/opendp-audit/issues/110) concerns the separate projection contract; upstream [#2952](https://github.com/opendp/opendp/issues/2952) concerns nonzero origins in `make_np_sscp`.

### `array2_domain` — large integer-origin false positives

**Conclusion:** The rowwise NumPy membership check can admit `int64` rows whose exact real-valued offset from the declared public center far exceeds the norm radius. The helper `_rows_within_norm` receives the already rounded difference and cannot recover the lost integer offsets. This violates the domain's advertised membership predicate, not merely a downstream implementation assumption.

**Pinned source:** `array2_domain` converts an integer `origin` ndarray to `float64`, then `_member` checks `centered = x - origin` and `_rows_within_norm(centered,norm,p)`. For an `int64` `x` around `O=2**60`, the mixed-type subtraction promotes `x` to float64 before subtracting, rounding both `O-64` and `O+128` to `O`. With `norm=1`, `p=1` or `2`, `size=1`, `num_columns=1`, `T=i64`, both arrays are declared members although their actual row-to-origin distances are 64 and 128. A sized `make_np_sum` then emits the original exact int64 sums `O-64` and `O+128`: separation `192` despite a nominal map `2*norm=2` at `d_in=2` (96×). Unlike [#143](https://github.com/opendp/opendp-audit/issues/143), this case has no integer summation overflow.

**Executed:** Source-equivalent NumPy 2.3.5 origin promotion, literal domain membership predicate, scaled helper, sums and map arithmetic; see [standalone regression](../../../../../../tools/tests/test_numpy_integer_origin_membership_model.py) and [full investigation](../../../../../../investigations/numpy-integer-origin-membership-sensitivity.md). **Not executed:** Native OpenDP FFI membership, map evaluation, or noise release. Because of the separate possible int64-metric/float callback type mismatch, this establishes a domain-membership and source-level stability-map violation, **not an observed end-to-end privacy guarantee failure**. [Issue #145](https://github.com/opendp/opendp-audit/issues/145) tracks the new root cause.

### SSCP rank-one Gram matrix numerical false negatives

A **separate** containment error runs opposite to audit #115. For `array2_domain(norm=1,p=2,size=1,num_columns=2,nan=False,T=f64)`, the input `X=[[0.5,0.7]]` has row-L2 norm approximately `0.8602` and is admitted. The current `make_np_sscp` computes `C=X.T@X`. On NumPy 2.3.5 this yields finite, exactly symmetric `C=[[0.25,0.35],[0.35,0.48999999999999994]]`, but its LAPACK-computed eigenvalues include `-5.551115123125783e-17`. The domain's exact `np.any(np.linalg.eigvals(C)<0)` guard rejects **the transformation's own valid-input output**. The same row under f32 has a small negative computed eigenvalue. This disproves `make_np_sscp`'s concrete floating-point **output-domain closure** under this backend without relying on extreme values, NaN, overflow or an invalid public precondition.

**Evidence:** [Independent NumPy regression](../../../../../../tools/tests/test_sscp_gram_psd_rounding_model.py) and [cross-file analysis](../../../../../../investigations/numpy-sscp-gram-psd-roundoff.md). **Executed:** Source-equivalent NumPy f32/f64 Gram product and strict eigenvalue membership; **not executed:** native OpenDP `Domain.member` and full private PCA release. This is a correctness/domain-contract failure, **not** an observed privacy-accounting breach. `idealized-numerics` does not model finite floating-point effects.

**Upstream disposition:** Draft [PR #3281](https://github.com/opendp/opendp/pull/3281), still unmerged on reviewed main `a010591f55b1713c926f8e355091471634480307`, replaces the old domain by a finite symmetric matrix domain that **does not require PSD**. This change directly addresses the false-negative contract for symmetric rounded Gram matrices, in addition to the distinct provenance-bound issue tracked by #115. No duplicate issue was filed.

## Next checks

For `array2_domain`, run native membership for `T=i64`, `norm=1`, `origin=[2**60]`, `x0=[[2**60-64]]` and `x1=[[2**60+128]]`; reject falsely admitted rows using exact or conservative centering rather than a float64 upcast.

Run a pinned OpenDP Python integration proving the actual `domain.member(C1)`, `make_eigenvalues(...).map(2)`, and output difference. Examine all downstream constructors trusting the `NPSSCPDomain` descriptor and require enforceable bounds or explicit trusted-provenance preconditions.
