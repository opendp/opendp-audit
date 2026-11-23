---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Audited
---

# Bernoulli floating-point sampler: subnormal bit indexing

## Invariant and threat model

For a caller-supplied binary floating-point probability `p∈[0,1]`, `sample_bernoulli_float` must return `true` with probability `p`. This audit analyzes the ideal output distribution conditioned on successful unbiased entropy, not the privacy map of any downstream measurement or execution timing.

## Affected symbols and source audits

- [Scoped sampler source coverage](../source/rust/src/traits/samplers/bernoulli/mod.rs.md).
- [Pinned Rust `sample_bernoulli_float` implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/bernoulli/mod.rs).
- [Pinned first-head index sampler](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/geometric/mod.rs).
- [Upstream issue #3251](https://github.com/opendp/opendp/issues/3251) and [draft fix PR #3257](https://github.com/opendp/opendp/pull/3257).

## Reasoning and evidence

Let `i` be the zero-based index of the first set bit in an unbiased sequence. Then `Pr[i=j] = 2^(-j-1)`. The sampler returns the bit at position `j` of its calculated binary expansion of `p`. Thus the exact success probability is `sum_j b_j 2^(-j-1)`.

For a positive **normal** floating-point input, `raw_exponent ≥ 1` and the implicit leading mantissa bit is present. The Rust `leading_zeros = EXPONENT_BIAS - 1 - raw_exponent` correctly places that bit at index `j` corresponding to its binary power. For **subnormals**, `raw_exponent = 0` means there is *no* implicit bit and the first mantissa bit should start one position earlier. The formula does not adjust for this and instead places every mantissa bit one place later, halving its contribution. Therefore every positive subnormal input has the exact idealized output law `Bernoulli(p/2)`.

At `f64` `p=2^-1023`, the intended success probability is `2^-1023` but the code implies `2^-1024`. The discrepancy is also true for `f32` subnormals, including their smallest positive representation.

### Executed finite exact model

The repository's [reproducible standard-library test](../tools/tests/test_bernoulli_float_subnormal_model.py) reconstructs `f32` and `f64` bit patterns with `struct`, exactly computes their represented numeric values via `Fraction.from_float`, and sums the code's selected binary digits using a common power-of-two denominator. The test assumes the sampler's documented ideal geometric first-head law; it never calls the OpenDP Rust library or simulates random trials.

Deterministic sample coverage (`random.Random(20261122)`):

- 262 positive subnormal bit patterns of each type (6 fixed boundary patterns and 256 pseudorandom mantissas): **524** exact equalities `Pr[true] = p/2`.
- 259 zero/normal bit patterns of each type (3 fixed and 256 pseudorandom patterns): **518** exact equalities `Pr[true] = p`.
- Largest subnormal and smallest normal of each type: **4** additional boundary equalities.

All **1,046** exact equalities passed locally under Python 3. **No compiled Rust, RNG, constant-time, or downstream privacy-map test was run.** The subnormal finding is also directly described in OpenDP's [upstream issue #3251](https://github.com/opendp/opendp/issues/3251).

## Findings

**Confirmed, already reported upstream:** `sample_bernoulli_float` places positive subnormal mantissa digits one index too late and samples `Bernoulli(p/2)`. It remains on upstream `main` at the pinned revision. The proposed fix [PR #3257](https://github.com/opendp/opendp/pull/3257) is open/draft, not merged. No duplicate audit issue was opened. The numerical distributional defect is established; a distinct mechanism-level privacy-accounting failure was not demonstrated in this scope.

## Unresolved questions

- Verify the upstream fix and run native compiled Rust boundary regressions after merge, including constant-time mode.
- Audit callers that supply subnormal probabilities against their stated privacy maps, without assuming a privacy violation from this sampler discrepancy alone.
