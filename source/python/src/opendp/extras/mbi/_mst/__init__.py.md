---
schema_version: 1
source: python/src/opendp/extras/mbi/_mst/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/mbi/_mst/__init__.py`

## Scope and assumptions

- **Scope:** MST's `_make_mst_scores` marginal discrepancy norm, and downstream `_make_mst_select` edge selection using those scores. Compare with AIM's `_make_aim_scores` as a sibling of the same type of scoring. [Reviewed upstream file at 7acfb2cdcee7d39fc26a6ade7edac15249c52f4b](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_mst/__init__.py).
- **Invariant:** For each two-way count table, score error by cellwise L1 discrepancy, i.e. sum of absolute residuals across **all cells**; the resulting scalar sensitivity must not exceed the advertised bound `max(d_in[query][1])`. Selection should not substitute a matrix operator norm for this objective.
- **Assumptions:** All model projections and exact marginals are finite and share the same two-dimensional shapes; the input `TypedDictDistance` is backed by sound `make_stable_marginals` certificates. Only a direct, isolated NumPy score test was executed, not a full MBI pipeline or the upstream compiled OpenDP library.
- **Coordination:** [Audit task #116](https://github.com/opendp/opendp-audit/issues/116), [new correctness issue #117](https://github.com/opendp/opendp-audit/issues/117), [previous, distinct upstream #2951](https://github.com/opendp/opendp/issues/2951).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `_make_mst_scores.score_query` | correctness/cellwise-l1-objective | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Reproduced selection inversion](#reproduced-selection-inversion); [issue #117](https://github.com/opendp/opendp-audit/issues/117) |
| `_make_mst_scores` | privacy/score-l1-sensitivity | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Numerical privacy counterexample](#numerical-privacy-counterexample); [native verification](../../../../../../../investigations/mbi-mst-score-rounding-privacy.md) and [issue #135](https://github.com/opendp/opendp-audit/issues/135). |
| `_make_mst_select` | correctness/score-selection-propagation | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Selection path](#selection-path) |

## Analysis

### Reproduced selection inversion

The current score function at [lines 321–323](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_mst/__init__.py#L321-L323) computes `float(np.linalg.norm(exact - synth, 1))`. For an `m×n` matrix, `np.linalg.norm(A, 1)` is the **induced matrix 1-norm** `max_j sum_i abs(A_ij)`, not the intended entrywise `sum_i sum_j abs(A_ij)`. The source [`make_stable_marginals`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_utilities/__init__.py) constructs **two-dimensional** arrays for pairwise cliques, so NumPy uses the matrix norm. By contrast [AIM's `_make_aim_scores`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_aim/__init__.py#L424-L439) explicitly flattens each residual array before computing its L1 norm.

The following Python/NumPy example **was executed** in the audit environment:

```python
import numpy as np
synth = np.full((2, 2), 10.0)
exact_ab = np.array([[16., 4.], [4., 16.]])
exact_cd = np.array([[18., 10.], [2., 10.]])
for name, exact in [("AB", exact_ab), ("CD", exact_cd)]:
    resid = exact - synth
    print(name, exact.sum(), np.linalg.norm(resid, 1), np.linalg.norm(resid.ravel(), 1))
```

Observed exact output:

```text
AB 40.0 12.0 24.0
CD 40.0 16.0 16.0
```

The two exact marginals and both model projections have the same total count (40). Under the intended elementwise L1 objective AB has greater discrepancy (24 > 16), but the implemented matrix 1-norm ranks CD above AB (16 > 12). This demonstrates a concrete ranking reversal at the level of the exact scoring expression. It does **not** claim an end-to-end run of the randomized MST mechanism.

### Sensitivity comparison

The current `stability_map` on line 333 is `max(distance[1] for distance in d_in.values())`, based on marginal **cellwise L1** distance. The induced matrix norm obeys `abs(||A||_1 - ||B||_1) <= ||A - B||_{matrix,1} <= ||A - B||_{entrywise,1}`. Thus for the finite tables under the stated input-domain assumptions, this norm substitution does **not** underestimate sensitivity; the stability map can remain conservative. This review does not establish independent correctness of `make_stable_marginals`, `TypedDictDistance`, the FFI callback, or all numerical corner cases, so status is **Partial** rather than a general privacy guarantee.

The earlier [upstream #2951](https://github.com/opendp/opendp/issues/2951) concerns an L2-vs-L1 metric certificate and was closed. It is not this matrix-vs-entrywise objective error.

### Numerical privacy counterexample

The **real-arithmetic** induced-matrix-L1 inequality above does not certify the actual **binary64** scorer. Subtracting an extremely large but finite public synthetic projection and then applying `np.linalg.norm` can amplify a one-count change by a full representable-spacing step. For three binary columns with consistent public MBI model total about `2**55`, the two adjacent pairwise tables each differ by entrywise L1 1; the actual compiled `_make_mst_scores` returns a score vector difference `[-8,0,0]`. The map still certifies 1. The 3-candidate permute-and-flip event ratio is `exp(8/scale)` for the inferior candidate, and at `scale=4` the event log ratio is `2 > advertised epsilon 0.5`.

**Native verification:** [Successful CI](https://github.com/opendp/opendp-audit/actions/runs/45254507499) tested the real OpenDP nightly `_make_mst_scores` and `_make_mst_select` with a self-consistent `mbi.MarkovRandomField`; MBI computed public projections through variable elimination from finite log-potentials. The scorer and actual selector both accepted the inputs, returned/used real scores, and certified `epsilon=0.5`. See [detailed investigation](../../../../../../../investigations/mbi-mst-score-rounding-privacy.md) and [issue #135](https://github.com/opendp/opendp-audit/issues/135). No complete `make_contingency_table` estimator/release workflow was run. This is **separate** from the matrix-vs-cellwise-L1 utility problem #117.

### Selection path

The `_make_mst_select` procedure [lines 231–297](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/mbi/_mst/__init__.py#L231-L297) instantiates `t_mst_scores`, subsets candidate scores to currently unconnected edges, and calls `make_noisy_max` on those scores, then records the selected edge. Therefore the wrong score vector directly changes randomized edge selection preferences, potentially worsening the graphical model's fit. Noise introduces randomness, so the example demonstrates an inverted *scoring preference*, not a deterministic end-to-end selected-edge outcome.

## Findings and next checks

**Reproduced correctness/utility defect** [#117](https://github.com/opendp/opendp-audit/issues/117); **upstream disposition: Unreported** based on open/closed issue and PR searches. Replace the scoring expression with `float(np.linalg.norm((exact - synth).ravel(), 1))` (or `float(np.abs(exact - synth).sum())`) and add a native MBI regression that checks ranking over distinct 2×2 marginals. Verify the resulting score domain and privacy map once more after any source change.

**Executed:** isolated Python/NumPy arithmetic witness with two 2×2 tables of equal total. **Not executed:** OpenDP/Polars/MBI end-to-end workflow and native library. The existing prior issue #2951 is related in area but distinct in root cause and correction.
