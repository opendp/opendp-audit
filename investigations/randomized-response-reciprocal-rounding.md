---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Partial
---

# Categorical randomized response: reciprocal boundary and privacy calibration

## Invariant and threat model

For the categorical `make_randomized_response` measurement, every accepted `prob` must yield `map(1)` greater than or equal to the true max-divergence of outputs on any distinct inputs in its `AtomDomain<T>`. Under `DiscreteDistance`, distinct input atoms are distance one. An event revealing a difference between the two output distributions refutes an advertised zero privacy loss.

The specific scope is the accepted minimum probability when the number of categories is three. Assume ideal uniform and Bernoulli samplers conditional on successful entropy generation, as specified by their upstream contracts. No timing or entropy-source adversary is considered.

## Affected symbols and source audits

- [Source coverage: `make_randomized_response`](../source/rust/src/measurements/randomized_response/mod.rs.md)
- [Constructor and privacy map, reviewed `main` SHA](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/randomized_response/mod.rs): the lower bound uses `num_categories.recip()` and the map uses `inf_div`, `inf_mul`, and `inf_ln` on `prob / (1 - prob) * (t - 1)`.
- [Directed rounding definitions and implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/arithmetic/mod.rs), [Bernoulli sampler](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/bernoulli/mod.rs), [uniform integer sampler](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/uniform/mod.rs), and [discrete metric](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/mod.rs).
- [Draft upstream PR #3257](https://github.com/opendp/opendp/pull/3257), inspected at head `849aa1c889f2cf7dd5e17e20b3e30a213e96709d`, modifies the same constructor and adds a three-category boundary regression.

## Reasoning and evidence

1. Choose `categories = {0_u8, 1, 2}`, `prob = 1.0_f64 / 3.0_f64`, and two neighboring inputs `x = 0`, `x' = 1`. The constructor accepts `prob` because it exactly equals the floating-point lower bound `3.0_f64.recip()`.
2. The accepted binary64 parameter is exactly `p = 6004799503160661 / 18014398509481984`, **less** than mathematical `1/3`. For outputs in the category set, the probability of the true category is `p`; each of the two false categories has probability `q = (1 - p) / 2 = 12009599006321323 / 36028797018963968`.
3. For output event `{1}`, `Pr[M(0) = 1] = q` and `Pr[M(1) = 1] = p`. Their ratio is exactly `q/p = 12009599006321323 / 12009599006321322`, greater than one. Hence the event gives a lower bound on max-divergence of `ln(q/p) = 8.326672684688674...e-17 > 0`.
4. The privacy constant follows the opposite, assumed nonnegative odds `p/q`: directed subtraction rounds `1 - p` **down** to `0.6666666666666666 = 2p`; directed division yields the exactly representable `0.5`; multiplication by `(3 - 1)` yields exactly `1.0`; `inf_ln(1.0)` is zero. The map therefore reports zero for `d_in = 1`, contrary to step 3. Outward rounding of the wrong likelihood ratio cannot repair the reversed inequality.

A Python 3.13 standard-library exact-rational check was executed locally and passed. It checked the accepted parameter, the exact odds ratio, and the sequence of representable directed-rounded intermediate values. The essential assertions are:

```python
from fractions import Fraction
p = Fraction(1.0 / 3.0)
q = (1 - p) / 2
assert p < Fraction(1, 3)
assert q / p == Fraction(12009599006321323, 12009599006321322)
assert (1.0 - float(p)) == 0.6666666666666667  # ordinary nearest rounding
assert float(p) / 0.6666666666666666 == 0.5  # directed-down denominator
assert (0.5 * 2.0) == 1.0
```

This is **analytical reproduction of the distributional contradiction**, not a run of OpenDP's Rust implementation. The reviewed sampler code and contracts support the model for this ordinary, non-subnormal `prob`. The separate [upstream issue #3251](https://github.com/opendp/opendp/issues/3251) concerns a subnormal Bernoulli probability and does not explain this `p ≈ 1/3` example.

## Findings

**Numerical privacy-accounting discrepancy on upstream `main`; pending upstream fix.** Severity: **low in absolute leakage**, but it breaks an exact epsilon-zero privacy claim under the stated sampler contracts. The issue is already covered by draft [PR #3257](https://github.com/opendp/opendp/pull/3257), which detects the floating-point reciprocal boundary, takes a direct uniform-draw path, and adds the three-category regression test. The PR is **open and unmerged** as of this audit; the fix is not present on the reviewed `main` revision.

Existing upstream [issue #2065](https://github.com/opendp/opendp/issues/2065) and [PR #2110](https://github.com/opendp/opendp/pull/2110) concern review of the mechanism. [Issue #2930](https://github.com/opendp/opendp/issues/2930) concerns bit-vector randomized response, not this boundary. No new defect issue was created. Work was not exclusively claimed because audit-task issue creation is outside the user's allowed GitHub actions.

## Unresolved questions

- Run an actual Rust assertion against upstream `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` to confirm the calculated zero map result, since the runtime and `dashu` arithmetic backend were not executed locally.
- After PR #3257 or a successor is merged, verify that the production sampler and privacy map agree for the boundary and adjacent representable probabilities, rather than treating a draft's regression as a shipped fix.
- Audit other values of `t` and other branches separately; this investigation establishes a counterexample, not comprehensive privacy coverage.
