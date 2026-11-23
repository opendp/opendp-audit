---
schema_version: 1
source: rust/src/measurements/noise/nature/float/utilities/mod.rs
updated: 2026-11-22
---

# `rust/src/measurements/noise/nature/float/utilities/mod.rs`

## Scope and assumptions

- **Scope:** Utilities used by `FloatExpFamily<2>`: dyadic grid index rounding, minimum float lattice step, L2 rounding allowance, and noise-scale integerization. The review excludes `P=1` and unbounded-resource execution at extreme `k` values.
- **Invariant:** Rounding to a grid of width `h=2^k` is nearest-integer with ties toward positive infinity; for floats on a lattice of width `g=2^k_min`, the coordinate distance increase is at most `h-g`, and the L2 vector increase at most `sqrt(n)(h-g)`. Exact finite input scale `σ` is converted to the rational `σ/h`.
- **Assumptions:** Rust signed integer shifts and `IBig` arithmetic satisfy documented semantics, and `InfCast` and `InfSqrt` provide upward bounds or errors. The executed Python model does not invoke Rust.
- **Reviewed upstream:** `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`; [implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/float/utilities/mod.rs), [unit tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/float/utilities/test.rs), [rounding proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/float/utilities/get_rounding_distance.tex).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::noise::nature::float::utilities::find_nearest_multiple_of_2k` | correctness/tie-breaking | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Round-to-grid analysis](#round-to-grid-analysis) |
| `measurements::noise::nature::float::utilities::get_rounding_distance` | privacy/l2-rounding-allowance | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Bound and finite model](../../../../../../../../investigations/gaussian-float-rounding-sensitivity.md) |
| `measurements::noise::nature::float::utilities::get_min_k` | correctness/minimum-dyadic-granularity | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Minimum-grid and scale analysis](#minimum-grid-and-scale-analysis) |
| `measurements::noise::nature::float::utilities::integerize_scale` | correctness/exact-scale-integerization | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Minimum-grid and scale analysis](#minimum-grid-and-scale-analysis) |

## Analysis

### Round-to-grid analysis

For rational `x/2^k = a/b`, `b>0`, the implementation evaluates `(floor(2a/b)+1)>>1`. Rust's signed big-integer right shift rounds toward negative infinity, so this expression equals `floor(a/b+1/2)`. Thus it selects the nearest integer, resolving exact half-integer ties toward **positive infinity** (including negative examples such as `-1.5 -> -1`). The upstream tests check both positive and negative tie cases. The independently executed Python rational model checked 729 dyadic inputs against the equivalent nearest-integer formula; all passed.

The `get_rounding_distance` source comment and its proof describe ties as “rounding down,” which does not match the index function or its tests. This is a **documentation inconsistency**, not by itself a stability-bound failure; the `h-g` bound holds for either deterministic tie rule.

### Minimum-grid and scale analysis

The smallest positive representable subnormal spacing of `f64` is `2^-1074` and of `f32` is `2^-149`; `get_min_k` computes these exponents from float traits. `get_rounding_distance` rejects `k<k_min`, returns zero if `k=k_min`, and requires a known size if `k>k_min`. For `P=2`, it computes `(2^k-2^k_min)*upper_bound_sqrt(size)`, where the intermediate cast and square root advertise conservative upward results.

`integerize_scale` rejects `k=i32::MIN` before negation, and converts finite `f64` scale to `RBig` exactly before multiplying by `2^-k`. Nonfinite scales fail at conversion; a *negative finite* scale remains negative here but is rejected later by the discrete-Gaussian privacy-map constructor. These helpers alone do not establish distributional correctness.

### Executed independent evidence

The [small-grid model](../../../../../../../../tools/tests/test_float_gaussian_rounding_model.py) exhaustively checked **2,461,004** vector-pair inequalities for dimensions 1, 2, and 3 with grid multipliers `1,2,4,8`. The test uses a miniature dyadic lattice and ordinary Python square roots, rather than the full finite `f32/f64` space or compiled Rust. No counterexample was found; L2 privacy coverage remains **Partial** pending actual runtime and directed-rounding verification.

## Next checks

- Run upstream Rust tests and add property tests for IEEE-754 boundary values, including tie-adjacent floats and subnormals.
- Verify directed rounding of the `sqrt(n)` multiplier and all rational-to-float conversions at extreme sizes and scales.
- Correct tie-language in the source comment/proof; no new issue or pull request was opened in this audit.
