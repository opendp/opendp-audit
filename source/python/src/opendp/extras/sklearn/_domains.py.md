---
schema_version: 1
source: python/src/opendp/extras/sklearn/_domains.py
updated: 2026-11-23
---

# `python/src/opendp/extras/sklearn/_domains.py`

## Scope and assumptions

- **Scope:** `SklearnFit`, `SklearnFitDescriptor`, `sklearn_fit_domain`, and `_n_rows`: enforce row alignment between features `X` and optional target `y` under the two independently supplied domains. Inspect `context.domain_of(infer=True)` and `DPEstimator.fit` as callers; exclude Theil–Sen's separately claimed warning side-channel audit and estimator-specific privacy proofs.
- **Invariants:** (1) For standard supported array/matrix `X` and vector `y`, membership implies that `X` and `y` separately belong to their respective declared domains and have equal first-axis lengths. (2) If no target domain is specified, the dataset must have no target, and conversely. (3) The default high-level `fit` path constructs/checks a measurement at the requested allowance before invoking it. These checks are public-domain prerequisites, not a proof that any estimator's internal mechanism is private.
- **Assumptions:** The primitive domain `member` methods accurately recognize their carrier types; `X` is a supported 2-D NumPy matrix or SciPy sparse matrix and `y` is a 1-D NumPy array or Python vector. A valid feature carrier has tuple `.shape`, and a valid vector supports `len`. A custom extrinsic `X` or `y` domain may admit other carriers; those cases are separately qualified below.
- **Pinned source:** [SklearnFit domain](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/sklearn/_domains.py), [standalone estimator](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/sklearn/_estimator.py), [domain inference](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/context.py), [upstream aligned-input regressions](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/test/extras/test_sklearn_aligned.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `sklearn_fit_domain` | correctness/aligned-features-target-membership | Audited | `a010591f55b1713c926f8e355091471634480307` | [Membership control flow](#membership-and-alignment); [independent test](../../../../../../tools/tests/test_sklearn_fit_alignment_model.py). |
| `sklearn_fit_domain` | correctness/optional-target-presence | Audited | `a010591f55b1713c926f8e355091471634480307` | [Membership control flow](#membership-and-alignment). |
| `_n_rows` | correctness/first-axis-row-count | Partial | `a010591f55b1713c926f8e355091471634480307` | [Supported and unsupported shape carriers](#row-count-extraction). |
| `SklearnFitDescriptor` | correctness/declared-domains | Audited | `a010591f55b1713c926f8e355091471634480307` | [Descriptor and inference](#descriptor-and-inference). |

## Analysis

### Membership and alignment

`sklearn_fit_domain(X, y)` constructs an extrinsic domain with `SklearnFitDescriptor(X,y)` and an explicit `member` callback. Its guard order is:

1. Require `isinstance(value, SklearnFit)`.
2. Require the supplied feature domain to accept `value.X`.
3. Require exact target presence consistency: `(y is None) == (value.y is None)`.
4. For a declared target domain, require it to accept `value.y` and require `_n_rows(value.X) == _n_rows(value.y)`.

Therefore, assuming ordinary carrier-domain soundness and total row-count extraction, a successful membership result cannot admit a mismatched feature/target length or silently drop an expected target. The two input domains' own fixed row counts, if present, provide additional independent constraints; the alignment check still operates when neither domain declares a fixed size.

**Executed:** A standard-library Python source-equivalent model exhaustively checked all **81** combinations of `X` and `y` row counts in `[0,8]`, plus missing-target, invalid-carrier, and zero-row cases. All assertions passed in the committed [standalone test](../../../../../../tools/tests/test_sklearn_fit_alignment_model.py). Source inspection of [upstream tests](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/test/extras/test_sklearn_aligned.py) found corresponding native Python tests for sized/mismatched NumPy arrays, 1-D vector targets, noncontiguous array views and SciPy sparse matrices. Those upstream tests were **inspected, not executed** here.

### Row-count extraction

`_n_rows` obtains `shape = getattr(value, "shape", None)` and uses `int(shape[0])` if truthy, otherwise `len(value)`. This returns the row dimension for NumPy feature matrices and SciPy sparse matrices and the length for Python lists or 1-D vectors. For standard supported inputs it agrees with the first-axis row count.

**Limitation:** The helper is *not* total over arbitrary custom domain carriers. In the source-equivalent model, if a custom target domain erroneously accepts an unsized scalar, `_n_rows(42)` raises `TypeError` instead of returning False. An unusual custom object whose `shape` has ambiguous truth value may raise at the `if shape` check. This is a constructor-contract/totality boundary, not a verified OpenDP privacy violation: the supported standard target types are sized, and `Domain.member` normally catches noncritical callback exceptions and reports false. Do not label this as a confirmed privacy failure.

### Descriptor and inference

The `SklearnFitDescriptor` is a frozen dataclass containing the two declared domain handles. The enclosing extrinsic-domain `descriptor` access returns a deep copy. `context.domain_of(SklearnFit(X, y), infer=True)` constructs domains for `X` and `y` recursively. For NumPy two-dimensional `X`, this records **dtype and feature count**, but not private row count or data-dependent norm; target vector inference records dtype, not values. `DPEstimator.fit` uses inferred domains only when no explicit domain is provided, then calls `self.make`, casts its output measure as needed, verifies `measurement.check(d_in,d_out)`, and invokes the measurement. No raw fit data is sent to the measurement before that allowance check in this control flow.

**Privacy qualification:** `domain_of(..., infer=True)` explicitly warns that inferring domains from sensitive examples may violate privacy. This API may reveal presence/absence of targets and dtype/feature-schema information through constructor behavior; these properties must be considered public or supplied explicitly in applications that require them private. The domain's row-alignment check alone does not guarantee estimator privacy or protect against all data-dependent exceptions.

## Findings and next checks

**No new defect established under the reviewed ordinary NumPy/list/sparse carrier contract.** The source-level membership guards enforce the declared alignment invariant, and the inference path does not infer NumPy row count as a publicly fixed size. The independent model and upstream-test inspection are not native FFI verification.

For completeness, run the upstream `test_sklearn_aligned.py` suite on the pinned revision and examine custom-domain carriers that are not sized, including whether exceptions should be normalized to false. Separately verify `DPEstimator.make` implementations for estimator-specific privacy, keeping clear of the active [Theil–Sen side-channel claim #133](https://github.com/opendp/opendp-audit/issues/133). No candidate-defect issue warranted for the scoped standard-carrier property.
