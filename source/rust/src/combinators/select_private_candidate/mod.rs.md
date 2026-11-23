---
schema_version: 1
source: rust/src/combinators/select_private_candidate/mod.rs
updated: 2026-11-23
---

# `rust/src/combinators/select_private_candidate/mod.rs`

## Scope and assumptions

- **Scope:** Early-stop probability in `make_select_private_candidate`, traced through the geometric sampler, plus a limited assessment of the privacy map.
- **Invariant:** With public `p = stop_probability` in `(0,1)`, and a valid scorer that always returns a score below the public threshold, the number of scorer calls `N` before `None` must satisfy `Pr[N=1] = p` and `Pr[N>n] = (1-p)^n`. For `p=0` there must be no randomized early termination.
- **Assumptions:** The scorer returns successfully and is always below threshold; the geometric sampler obeys its specified distribution and draws independent randomness. This isolates the early-stop behavior from threshold success and fallible mechanisms.
- **Pinned upstream:** [Selector](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/select_private_candidate/mod.rs), [sampler](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/cks20/mod.rs), [sampler proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/cks20/sample_geometric_exp_fast.tex), [selector proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/select_private_candidate/make_select_private_candidate.tex).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_select_private_candidate` | correctness/stopping-distribution | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Counterexample](#counterexample); [investigation](../../../../../investigations/private-candidate-geometric-rate.md) |
| `make_select_private_candidate` | privacy/selection-bound | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Privacy impact](#privacy-impact) |

## Analysis

### Counterexample

For accepted `p>0`, the code computes `ln_cp = 1.0.neg_inf_sub(&p)?.inf_ln()?`, then constructs `scale = -1 / ln_cp` and passes that value directly to `sample_geometric_exp_fast(scale)`. The sampler contract specifies a zero-based geometric random variable `G` with success/stopping probability `q = 1 - exp(-x)` for input **rate** `x`. The selector uses `N=G+1`; therefore its actual first-iteration stopping probability is approximately `q = 1 - exp(1/ln(1-p))`, not `p`. A correct sampler rate would be `x = -ln(1-p)` (subject to finite-precision rounding), **not its reciprocal**.

Source-level numerical counterexamples using real arithmetic (the directed-rounding operations affect only low-order bits for these inputs):

| Requested `p` | Code's computed `scale` | Actual `Pr[N=1]` |
| --- | ---: | ---: |
| 0.01 | 99.4991624734 | almost 1 (failure probability approximately 6.1e-44) |
| 0.50 | 1.44269504089 | 0.763709911655 |
| 0.90 | 0.434294481903 | 0.352278514858 |

At `p=0.01`, when scores never exceed the threshold, the intended expected call count is `100` but the implemented expected count is approximately `1`. At `p=0`, the code skips the sampler and does not randomly stop, as intended. The [selector proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/select_private_candidate/make_select_private_candidate.tex) and its pseudocode repeat the reciprocal argument, so their claimed equivalence with the intended stopping distribution does not follow from the sampled geometric distribution.

**Evidence type:** Static inspection of the pinned Rust selector, sampler, and proof documents; independent numerical checks executed in Python using `math.log1p` and `math.expm1`. No compiled upstream Rust regression was run. The distributional counterexample is conditional on the sampler's documented postcondition. See [investigation](../../../../../investigations/private-candidate-geometric-rate.md).

### Privacy impact

The privacy map computes twice the child epsilon using `inf_mul(&2.0)`. The realized iteration count remains an independently sampled shifted geometric distribution, albeit for a **different** public stopping probability. The private-selection theorem used in the upstream proof gives a `2ε` bound independent of that positive probability. This points to a correctness/utility failure rather than a demonstrated privacy breach. A full verification of the selection theorem, finite-precision operations, and all child error paths was not performed: privacy coverage is `Partial`.

### Independent finite privacy check

An independent, exact-rational [reference model](../../../../../tools/tests/test_select_private_candidate_model.py) analytically tests the retained early-stop distribution's factor-two privacy claim. It checks 15,125 directed pairs of full-support three-outcome scorer distributions across five stopping probabilities; each output likelihood ratio stays within the square of the base likelihood-ratio bound. These checks do **not** execute Rust or resolve the confirmed stopping-rate mismatch. They support keeping the privacy assessment **Partial**, not classifying the mismatch as a demonstrated privacy undercount.

### Upstream disposition: Pending PR

[OpenDP PR #2657](https://github.com/opendp/opendp/pull/2657) is an **open draft, unmerged** proposed fix for this exact rate/scale mismatch. Its change to the legacy `make_select_private_candidate` constructor replaces `-1/ln(1-p)` with `-ln1p(-p)`, passed as the geometric sampler's rate, and includes `test_private_selection_legacy_stopping_probability` with a consistently below-threshold scorer at `p=0.01`. The PR also introduces `make_select_above_threshold` and deprecates the legacy constructor. The fix is **pending**, not present in the pinned upstream `main` revision; the PR's tests and numerical edge cases have not been independently executed or verified in this audit. The previous search incorrectly reported that no corrective PR existed.

## Next checks

- Recheck [PR #2657](https://github.com/opendp/opendp/pull/2657) after merge; re-review the modified legacy constructor and its numerical edge cases, especially small positive and near-one `p`.
- Execute upstream compiled Rust regressions, including the PR's deterministic repeated-scorer test and additional stopping-rate checks for `p=0.5` and `0.9`.
- Check proof-document correspondence for the legacy constructor and independently review privacy assumptions for fallible child mechanisms.

No GitHub issue or PR was created, following the user's restrictions.
