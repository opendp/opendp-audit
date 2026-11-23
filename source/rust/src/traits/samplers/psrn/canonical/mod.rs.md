---
schema_version: 1
source: rust/src/traits/samplers/psrn/canonical/mod.rs
updated: 2026-11-23
---

# `rust/src/traits/samplers/psrn/canonical/mod.rs`

## Scope and assumptions

- **Audit scope:** Termination of `CanonicalRV::inverse_cdf` and `quantile_cnd` at exact uniform endpoints `0` and `1` for pure-DP tradeoffs. General quantile distribution correctness and tail runtime are excluded.
- **Invariant:** Endpoint evaluations must terminate or return `None` rather than recurse indefinitely.
- **Assumptions:** Exact rational arithmetic, a symmetric pure-DP tradeoff where `f(0)=1` and `0<c<1/2`, and `PartialSample::new` initializes its interval to `[0,1]`.
- **Pinned sources:** [Inverse-CDF implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/psrn/canonical/mod.rs), [PartialSample](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/psrn/mod.rs), [tradeoff constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/canonical_noise/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `traits::samplers::psrn::canonical::quantile_cnd` | correctness/endpoint-termination | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Investigation](../../../../../../../investigations/canonical-noise-pure-dp-endpoint-recursion.md) |
| `traits::samplers::psrn::canonical::CanonicalRV::inverse_cdf` | correctness/endpoint-termination | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Endpoint recursion](#endpoint-recursion) |

## Analysis

### Endpoint recursion

For `0<c<1/2`, `quantile_cnd(0, f, c)` enters the lower branch and calls `quantile_cnd(1-f(0), f, c) - 1`. At `delta=0`, `f(0)=1`, so this passes exactly `0` to itself. For `u=1`, the upper branch calls `quantile_cnd(f(0), f, c) + 1`, again passing exactly `1`. There are no endpoint checks or depth limits, and both calls are non-tail recursive.

`CanonicalRV::inverse_cdf` forwards directly to `quantile_cnd`. `PartialSample::new` initializes `randomness=0`, `refinements=0`; the first `lower()` edge is `(0+0)/2^0=0`, so `PartialSample::value()` necessarily hits the recursion before its first entropy refinement. These observations establish an unbounded call chain under the pinned source's pure-DP parameters. The actual Rust stack-exhaustion response was not executed.

A Python exact-rational transition test verified 25 identical zero transitions for `delta=0` and progression for `delta=1e-6`. See the [cross-file investigation](../../../../../../../investigations/canonical-noise-pure-dp-endpoint-recursion.md).

**Disposition:** [Draft upstream PR #2859](https://github.com/opendp/opendp/pull/2859) directly adds a `uniform == 0 || uniform == 1` guard returning `None` and an iterative quantile traversal, but is not merged to upstream `main`. No duplicate defect issue was filed.

## Next checks

- Reproduce in an isolated Rust child process, then verify the draft endpoint guard allows `PartialSample::value` to refine.
- Audit non-endpoint traversal complexity separately; only endpoint termination is covered here.
