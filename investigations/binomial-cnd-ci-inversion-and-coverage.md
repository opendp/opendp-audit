---
schema_version: 1
upstream_commit: 7acfb2cdcee7d39fc26a6ade7edac15249c52f4b
updated: 2026-11-23
status: Partial
---

# BinomialCND confidence intervals invert the hypothesis-test parameters

## Invariant and threat model

`BinomialCND` is a postprocessing helper for the published model `Z = X + N`, where `X ~ Binomial(size, θ)` and `N` is independently drawn from the canonical/Tulap distribution calibrated by `d_in` and `d_out`. At significance `alpha`, a one-sided `side="upper"` confidence limit should have frequentist coverage at least `1 - alpha` for any `θ ∈ [0, 1]`; similarly for a two-sided interval. This is a **statistical correctness** property, not an OpenDP privacy-mechanism property. The vulnerability is that an incorrectly narrow reported confidence limit could lead to unsupported conclusions about the unknown proportion.

Assumptions: legitimate finite parameters `size=10`, `d_in=1`, `d_out=(ε=10, δ=0)`, `alpha=0.05`; no adversarial mutation of parameters. Test and source correspond to upstream `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b`.

## Affected symbols and source audits

- [`python/src/opendp/extras/numpy/canonical.py`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/canonical.py): `BinomialCND.confidence_interval`, `one_sided_confidence_interval`, `two_sided_confidence_interval`, `one_sided_pvalue`, `two_sided_pvalue`, and `_cnd_cdf`.
- [`python/test/extras/test_canonical_noise_numpy.py`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/test/extras/test_canonical_noise_numpy.py): its `test_confidence_interval` samples *only noise* around a fixed `Z=100`, not joint binomial counts and independent noise. It cannot establish frequentist coverage for varying true θ.
- [Source audit](../source/python/src/opendp/extras/numpy/canonical.py.md).
- [Audit issue #128](https://github.com/opendp/opendp-audit/issues/128); [audit task #126](https://github.com/opendp/opendp-audit/issues/126).

## Reasoning and evidence

### Inversion swaps observation and null parameter

The one-sided routine computes `mle = clip(Z / size, 0, 1)` and chooses a bound `B` by evaluating:

```python
one_sided_pvalue(
    Z=B * size,
    d_in=d_in,
    d_out=d_out,
    size=size,
    theta=mle,
    tail={"lower": "left", "upper": "right"}[side],
) > alpha
```

Here `B` (the candidate null parameter) is incorrectly placed in the **observed-count** slot, and `mle` (estimated from the private observation) is incorrectly placed in the **null θ** slot. For an upper confidence limit, the valid inverted hypothesis test holds the observed `Z` fixed and varies `theta=B`, using the *left-tail* p-value for low noisy observations. The two-sided routine makes the same swap, using `two_sided_pvalue(B * size, ..., theta=mle)`.

### Numerically evaluated exact counterexample

Executed a standalone faithful transcription of the source `_cnd_cdf`, `one_sided_pvalue`, and `two_sided_pvalue` under NumPy **2.3.5** and SciPy **1.17.0**, and solved the returned continuous p-value boundaries with `scipy.optimize.brentq`. The OpenDP Python package/native library was **not installed or executed**.

At `size=10, d_in=1, d_out=(10.0, 0.0), alpha=0.05, Z=0`:

| Bound | Current argument-swapped search | Search with fixed observation and candidate θ |
| --- | ---: | ---: |
| One-sided upper | `0.04500408617919087` | `0.20568110318335647` |
| Two-sided upper | `0.04750431318914592` | `0.28076778574977784` |

These discrepancies alone motivate correction, but the next calculation establishes actual frequentist *undercoverage*.

### Rigorous finite-sample undercoverage bound

Take true θ = **0.2** and `X ~ Binomial(10, 0.2)`. For pure-DP Tulap noise with `ε=10`, the probability of being in the central uniform cell `[-1/2, 1/2]` is exactly `(1 - b)/(1 + b)`, where `b = exp(-10)`. On the joint event

```text
E = {X = 0 and N ∈ [-0.5, 0.5]}
```

the noisy observation is `Z ∈ [-0.5, 0.5]` and the implementation uses `mle = clip(Z/10, 0, 1) ≤ 0.05`. The implemented upper-bound predicate for `B=0.2` is maximized at `mle=0.05`, yielding:

```text
one_sided_pvalue(Z=2.0, d_in=1, d_out=(10, 0),
                 size=10, theta=0.05, tail="right")
    = 0.04882787279160891 < alpha=0.05
```

Because this predicate decreases with candidate B, the reported upper bound is below θ=0.2 throughout E. Its probability is

```text
P(E) = (0.8)^10 * (1 - exp(-10)) / (1 + exp(-10))
     = 0.10736443328193082.
```

Hence `P_θ(upper_bound < θ) ≥ 10.736%`, versus the nominal maximum 5%. The *coverage* is at most **89.264%**, invalidating the claimed 95% one-sided confidence level.

### Duplicate and pending-fix check

Searched open and closed `opendp/opendp` and `opendp/opendp-audit` issues for `BinomialCND`, canonical confidence intervals, Tulap, and binomial confidence bounds; no equivalent defect was found before filing. Upstream [PR #2859](https://github.com/opendp/opendp/pull/2859) changes canonical-noise construction and `python/test/extras/test_canonical_noise_numpy.py`, **not** `canonical.py`; it does not repair this interval inversion. This is not related to the negative-epsilon eigenvector bug or numerical privacy accounting.

## Findings

- **Confirmed source-level statistical coverage failure:** [audit defect #128](https://github.com/opendp/opendp-audit/issues/128), upstream disposition **Unreported**, severity **correctness** and **important**.
- The failure is demonstrably not caused by numerical roundoff or finite precision in native samplers: the exact binomial/Tulap model itself gives a coverage violation for the stated source formula.
- No claim is made of differential-privacy leakage, Rust memory unsafety, or execution of the native OpenDP integration test.

## Unresolved questions

1. Execute an end-to-end regression against native OpenDP `BinomialCND(estimate=0.0, d_in=1.0, d_out=(10.0, 0.0), size=10)` and capture both upper and two-sided bounds.
2. Repair inversion to vary `theta=B` with the observation held fixed; verify correct one-/two-sided tail conventions, boundary behavior at θ=0 and θ=1, and strict versus non-strict inequality for continuous Tulap noise.
3. Add a deterministic coverage proof/regression involving `X ~ Binomial(n, θ)`, not a fixed-count-only noise simulation; test the discrete/continuous limiting cases.
