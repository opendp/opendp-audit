---
schema_version: 1
source: rust/src/traits/samplers/psrn/mod.rs
updated: 2026-11-23
---

# `rust/src/traits/samplers/psrn/mod.rs`

## Scope and assumptions

- **Audit scope:** Termination and documented Boolean correctness of `PartialSample::greater_than` when two valid `InverseCDF` implementations produce exactly equal samples. This does not audit the general PSRN sampling distribution, sampler entropy, or privacy of downstream mechanisms.
- **Invariant:** `greater_than` must return `Ok(false)` when its receiver is exactly equal to `other`, rather than repeatedly refining forever. Its public proof-definition comment says that the result is true if the first sample is greater and false otherwise.
- **Assumptions:** A valid `InverseCDF` may describe a point-mass distribution whose exact quantile is constant; `RBig` and `PartialOrd` implement their usual equality/ordering semantics. The result is conditioned on successful entropy acquisition during repeated refinements; an unrelated entropy error would terminate with `Err`, not a correct comparison.
- **Reviewed upstream revision:** `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. Pinned [implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/psrn/mod.rs), [unit tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/psrn/test.rs), and [public re-export](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/mod.rs).
- **Coordination:** [Audit task #26](https://github.com/opendp/opendp-audit/issues/26), [new candidate defect #28](https://github.com/opendp/opendp-audit/issues/28).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `traits::samplers::psrn::PartialSample::greater_than` | correctness/equality-termination | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Counterexample and validation gap](#equal-sample-counterexample) |

## Analysis

### Equal-sample counterexample

**Finding: source-level deterministic nontermination, not a demonstrated privacy failure.**

`InverseCDF::inverse_cdf` is a public trait method that receives a rational uniform point and returns an optional bound. A point-mass distribution at zero can validly implement this method by returning `Some(RBig::ZERO)` for every input, regardless of rounding direction or refinement depth. Construct two separate `PartialSample::new(PointMass)` instances. For either instance, both `lower()` and `upper()` always return the same exact zero.

The `greater_than` loop has only two success exits:
1. `self.lower() > other.upper()`, yielding true;
2. `self.upper() < other.lower()`, yielding false.

Both compare `0` with `0` and are false. The subsequent `refine()` call changes only the random interval, not the point-mass inverse CDF, so neither success exit is ever reached. Refinement alternates between the samples; the method never reports `false` for equality as documented. Conditional on ongoing entropy availability, it keeps consuming entropy and computation rather than returning. Resource exhaustion or a separate error is possible, but not the intended Boolean result.

The failure is not restricted to degenerate distributions: a valid binary-valued quantile may produce `0` for uniform draws below `1/2` and `1` otherwise. Two independent fair binary samples tie with probability `1/2`. Once both sampled uniform intervals are wholly in the same quantile cell, the output intervals equal a common point and the strict comparisons remain false.

The existing upstream `test_greater_than` uses two independent *continuous uniform* distributions. Such draws tie with probability zero in the ideal model, so the test does not exercise either equal-point-mass or discrete-tie behavior. Repository code search located the method's definition and the test call, but no production call site. This limits demonstrated practical impact to the exported Rust utility.

### Executed checks and limitations

A standalone Python 3.13 exact-rational transition model was executed with the same lower/upper strict-comparison branches and alternating 64-bit refinements:

- Two point-mass distributions at zero: **1,000 iterations**, zero/zero edges throughout, no comparison result.
- Two fair binary distributions with respective underlying uniform draws `1/4` and `3/8` (both yield zero): **1,000 iterations**, no result.
- An untied binary control with draws `3/4` and `1/4` returned `true`.

This model establishes why the source control flow cannot distinguish ties. **No compiled OpenDP Rust test, FFI test, or timeout subprocess was run.** Thus [issue #28](https://github.com/opendp/opendp-audit/issues/28) is tracked as a **Candidate**, even though the source-level counterexample is deterministic.

**Deduplication:** Searches of open and closed audit and upstream issues and upstream PRs found no equivalent report. [Upstream open PR #2856](https://github.com/opendp/opendp/pull/2856) changes `InverseCDF` error propagation but retains both strict comparison guards, so it does not fix equality. [Upstream draft PR #2859](https://github.com/opendp/opendp/pull/2859) addresses a distinct canonical-quantile endpoint recursion.

### Repair considerations

Handle a *certified* equality case: if both samples' lower and upper bounds equal the same exact value, their strict comparison is false. Do not treat merely overlapping intervals as equal: further refinement can distinguish nonidentical samples. Alternatively, make strict no-tie distribution assumptions explicit and enforceable or use a three-way result. A regression test for `PointMass` and a finite-support binary inverse CDF should be executed in an isolated process with a timeout before a fix is established.

## Next checks

- Execute a targeted compiled Rust reproduction safely in a child process with a timeout; test both point-mass and discrete-tie cases.
- Review any external users of the exported `PartialSample` API; no production call site was found within the inspected repository search.
- Once fixed upstream, verify equality handling for exact singleton intervals without sacrificing strict ordering for overlapping nondegenerate intervals.
