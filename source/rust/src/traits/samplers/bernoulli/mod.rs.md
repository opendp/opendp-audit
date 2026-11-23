---
schema_version: 1
source: rust/src/traits/samplers/bernoulli/mod.rs
updated: 2026-11-22
---

# `rust/src/traits/samplers/bernoulli/mod.rs`

## Scope and assumptions

- **Scope:** The probability mass assigned by `sample_bernoulli_float<T>` to IEEE-754 normal versus subnormal `f32` and `f64` inputs. This is a narrowly scoped distributional audit, not a general audit of entropy failure or constant-time guarantees.
- **Invariant:** For every public probability `p` in `[0,1]`, a successful call returns `true` with probability exactly `p`.
- **Assumptions:** `sample_geometric_buffer` returns the index `i` of the first unbiased set bit with probability `2^(-i-1)`, or `None` when all buffer bits are zero. `T::raw_exponent` and `T::to_bits` follow the declared binary IEEE-754 representation. The finite exact model does not execute the Rust implementation.
- **Pinned sources:** [Bernoulli sampler](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/bernoulli/mod.rs), [geometric first-head sampler](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/geometric/mod.rs), [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/bernoulli/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `traits::samplers::bernoulli::sample_bernoulli_float` | distribution/subnormal-bit-index | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Independent exact model](../../../../../../investigations/bernoulli-float-subnormal-indexing.md); [upstream issue #3251](https://github.com/opendp/opendp/issues/3251) |
| `traits::samplers::bernoulli::sample_bernoulli_float` | distribution/normal-bit-index | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Finite exact-normal checks](../../../../../../investigations/bernoulli-float-subnormal-indexing.md) |

## Analysis

The Rust algorithm samples a geometric first-head index `i` and returns binary digit `b_i` from `p`, yielding `Pr[true] = sum_i b_i / 2^(i+1)`. It computes `leading_zeros = EXPONENT_BIAS - 1 - raw_exponent`. For a normal float (`raw_exponent >= 1`) it correctly accounts for the implicit leading mantissa bit. For a positive **subnormal** (`raw_exponent = 0`), the implicit bit is absent, but the mantissa digits are incorrectly positioned one place to the right. Hence every subnormal nonzero bit contributes half its correct probability: **`Pr[true] = p/2`, not `p`**. The `constant_time` flag changes how `i` is sampled but not the erroneous digit selection, so both modes are affected.

A [dependency-free Python exact-dyadic test](../../../../../../tools/tests/test_bernoulli_float_subnormal_model.py) reconstructed the precise bit selection from the pinned Rust source and summed geometric-index probabilities using `fractions.Fraction`. It performed **1,046 exact comparisons**: 524 nonzero subnormal samples, 518 zero/normal samples, and four boundary-transition samples. All passed the analytic law above. The model was executed locally under Python 3; **no native OpenDP Rust sampling or random-bit experiments were executed**.

**Disposition:** This is a confirmed, **already reported upstream** distribution defect, [OpenDP #3251](https://github.com/opendp/opendp/issues/3251); open draft [PR #3257](https://github.com/opendp/opendp/pull/3257) proposes a fix but is **not merged** into the reviewed `main`. Do not open a duplicate audit issue for the same subnormal probability error. The issue's possible privacy implications depend on which measurements use such probabilities; no separate end-to-end privacy counterexample is claimed here.

## Next checks

- Execute upstream compiled Rust tests for the minimum normal, maximum subnormal, and subnormal `p=2^-1023` (`f64`), after the upstream fix merges.
- Verify the exact merged fix's subnormal exponent positioning and avoid extrapolating this independently modeled law to malformed, NaN, or out-of-range probabilities.
- If a caller derives its privacy map from the requested probability but receives a subnormal probability, audit whether the halving creates a concrete privacy loss beyond the advertised bound; record a distinct counterexample only if proven and not already covered upstream.
