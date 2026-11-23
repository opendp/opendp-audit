---
schema_version: 1
source: python/src/opendp/extras/numpy/canonical.py
updated: 2026-11-23
---

# `python/src/opendp/extras/numpy/canonical.py`

## Scope and assumptions

- **Audit scope:** `BinomialCND` confidence-interval inversion for the `Binomial(size, θ) + Tulap` observation model, inspecting p-value and CDF dependencies.
- **Invariant:** A nominal `1 - alpha` confidence limit must have at least `1 - alpha` frequentist coverage under the stated statistical model.
- **Assumptions:** Valid `alpha=0.05`, `size=10`, pure-DP `d_out=(10.0, 0.0)`, `d_in=1`. The statistical proof is source-level; native OpenDP was not run.
- **Source links:** [canonical.py](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/canonical.py), [incomplete fixed-count test](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/test/extras/test_canonical_noise_numpy.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `opendp.extras.numpy.canonical.one_sided_confidence_interval` | statistics/frequentist-coverage | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Cross-file exact undercoverage argument](../../../../../../investigations/binomial-cnd-ci-inversion-and-coverage.md); [issue #128](https://github.com/opendp/opendp-audit/issues/128). |
| `opendp.extras.numpy.canonical.two_sided_confidence_interval` | statistics/test-inversion | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Source swaps observed `Z` and candidate `theta`; numerical endpoint witness in [investigation](../../../../../../investigations/binomial-cnd-ci-inversion-and-coverage.md). |
| `opendp.extras.numpy.canonical.BinomialCND.confidence_interval` | statistics/delegation | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Delegates the public API to both affected interval functions without adjustment. |
| `opendp.extras.numpy.canonical.one_sided_pvalue` | statistics/null-test-orientation | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Right tail is survival of noisy count for fixed θ; checked for inversion but not exhaustively verified for all numeric parameters. |
| `opendp.extras.numpy.canonical.two_sided_pvalue` | statistics/null-test-orientation | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Reviewed as a dependency for the incorrect two-sided inversion; full two-sided test validity remains outside scope. |
| `opendp.extras.numpy.canonical._cnd_cdf` | statistics/tulap-central-mass | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Numerically checked source formula at ε=10, δ=0; no complete sampler/CDF audit claimed. |

## Analysis

### One-sided interval — `statistics/frequentist-coverage`

**Conclusion:** Confirmed failure. The routine passes candidate bound `B` as `Z=B*size`, and uses the observed MLE `clip(Z/size,0,1)` as fixed null `theta`. For an upper bound, a correct test inversion holds the actual observed noisy count fixed and varies the candidate θ under the left-tail p-value. The source's inversion can exclude θ=0.2 with probability at least 0.107364433, despite nominal alpha=0.05.

**Evidence:** See [investigation](../../../../../../investigations/binomial-cnd-ci-inversion-and-coverage.md) for exact binomial/Tulap event, computed predicate upper bound, and runnable equations.

**Limitations:** Computations reproduce the source formulas in standalone NumPy/SciPy, without executing native OpenDP; other parameter and endpoint cases remain untested.

### Two-sided interval — `statistics/test-inversion`

**Conclusion:** The source repeats the argument swap. For a noisy observation Z=0 and size=10, numerical root of implemented inversion returns upper bound ~0.04750, whereas holding Z fixed and inverting the same two-sided p-value over candidate θ returns ~0.28077. This is evidence of an incorrect confidence-interval construction, not a complete proof of the nominal coverage of the corrected two-sided construction.

**Evidence:** [Investigation](../../../../../../investigations/binomial-cnd-ci-inversion-and-coverage.md) and [issue #128](https://github.com/opendp/opendp-audit/issues/128).

### Dependency checks

The `BinomialCND.confidence_interval` dispatcher forwards to the two interval functions. The underlying fixed-θ p-value and Tulap CDF routines were inspected sufficiently to provide the finite-sample one-sided counterexample; full CDF accuracy and mechanism correctness are not asserted. A pre-existing test samples from Tulap centered at a **fixed** count rather than varying the binomial count, and thus fails to test confidence coverage under the model.

## Next checks

Fix the inversion and tail orientation, add exact finite-sample coverage tests against binomial-plus-noise observations, and exercise the native `BinomialCND` wrapper with the witness parameters.
