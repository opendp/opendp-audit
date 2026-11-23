---
schema_version: 1
source: rust/src/combinators/sequential_composition/mod.rs
updated: 2026-11-22
---

# `rust/src/combinators/sequential_composition/mod.rs`

## Scope and assumptions

- **Scope:** The componentwise numerical upper bound produced by `compose` for `Approximate<MaxDivergence>` and `Approximate<ZeroConcentratedDivergence>`, plus a limited proof-to-implementation check of `MaxDivergence::composability` for `FullyAdaptive`.
- **Invariant:** For a finite sequence of valid, finite, nonnegative input privacy distances `(p_i, delta_i)`, a successful composition result `(p, delta)` must satisfy `p >= sum(p_i)` and `delta >= sum(delta_i)` with the sums interpreted over exact reals. An unrepresentable sum may produce an error rather than a numerical bound. For the fully adaptive branch, any returned `Composability` must be justified for the selected adaptivity mode.
- **Assumptions:** Each input distance is a valid privacy upper bound, both components are finite and nonnegative, and `InfAdd` meets its documented upward-rounding contract. This review does not establish that every caller supplies valid distances or independently verify the underlying composition theorems.
- **Pinned source:** [CompositionMeasure implementations](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/mod.rs), [InfAdd trait and f64 implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/arithmetic/mod.rs), and [measure distance types](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measures/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `CompositionMeasure for Approximate<MaxDivergence>::compose` | privacy/composition-upper-bound | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Componentwise upper bound](#componentwise-upper-bound) |
| `CompositionMeasure for Approximate<ZeroConcentratedDivergence>::compose` | privacy/composition-upper-bound | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Componentwise upper bound](#componentwise-upper-bound) |
| `CompositionMeasure for MaxDivergence::composability` | privacy/fully-adaptive-composability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Proof alignment](#proof-alignment) |

## Analysis

### Componentwise upper bound

Both approximate-measure implementations use `d_mids.iter().try_fold((0.0, 0.0), ...)`, applying `inf_add` independently to the privacy parameter (`epsilon` or `rho`) and slack (`delta`). For an empty list the result is `(0.0, 0.0)`. For each subsequent entry, if the running components upper-bound their respective exact partial sums, `InfAdd`'s documented postcondition preserves those inequalities. Induction gives the stated componentwise bound for every `Ok` result.

The reviewed `f64` `InfAdd` implementation converts finite inputs to `FBig<Up>`, performs addition, then calls `inf_cast` on the result; it rejects NaN/infinite operands and rejects non-finite results. The fold uses `?`, so an arithmetic failure returns an error rather than a smaller reported distance. This reasoning relies on the `InfAdd`/`InfCast` contract; it is not an independent proof of the arbitrary-precision backend or conversion implementation.

The [approximate max-divergence proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/CompositionMeasure_for_ApproximateMaxDivergence.tex) and [approximate zCDP proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/CompositionMeasure_for_ApproximateZeroConcentratedDivergence.tex) also use componentwise summation and the `InfAdd` postcondition. This row audits **numerical accounting only**, not the validity of composing underlying interactive mechanisms or the interpretation of privacy distances outside the assumptions above.

**Evidence type:** Static source and proof-document inspection at the pinned commit. No upstream Rust binaries or numeric regression tests were executed in this review. **Scoped finding:** No undercounting path identified for successful composition of the assumed valid distances.

### Proof alignment

`CompositionMeasure for MaxDivergence::composability` ignores the adaptivity argument and returns `Composability::Concurrent`. Its [associated proof table](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/CompositionMeasure_for_MaxDivergence.tex) lists no theorem for the fully adaptive case, whereas the approximate max-divergence proof cites a fully adaptive concurrent-composition theorem. The [fully adaptive constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/fully_adaptive/mod.rs) queries this method and relies on `Concurrent` to omit sequential-interaction wrappers.

This is an **unresolved proof-alignment discrepancy**, not a demonstrated privacy bug. In particular, the approximate theorem may imply the pure case when `delta = 0`; applicability to the implemented odometer and its realized privacy-loss output was not proven here. The `Partial` row does not certify fully adaptive composability.

## Next checks

- Establish whether the cited fully adaptive approximate-DP theorem proves the required pure-DP concurrent case, including the semantics of querying the odometer's composed distance after adaptively chosen queries.
- Check `InfCast`'s concrete `FBig` to `f64` conversion and add upstream boundary-case Rust tests for outward rounding and overflow if coverage is absent.
- Inspect other `CompositionMeasure` implementations and all caller paths for invalid signed or non-finite privacy distances; the summation result above is conditional on valid inputs.

No candidate defect was confirmed within the reviewed scope. GitHub audit-task and candidate-defect issues were not created because this run's instructions prohibit opening issues.
