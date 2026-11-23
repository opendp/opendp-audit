---
schema_version: 1
source: rust/src/traits/samplers/cks20/mod.rs
updated: 2026-11-23
---

# `rust/src/traits/samplers/cks20/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated `sample_geometric_exp_fast` and `sample_discrete_laplace`, their exact distribution laws, zero-scale convention, and Rustdoc probability-mass expression. The Gaussian sampler is excluded.
- **Invariant:** For positive rational scale `s`, the signed geometric construction has probability `[(1-q)/(1+q)] q^|x|`, where `q=exp(-1/s)`. A probability-mass expression cannot be negative. For rational `x=n/d>0`, fast geometric output has mass `(1-exp(-x)) exp(-kx)`. For scale zero the Laplace sampler returns zero.
- **Assumptions:** Uniform and Bernoulli entropy primitives satisfy their specifications and use independent draws; all rational denominators are positive. Entropy failure, Gaussian rejection sampling, arbitrary precision extremes, and actual OpenDP Rust execution are excluded.
- **Upstream:** [Rust implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/cks20/mod.rs), [LaTeX Laplace proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/cks20/sample_discrete_laplace.tex), [geometric proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/cks20/sample_geometric_exp_fast.tex), [native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/cks20/test/symmetric.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `sample_geometric_exp_fast` | correctness/geometric-distribution | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Distribution trace](#distribution-trace) and [investigation](../../../../../../investigations/cks20-discrete-laplace-normalization.md) |
| `sample_discrete_laplace` | correctness/discrete-laplace-pmf | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Distribution trace](#distribution-trace) and [model tests](../../../../../../tools/tests/test_cks20_laplace_law_model.py) |
| `sample_discrete_laplace` | documentation/discrete-laplace-pmf | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Rustdoc mismatch](#rustdoc-mismatch) and [issue #48](https://github.com/opendp/opendp-audit/issues/48) |
| `sample_discrete_laplace` | correctness/zero-scale-sampling | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Zero scale](#zero-scale) |

## Analysis

### Distribution trace

Write the input of the fast geometric sampler as `x=n/d>0`. It selects `u` from `0..d-1` with probability proportional to `exp(-u/d)`, then independently selects `v` from `Geometric(1-exp(-1))`. The intermediate `z=d*v+u` has PMF `(1-exp(-1/d)) exp(-z/d)`; the returned `floor(z/n)` therefore has PMF `(1-exp(-n/d)) exp(-kn/d)`. The independent [model](../../../../../../tools/tests/test_cks20_laplace_law_model.py) tests 32 combinations of `x` in `{1/2, 3/4, 5/3, 2}` and `k=0..7`.

For discrete Laplace with `scale=s>0`, put `q=exp(-1/s)`. The magnitude has geometric mass `(1-q)q^y`, and an independent fair sign is rejected only when sign is negative and magnitude zero. The acceptance probability is `(1+q)/2`; consequently the output has PMF `[(1-q)/(1+q)] q^|x|`. The model checks 68 signed masses across `s` in `{1/2,1,2,3}` and `x=-8..8`, and full normalization. These are algebraic source models, not native OpenDP sampling runs.

### Rustdoc mismatch

The Rustdoc instead writes `(exp(-1/s)-1)/(exp(-1/s)+1)`, which is **negative for every positive s**; at `s=1` its supposed `P[X=0]` is about `-0.462117`. The corrected LaTeX proof and native Rust test oracle use `(1-exp(-1/s))/(1+exp(-1/s))`, matching the actual rejection logic. This is a **confirmed documentation defect**, not evidence of a sampler/privacy defect. See [audit #48](https://github.com/opendp/opendp-audit/issues/48).

Historical upstream [#1133](https://github.com/opendp/opendp/issues/1133) was fixed by merged [#1134](https://github.com/opendp/opendp/pull/1134), but that patch edited only the proof. Open review [PR #2116](https://github.com/opendp/opendp/pull/2116) edits proof/pseudocode, not the Rustdoc.

### Zero scale

`sample_discrete_laplace` directly returns `Ok(0)` for scale zero, before reciprocal conversion. The positive-scale law tends to that point mass as scale decreases; the model checks this limit, **not** the native zero branch. The upstream Rust test explicitly exercises that branch.

**Verification:** Four standard-library Python model tests passed locally, and the pinned implementation, proof and native tests were inspected. The native Rust sampler suite was not executed; `Partial` for the distribution laws reflects unverified primitive contracts and extreme inputs.

## Next checks

Run the native Rust sampler tests, confirm entropy error propagation and extreme-rational behavior, and fix the Rustdoc coefficient without applying the positive-scale law at scale zero. Audit discrete Gaussian separately.
