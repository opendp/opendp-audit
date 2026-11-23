---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# CKS20 discrete-Laplace normalization and fast geometric sampling

## Invariant and threat model

At any positive rational `scale=s`, the accepted discrete-Laplace output must have a nonnegative normalized PMF `[(1-q)/(1+q)] q^|x|` for `q=exp(-1/s)`. Its helper with positive rational `x` must produce `Geometric(1-exp(-x))`. An erroneous negative coefficient in public Rustdoc is a specification defect, not by itself evidence of a runtime distribution or differential privacy failure. Scale zero is an explicit point mass and must not use the positive-scale density.

## Affected symbols and source audits

- [CKS20 source audit](../source/rust/src/traits/samplers/cks20/mod.rs.md), including `sample_geometric_exp_fast`, `sample_discrete_laplace` and their documented mass.
- [Pinned Rust implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/cks20/mod.rs), [fast-geometric proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/cks20/sample_geometric_exp_fast.tex), and [Laplace proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/cks20/sample_discrete_laplace.tex).
- [Native Rust statistical test oracle](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/cks20/test/symmetric.rs); [independent mathematical model](../tools/tests/test_cks20_laplace_law_model.py).

## Reasoning and evidence

### Fast geometric law

For rational `x=n/d>0`, the proposal `U` is uniform on `0..d-1` and accepted with probability `exp(-u/d)`, so accepted `U` is proportional to `exp(-u/d)`. The independent `V` has law `Geometric(1-exp(-1))`. Thus `Z=dV+U` has mass `(1-exp(-1/d))exp(-z/d)`. Partitioning `Z` into groups of `n` gives returned `floor(Z/n)` mass `(1-exp(-n/d))exp(-kn/d)`.

The [test](../tools/tests/test_cks20_laplace_law_model.py) evaluates this decomposition for 32 selected cases with `x` in `{1/2,3/4,5/3,2}` and `k=0..7`; numerical comparisons pass to 13 decimal places. This tests an independent algebraic model, not native random draws.

### Discrete-Laplace law

Put `q=exp(-1/s)`. The sampler draws an independent fair sign and `Y~Geometric(1-q)`, rejecting the negative-sign/zero-magnitude pair. Acceptance is `(1+q)/2`. For zero, only the positive-sign outcome returns, while for nonzero signed values only one sign matches. The resulting PMF is `[(1-q)/(1+q)] q^|x|`, and

`[(1-q)/(1+q)] * [1 + 2q/(1-q)] = 1`.

The independent model checks 68 selected signed mass values for four rational scales and verifies nonnegativity, symmetry, and normalization. Positive scales approaching zero converge to the deterministic point mass; the Rust `scale=0` branch was inspected, not executed.

### Rustdoc discrepancy and disposition

The Rustdoc formula is `[(exp(-1/s)-1)/(exp(-1/s)+1)] exp(-|x|/s)`. Since `0<exp(-1/s)<1`, this is negative at **every positive scale**: e.g. at `s=1` it says `P[X=0]≈-0.462117`. The implementation, LaTeX proof and native test oracle all use the *positive* coefficient. The remaining documentation defect is filed as [audit #48](https://github.com/opendp/opendp-audit/issues/48), verification **Confirmed** and upstream disposition **Unreported**.

Upstream [issue #1133](https://github.com/opendp/opendp/issues/1133) and merged [PR #1134](https://github.com/opendp/opendp/pull/1134) corrected the LaTeX proof only. Open [PR #2116](https://github.com/opendp/opendp/pull/2116) does not modify the Rustdoc.

**Executed:** Four independent standard-library Python `unittest` model tests passed locally; commit-pinned Rust, proof, and native test sources were inspected. **Not executed:** compiled Rust/OpenDP, entropy draws, or privacy-neighbor distributions. The native implementation's full distribution law remains `Partial` pending primitive and integration verification.

## Findings

- **Confirmed low-severity documentation bug:** The displayed Laplace density is negative for all positive scales, tracked in [audit #48](https://github.com/opendp/opendp-audit/issues/48).
- **Negative result:** No implementation or privacy defect was identified in the bounded positive-scale analytical model. This does not generalize to arbitrary-precision entropy behavior or to the discrete-Gaussian sampler.

## Unresolved questions

Run the pinned Rust test suite and native entropy-error checks, update the Rustdoc and record a merged fix SHA, and review discrete-Gaussian rejection independently.
