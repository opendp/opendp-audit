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

## Findings

**Confirmed source-level correctness mismatch, without an executed OpenDP reproduction.** The parameter documented as the per-iteration early stopping probability is not the probability realized by the implementation. The impact is selection behavior, utility, and runtime; **no privacy violation is claimed**. Searches of the audit repository and upstream issues/PRs by symbol, stopping parameter, and geometric-selection terms did not reveal an equivalent tracked fix. No issue or PR was opened under current user restrictions.

## Unresolved questions

- Decide whether to honor the exact dyadic-rational input probability using repeated Bernoulli draws or to document a conservatively rounded geometric-rate approximation.
- Correct the implementation, proof pseudocode, and documentation together; run compiled Rust regressions for representative and extreme `p` values.
- Check all child scorer failure paths and the full applicability of the private-selection `2ε` theorem.
