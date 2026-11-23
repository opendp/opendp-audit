---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Private candidate selection uses geometric scale as rate

## Invariant and threat model

For public `stop_probability = p` between zero and one and a valid, constantly below-threshold scorer, the algorithm must return `None` after a shifted geometric number of calls, with `Pr[N=1]=p`. Misparameterization changes selection utility, runtime, and distribution of the public `Option` result.

## Affected symbols and source audits

- [Selector source audit](../source/rust/src/combinators/select_private_candidate/mod.rs.md), `make_select_private_candidate` under `correctness/stopping-distribution` and `privacy/selection-bound`.
- [Selector code](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/select_private_candidate/mod.rs), including `scale = -1 / ln(1-p)` and `sample_geometric_exp_fast(scale)`.
- [CKS20 sampler code](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/cks20/mod.rs) and [formal proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/cks20/sample_geometric_exp_fast.tex), which specify `Geometric(1-exp(-x))` for **rate** `x`.
- [Selector proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/select_private_candidate/make_select_private_candidate.tex) and [pseudocode](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/select_private_candidate/pseudocode/make_select_private_candidate.py), which repeat the inconsistent reciprocal.

## Reasoning and evidence

1. The selector computes an approximation to `s=-1/ln(1-p)`; it does not invert the value before calling the sampler.
2. The geometric sampler returns a nonnegative `G` with `Pr[G=0] = 1-exp(-s)`. The selector uses `N=G+1`, so `Pr[N=1]=1-exp(-s)` instead of `p`. The required sampler argument is instead approximately `-ln(1-p)`.
3. At `p=0.01` the first-iteration stopping probability is virtually `1`. At `p=0.50` it is `0.763709911655`; at `p=0.90` it is `0.352278514858`. Independent Python standard-library computations of the formulas were executed. No OpenDP Rust binary or sample-based regression was executed.
4. The `p=0` branch is handled separately and is unaffected. The generic `2ε` selection bound may still apply because the actual stopping distribution is a geometric distribution with a different public parameter; an independent proof was not completed.

### Finite privacy-model checks

A reproducible [standard-library Python test](../tools/tests/test_select_private_candidate_model.py) was added. For a base scorer with probabilities `(a,b,c)` for two qualifying outcomes and one below-threshold outcome, write `q=a+b` and let `r` be its actual public per-failure stop probability. For `r+(1-r)q>0`, the output law is

- `P(A)=a/[r+(1-r)q]`
- `P(B)=b/[r+(1-r)q]`
- `P(None)=r*c/[r+(1-r)q]`

The test enumerates the 55 strictly positive three-outcome rational distributions with denominator 12, compares every directed pair (55²), and repeats for `r in {0, 1/100, 1/10, 1/2, 9/10}` (15,125 pairs). It verifies by `fractions.Fraction` that each output likelihood ratio in either direction does not exceed the square of the maximum base likelihood ratio. It also checks the mismatched numerical rates and the `p=0`, never-qualifying nontermination case. This is an **independent idealized model**, not native OpenDP execution, and is not a general privacy proof. No finite counterexample to the factor-two bound was found.

## Findings

**Confirmed source-level correctness mismatch on upstream `main`, without an executed OpenDP reproduction.** The documented per-iteration stopping probability differs from the realized probability. Impact: selection behavior, utility, and runtime; **no privacy violation is claimed**. **Upstream disposition: Pending PR.** [OpenDP PR #2657](https://github.com/opendp/opendp/pull/2657) is open, draft, and unmerged. Its legacy-constructor patch replaces the reciprocal logarithm with `-ln_1p(-stop_probability)` and adds a regression for `p=0.01`. That patch addresses the reported mismatch in the PR branch, but is **not yet on `main`**. Our prior search incorrectly reported no existing corrective PR. No new issue or PR was opened under the user's restrictions.

## Unresolved questions

- Track [PR #2657](https://github.com/opendp/opendp/pull/2657) through merge and independently test its proposed `-ln_1p(-p)` rate conversion, including floating-point extreme `p` boundaries and the legacy constructor's stochastic semantics.
- Recheck the upstream source and relevant proof documentation after merge; run compiled Rust regressions for representative and extreme `p` values.
- Check all child scorer failure paths and the full applicability of the private-selection `2ε` theorem.
