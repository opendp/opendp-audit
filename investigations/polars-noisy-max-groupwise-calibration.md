---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Polars noisy_max: one-row selection and L0 privacy composition

## Invariant and threat model

The non-deprecated Polars `noisy_max` expression releases one index per fixed-width score array, under an input metric with `L0` component `l0` (number of changed row arrays) and `L-infinity` component `li` (maximum per-coordinate score change). With public positive scale and valid numeric arrays, the declared output privacy loss must bound the divergence of up to `l0` changed index releases. This audit considers two legal one-row measures: `MaxDivergence` and `ZeroConcentratedDivergence`. It does not treat row length as private or verify composition for arbitrary dynamic query plans.

## Affected symbols and source audits

- [Polars noisy-max source coverage](../source/rust/src/measurements/make_private_expr/expr_noisy_max/mod.rs.md), with [pinned upstream code](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_noisy_max/mod.rs).
- [Top-k source audit](../source/rust/src/measurements/noisy_top_k/mod.rs.md), [top-k privacy investigation](noisy-top-k-privacy-calibration.md), and [scalar wrapper](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noisy_max/mod.rs).
- [Reproducible independent model](../tools/tests/test_polars_noisy_max_model.py); [existing upstream Polars tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_noisy_max/test.rs).

## Reasoning and evidence

### Source path and privacy bound

`make_expr_noisy_max` composes the stable input `t_prior` with `NoisyMaxPlugin` and a privacy map returned by `rnm_privacy_map<T,MO>`. For each score array, `rnm_privacy_map` builds `make_noisy_max` using a non-monotonic `LInfDistance::default()`, and the same `scale`, `negate` and output measure as the row plugin. The privacy map evaluates `meas.map(T::inf_cast(li)?)` and multiplies the result by `f64::inf_cast(l0)?.inf_mul(...)`. This conservatively rounds the numeric sensitivity into the score dtype before evaluating a top-1 map. Consequently for positive scale and ideal real-valued score sensitivity `li` the reference bound is:

- Pure DP: `epsilon = l0 * (2li / scale)`.
- zCDP: `rho = l0 * (2li / scale)^2 / 8`.

The actual map may be larger due to the conservative cast of `li` and outward floating-point rounding. Under independent per-row noise and fixed public index sets, sequential composition across affected rows gives a sum of privacy losses. Unchanged rows have identical output distributions and contribute zero; changing at most `l0` rows is therefore covered by multiplying the conservative worst per-row loss by `l0`.

For positive `scale` and score vector `s`, the selection score is `v_i = -s_i` for minimization and `v_i=s_i` otherwise. Let `w_i=exp((v_i-max_j(v_j))/scale)`. With `replacement=false` (pure DP), a uniformly random permutation is scanned and each candidate `i` is accepted independently with probability `w_i`; at least one maximum has `w_i=1`. With `replacement=true` (zCDP), proposals repeat with replacement until accepted, yielding the softmax `Pr[i] = w_i / sum_j w_j`. The flag is about **proposals within the round**, not allowing the same candidate to be selected multiple times; the Polars plugin always requests one index.

### Executed independent finite model

A standard-library Python 3 [test](../tools/tests/test_polars_noisy_max_model.py) independently reconstructs these one-row probability mass functions: it **exhausts all permutations** for the pure-DP branch and normalizes exponential weights for the zCDP branch. It checks the one-row selection distribution and product divergence for up to `l0=2` changed rows. With a repeated neighboring row pair, the output joint law is a tensor product, for which `D_alpha(P^{⊗l0} || Q^{⊗l0}) = l0 D_alpha(P||Q)` (and the same additivity for worst-case log-likelihood ratio). A separate test explicitly constructs the 9-atom two-row product PMF to check this algebraic identity.

Deterministic model grid: score-vector lengths `n=1,2,3,4`; scores drawn from `{-1,0,1}`; **all ordered pairs** with coordinatewise differences of at most 1; positive scales `0.5`, `1`, `2`; both maximization/minimization flags; both proposal distributions; `l0=1` or `2`; and Rényi orders `alpha=1.1,1.5,2,4,8,16`. All probabilities were computed with standard binary64 arithmetic, testing bounds with tolerance `1e-10`.

- **33,600** directional pure-DP bound comparisons; **zero** overruns.
- **201,600** zCDP Rényi-bound comparisons; **zero** overruns.
- Explicit two-row joint-divergence identity checks and an independent 81-score-vector zero-scale argmax/argmin model both passed.
- The test verifies probability normalization and index support in `0..n` for every modeled positive-scale row.

These are finite deterministic computations of an independent **probability model**, not OpenDP Rust execution, a source-equivalent compiler test, a proof for arbitrary values, or a timing analysis. The published model counts overlap previously tested top-k laws but add the Polars-specific `l0` multiplication and index-return contract.

## Findings

**Bounded negative result:** No undercount in groupwise privacy cost or out-of-range nonempty-row index was identified in the tested scope. Positive-scale privacy/composition coverage remains **Partial** pending the complete Polars planner, sensitivity derivation, native runtime, and floating-point boundaries. No new defect issue was opened; the work lease is [audit task #30](https://github.com/opendp/opendp-audit/issues/30).

## Unresolved questions

- Validate `approximate_c_stability` and the data/metric preconditions of arbitrary nontrivial stable expression composition.
- Run compiled Polars tests for nullable child arrays, both output measures, and extreme public widths, including whether a `usize` index above `u32::MAX` could be truncated by the output cast.
- Confirm extreme-scale directed f64 arithmetic without relying solely on this small-grid probability model.
