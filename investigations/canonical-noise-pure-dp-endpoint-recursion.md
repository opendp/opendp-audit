---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Canonical noise pure-DP endpoint recursion

## Invariant and threat model

For valid parameters, `make_canonical_noise` must either return a sample or a controlled, data-independent error on in-domain inputs; it must not perform unbounded recursion. The counterexample uses finite `epsilon=1, delta=0, d_in=1` and is an **availability / fallible-API concern**, not a demonstrated disclosure of private data.

## Affected symbols and source audits

- [`make_canonical_noise` and `approximate_to_tradeoff` source audit](../source/rust/src/measurements/canonical_noise/mod.rs.md)
- [`quantile_cnd` and `CanonicalRV::inverse_cdf` source audit](../source/rust/src/traits/samplers/psrn/canonical/mod.rs.md)
- [`PartialSample::value` implementation, upstream pinned commit](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/psrn/mod.rs)

## Reasoning and evidence

**Accepted parameters.** Construct `make_canonical_noise(AtomDomain::new_non_nan(), AbsoluteDistance::default(), 1.0, (1.0, 0.0))`. Positive finite epsilon, zero delta, and finite positive sensitivity satisfy the implementation guards. For `q = exp_down(1) > 1`, the tradeoff's fixed point `c=1/(1+q)` lies in `(0,1/2)`, and its evaluation `f(0) = max(1 - q*0, exp_up(-1), 0)` equals **one** exactly.

**Unbounded recurrence.** `quantile_cnd(u,f,c)` at `u=0<c` enters its lower recursive branch, `quantile_cnd(1-f(u),f,c)-1`. Since `f(0)=1`, the next argument is again zero. Similarly at `u=1>1-c`, the upper branch re-enters at `f(0)=1`. Both branches lack termination checks and require arithmetic after the recursive call, preventing tail-call elimination from providing a bound.

**Unavoidable invocation.** `PartialSample::new` initializes `randomness=0, refinements=0`. Its first `edge::<Down>()` computes uniform `u=(randomness+0)/2^refinements=0`. The `value()` loop calls `self.lower().zip(self.upper())` before random-bit refinement, so an accepted measurement invokes `quantile_cnd(0,...)` on its first release. The computation is independent of input data and never advances; typical Rust execution eventually exhausts the stack instead of returning a recoverable error. This latter process-level manifestation was reasoned about, **not observed** in a compiled OpenDP test.

**Independent test executed:** Python 3.13 standard-library `fractions.Fraction` was used with rationalized `exp(1)` to model the pure-DP tradeoff's exact recursive transition. Twenty-five consecutive steps starting at zero remained zero for `delta=0`. A `delta=1e-6` control advanced from zero into the interior. No OpenDP binary, FFI, or upstream Rust tests were executed.

**Existing fix and tests:** The upstream canonical-noise test only uses positive delta. [Draft PR #2859](https://github.com/opendp/opendp/pull/2859) modifies `quantile_cnd` with explicit `uniform=0` and `uniform=1` `None` returns and an iterative loop, directly addressing this fault. It is **open and unmerged**; this does not mean upstream `main` is fixed.

## Findings

**Source-level established invariant failure, upstream disposition: Pending PR.** Under accepted pure-DP parameters, the initial quantile evaluation recurses without progress. Severity: moderate availability risk; no separate privacy loss demonstrated. A deduplication search across audit issues, upstream issues, and PRs found the existing explicit fix in PR #2859. Consequently **no new candidate-defect issue** was created for this already-addressed pending repair. [Audit-task #22](https://github.com/opendp/opendp-audit/issues/22) coordinates the work.

## Unresolved questions

- Observe the failure in a compiled, isolated Rust child process; no process-level reproduction was executed here.
- Confirm PR #2859's endpoint guard through the full `PartialSample::value` path after it merges.
- Evaluate near-perfect privacy positive-delta tail performance and the general tradeoff proof separately.
