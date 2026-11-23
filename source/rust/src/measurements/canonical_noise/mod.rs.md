---
schema_version: 1
source: rust/src/measurements/canonical_noise/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/canonical_noise/mod.rs`

## Scope and assumptions

- **Audit scope:** Whether valid pure-DP parameters (`epsilon > 0, delta = 0`) create a canonical-noise measurement whose invocation never terminates due to the downstream inverse-CDF sampler. This is a bounded correctness and availability review, not a full privacy proof.
- **Invariant:** For in-domain input, an accepted measurement must release a value or return a controlled error; it must not recurse indefinitely.
- **Assumptions:** `RBig` arithmetic is exact; for `epsilon=1` the down-rounded exponential is finite and greater than one; `PartialSample::value` begins with the initial interval before refinement. No OpenDP Rust invocation was executed.
- **Pinned sources:** [Constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/canonical_noise/mod.rs), [sampler](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/psrn/mod.rs), [recursive quantile](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/psrn/canonical/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::canonical_noise::make_canonical_noise` | correctness/pure-dp-termination | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file investigation](../../../../../investigations/canonical-noise-pure-dp-endpoint-recursion.md) |
| `measurements::canonical_noise::approximate_to_tradeoff` | correctness/pure-dp-boundary | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Boundary analysis](#boundary-analysis) |

## Analysis

### Boundary analysis

`make_canonical_noise(AtomDomain::new_non_nan(), AbsoluteDistance::default(), 1.0, (1.0, 0.0))` satisfies the constructor's sensitivity and privacy-parameter guards. `approximate_to_tradeoff` admits `epsilon=1, delta=0`, builds a rational fixed point `c = 1/(1 + exp_down(1))` strictly between zero and one half, and defines a tradeoff with `f(0) = 1` exactly.

The returned closure constructs a `CanonicalRV` and evaluates `PartialSample::value`. Its first lower interval endpoint is exactly zero, and the recursive inverse-CDF call maps that endpoint to itself. Thus, by source control flow, **the first invocation cannot complete**. Repeated non-tail recursion would normally exhaust the stack rather than return a `Fallible` error; the compiled process failure mode was not executed. This is an availability defect, **not** demonstrated privacy leakage. The existing upstream test uses `delta=1e-7` and misses the pure-DP boundary.

An independent Python `Fraction` model was executed for 25 transitions: at `delta=0`, the argument remained exactly zero; at `delta=1e-6`, it advanced into the interior. This is a mathematical recurrence test, not compiled Rust. The [investigation](../../../../../investigations/canonical-noise-pure-dp-endpoint-recursion.md) traces the full dependency chain.

**Upstream disposition:** Pending PR. [Draft PR #2859](https://github.com/opendp/opendp/pull/2859) explicitly guards uniform endpoints and replaces recursion with a loop; it is **open and unmerged** at this review. No duplicate candidate-defect issue was opened because that PR addresses the exact failure. [Audit task #22](https://github.com/opendp/opendp-audit/issues/22) coordinates this review. `Audited` describes only the declared constructor endpoint behavior; broader tradeoff properties remain `Partial`.

## Next checks

- Run an isolated-process Rust regression for the exact constructor and invocation; no compiled OpenDP execution was performed here.
- Verify PR #2859's endpoint behavior after merge, including the `PartialSample::value` refinement path.
- Separately assess extreme positive but nonzero delta and other tradeoff arithmetic.
