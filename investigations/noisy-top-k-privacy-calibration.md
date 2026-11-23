---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Partial
---

# Noisy top-k: selection distributions and privacy-map calibration

## Invariant and threat model

For positive finite `scale` and any valid inputs of the same public vector length with `LInfDistance` bound `d`, the advertised output privacy map of `make_noisy_top_k` must upper-bound the divergence between **ordered** selected-index sequences. For a non-monotonic change, the per-score range sensitivity is bounded by `2d`; for a monotonic change it is bounded by `d`. The constructor charges `k` rounds of one-step privacy loss, even if fewer than `k` indices are available.

For `MaxDivergence`, the advertised bound is `epsilon = k * Delta_range / scale`. For `ZeroConcentratedDivergence`, the bound is `rho = k * (Delta_range / scale)^2 / 8`. The zCDP condition requires `D_alpha(P || Q) <= alpha * rho` for every `alpha > 1` in both input directions. These comparisons concern observable output indices, not timing, random-bit consumption, sampler errors, or untrusted public parameters.

## Affected symbols and source audits

- [Primary source audit](../source/rust/src/measurements/noisy_top_k/mod.rs.md)
- [`make_noisy_top_k` constructor, `TopKMeasure` implementations, `permute_and_flip`, and peeling](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noisy_top_k/mod.rs)
- [`LInfDistance` monotonic interpretation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/mod.rs)
- [Exact rational `sample_bernoulli_exp` contract](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/cks20/mod.rs)
- [Uniform integer sampler and contracts](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/uniform/mod.rs)
- [Constructor proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noisy_top_k/make_noisy_top_k.tex) and [existing tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noisy_top_k/test.rs)

## Reasoning and evidence

### Sampling and per-round composition

In both positive-scale branches, a candidate with score `s_i` is accepted with probability `w_i = exp((s_i - max(s)) / scale)`, by the `sample_bernoulli_exp` contract. Each `w_i` lies in `(0,1]` and at least one equals one.

When `replacement = false` (`MaxDivergence`), the proposal order is a random permutation: the Fisher-Yates step selects a remaining position uniformly. The resulting permute-and-flip single-step distribution assigns an index `i` the sum, over all permutations, of the probability of rejecting earlier candidates then accepting `i`. The acceptance of a maximum-score candidate with probability one ensures termination.

When `replacement = true` (`ZeroConcentratedDivergence`), proposals are drawn uniformly **with replacement**, and the loop repeats until accepted. Rejection sampling gives exactly `Pr[i] = w_i / sum_j w_j`, the exponential-mechanism/softmax distribution. The `replacement` flag only controls **proposal sampling** within one selection: `peel_permute_and_flip` removes the chosen score after each round in both cases. Thus the ordered top-k distribution is the product of conditional one-step distributions on successively smaller score sets, with original indices restored by the separate index-rebasing logic.

For score vectors `x, x'` with coordinate differences bounded by `d`, the range of the differences is at most `2d`; when all differences share a sign, at most `d`. The implementation uses outward-rounded `d.inf_add(d)` when `monotonic` is false, otherwise `d`, then converts it outward to `f64`. The per-round advertised pure-DP cost is `Delta_range / scale`; the per-round advertised zCDP cost is `(Delta_range / scale)^2 / 8`. The final outward multiplication by `k` is the standard conservative sequential-composition bound. The established one-round privacy theorems are external prerequisites to a proof over all inputs; they were not reproved in this audit.

The constructor rejects nonfinite/negative scales and `k > size` for fixed-size domains. For input distance zero, the map returns zero; for positive distance and zero scale, it returns infinity. With `k = 0` the positive-scale map is zero and the mechanism returns the empty selection. The zero-scale map for positive distance is infinite even when `k = 0`, which is conservative, not a privacy underestimation.

### Executed independent exhaustive probability model

A standard-library Python 3 model computed one-step probability mass functions in two independent ways: for permute-and-flip, summing the accept/reject probabilities across **every** permutation of candidate indices; for the exponential mechanism, normalizing the weights `w_i`. It recursively composed these one-step laws after removing each selected index, retaining the **ordered** output sequence.

All ordered pairs of equal-length vectors over the score alphabet `{-1,0,1}` with `L-infinity distance exactly 1` were considered, for lengths `n = 2, 3, 4`, `k = 1..n`, scales `0.5, 1.0, 2.0`, and both signs of the scores (maximize/minimize). Each pair was tested with the monotonic bound (`d`) when its coordinate differences were all of one sign, or the conservative bound (`2d`) otherwise.

- **Pure-DP:** 61,848 directional comparisons of `max_y ln(P(y)/Q(y))` against `k * Delta_range / scale`; **zero** overruns larger than `1e-10`.
- **zCDP:** 371,088 Rényi comparisons, at orders `alpha = 1.1, 1.5, 2, 4, 8, 16`, of `D_alpha(P||Q)` against `alpha * k * (Delta_range / scale)^2 / 8`; **zero** overruns larger than `1e-10`.
- Maximum observed positive pure-DP bound overrun from ordinary floating-point accumulation was `4.440892098500626e-16`; maximum ratio of sampled `D_alpha` to the claimed `alpha*rho` was approximately `0.9961387577`; maximum probability-mass normalization error was `4.440892098500626e-16`.

This is a **finite exact-enumeration algorithm using approximate floating-point probability arithmetic**; it is not a symbolic proof, not direct OpenDP Rust execution, and not a verification of every Rényi order or parameter value. No hidden distributional test is represented as a real Rust test.


### Extended numerical calibration model (subnormals and overflow)

A deterministic Python 3 independent reference model used `fractions.Fraction.from_float` to represent each accepted binary64 input exactly. Every positive finite arithmetic step was rounded upward to the nearest representable binary64 number by comparing `Fraction.from_float(float(ideal))` with the exact rational result and applying `math.nextafter(value, math.inf)` if nearest rounding fell below the ideal. Values whose upward result could not be represented as a finite binary64 number were classified as **reference-model errors**. This models the algebraic directed-rounding contracts; it does **not** execute or test OpenDP's `FBig` backend.

For each input `d >= 0`, `scale > 0`, `k >= 0`, monotonic flag, and measure, the model evaluated the same outward-rounded path as the constructor: `d` or `inf_add(d,d)`, `inf_div(d,scale)`, then (for zCDP) `inf_powi(ratio, 2)` and `inf_div(square, 8)`, followed by an upward cast of `k` and `inf_mul(result,k)`. For every successfully represented value it verified against a **separately computed exact rational bound**:

- Pure DP: `k * ((monotonic ? d : 2d) / scale)`.
- zCDP: `(k / 8) * ((monotonic ? d : 2d) / scale)^2`.

The deterministic tests covered:

- A **13,680-case Cartesian grid** with `d` drawn from zero and 18 positive edge values (smallest subnormal, nearby subnormals, minimum normal and adjacent values, powers of two spanning very small and very large magnitudes, `0.1`, `1`, and maximum finite binary64); `scale` from the 18 positive edge values; `k` from `{0,1,2,3,7,100,2^53-1,2^53,2^53+1,2^63-1}`; both monotonicity settings and both privacy measures. Outcomes: **10,429** representable bounds, **3,251** model arithmetic errors, **zero** representable underestimates.
- **30,000 deterministic pseudorandom samples** using Python `random.Random(20261122)` with positive finite numbers sampled across binary exponents from `-1022` through `1023`, plus small subnormal values and selected fixed edge values; `k` from `{0,1,2,3,7,100,2^53+1,2^63-1}`; both monotonicity settings and both measures. Outcomes: **22,869** representable bounds, **7,131** model arithmetic errors, **zero** representable underestimates.
- Within these tests, **875** random cases produced the smallest positive binary64 (`2^-1074`) via upward rounding where the exact positive ideal result lay below it. In particular, the model did not round a positive ideal privacy loss down to zero.

**Combined:** **43,680** parameter combinations; **33,298** representable conservative reference-model results; **10,382** model arithmetic errors; **zero** exact-rational underestimates. The reference model's error count is **not** a claim that Rust errors identically, since it was not executed. A bounded-float backend may fail for additional cases. By contract, an error means the map cannot certify that distance, not that its privacy cost is zero or infinite.

These tests do not analyze the exact distribution at extreme scales or guarantee arbitrary-precision rational conversion performance. The coverage remains **Partial** until the native backend is exercised and its directed-rounding contracts validated.

## Findings

**No privacy-map or selection-distribution defect identified in the enumerated scope.** Do not generalize this negative result to arbitrary score domains, infinitesimal or extreme positive scales, all `alpha > 1`, or runtime behavior. The existing audit record for index rebasing remains separate. No candidate-defect issue was created, and no new audit-task lease was claimed.

## Unresolved questions

- Execute the native OpenDP test suite and implement deterministic distributional regression tests where practical.
- Prove/calibrate the monotonic range-distance conversion and zCDP bound over all allowed score types and scales without relying on a finite test model; examine the directed-rounding arithmetic for extreme values.
- Clarify the valid `LInfDistance` adjacency interpretation for unsized vectors and any effect of observable vector length. The model held the length fixed.
- Re-review if sampler or privacy-map implementations change on upstream `main`.
