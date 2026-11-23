---
schema_version: 1
source: rust/src/combinators/sequential_composition/mod.rs
updated: 2026-11-22
---

# `rust/src/combinators/sequential_composition/mod.rs`

## Scope and assumptions

- **Scope:** The componentwise numerical upper bound produced by `compose` for `Approximate<MaxDivergence>` and `Approximate<ZeroConcentratedDivergence>`, plus a targeted theorem-to-implementation check of `MaxDivergence::composability` for `FullyAdaptive` (including its odometer caller and proof pseudocode).
- **Invariant:** For a finite sequence of valid, finite, nonnegative input privacy distances `(p_i, delta_i)`, a successful composition result `(p, delta)` must satisfy `p >= sum(p_i)` and `delta >= sum(delta_i)` with the sums interpreted over exact reals. An unrepresentable sum may produce an error rather than a numerical bound. For the fully adaptive branch, any returned `Composability` must be justified for the selected adaptivity mode.
- **Assumptions:** Each input distance is a valid privacy upper bound, both components are finite and nonnegative, and `InfAdd` meets its documented upward-rounding contract. For the fully adaptive analysis, child privacy maps must validly upper-bound the privacy loss at a fixed input distance, child mechanisms must meet the paper's finite-communication assumption, and the privacy-loss accumulator is interpreted through truncated views at a fixed threshold. This review does not establish that all callers meet these assumptions or independently verify the cited theorems.
- **Pinned source:** [CompositionMeasure implementations](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/mod.rs), [InfAdd trait and f64 implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/arithmetic/mod.rs), and [measure distance types](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measures/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `CompositionMeasure for Approximate<MaxDivergence>::compose` | privacy/composition-upper-bound | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Componentwise upper bound](#componentwise-upper-bound) |
| `CompositionMeasure for Approximate<ZeroConcentratedDivergence>::compose` | privacy/composition-upper-bound | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Componentwise upper bound](#componentwise-upper-bound) |
| `CompositionMeasure for MaxDivergence::composability` | privacy/fully-adaptive-composability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Proof alignment](#proof-alignment); [cross-file investigation](../../../../../investigations/fully-adaptive-pure-composition.md) |

## Analysis

### Componentwise upper bound

Both approximate-measure implementations use `d_mids.iter().try_fold((0.0, 0.0), ...)`, applying `inf_add` independently to the privacy parameter (`epsilon` or `rho`) and slack (`delta`). For an empty list the result is `(0.0, 0.0)`. For each subsequent entry, if the running components upper-bound their respective exact partial sums, `InfAdd`'s documented postcondition preserves those inequalities. Induction gives the stated componentwise bound for every `Ok` result.

The reviewed `f64` `InfAdd` implementation converts finite inputs to `FBig<Up>`, performs addition, then calls `inf_cast` on the result; it rejects NaN/infinite operands and rejects non-finite results. The fold uses `?`, so an arithmetic failure returns an error rather than a smaller reported distance. This reasoning relies on the `InfAdd`/`InfCast` contract; it is not an independent proof of the arbitrary-precision backend or conversion implementation.

The [approximate max-divergence proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/CompositionMeasure_for_ApproximateMaxDivergence.tex) and [approximate zCDP proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/CompositionMeasure_for_ApproximateZeroConcentratedDivergence.tex) also use componentwise summation and the `InfAdd` postcondition. This row audits **numerical accounting only**, not the validity of composing underlying interactive mechanisms or the interpretation of privacy distances outside the assumptions above.

**Evidence type:** Static source and proof-document inspection at the pinned commit. No upstream Rust binaries or numeric regression tests were executed in this review. **Scoped finding:** No undercounting path identified for successful composition of the assumed valid distances.

### Proof alignment

`CompositionMeasure for MaxDivergence::composability` ignores the adaptivity argument and returns `Composability::Concurrent`, including for `FullyAdaptive`. Its [associated proof table](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/CompositionMeasure_for_MaxDivergence.tex) lists no theorem for fully adaptive composition. More concretely, the [proof pseudocode](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/pseudocode/CompositionMeasure_for_MaxDivergence.py) explicitly rejects `FullyAdaptive`, although the current Rust code accepts it. **The proof artifact and implementation do not agree.**

The missing theoretical justification is nevertheless available under explicit assumptions: basic adaptive composition for noninteractive pure-DP mechanisms gives a valid additive privacy filter, and the filter/odometer equivalence (Lemma 2.19) yields the additive noninteractive privacy-loss accumulator. Theorem 1.19(2) of [Haney et al. (CCS 2023)](https://doi.org/10.1145/3576915.3623128) extends a valid noninteractive `(epsilon, delta)` accumulator to concurrent interactive mechanisms with adaptively selected parameters, including the pure `delta = 0` case. This uses the paper's **truncated-view odometer guarantee**, not a claim that an untruncated transcript with a random realized budget is itself DP at that budget.

The [fully adaptive constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/fully_adaptive/mod.rs) queries `composability` and omits sequential-interaction wrappers when it returns `Concurrent`. It records each child's privacy map **before** invoking that child; the privacy-loss query evaluates all recorded maps at its requested `d_in` and calls `compose`. The corresponding [queryable proof document](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/fully_adaptive/new_fully_adaptive_composition_queryable.tex) explains how this representation corresponds to Algorithm 6 of the paper. Existing upstream tests inspect accumulated costs after successful and failed invocations, but these were **read, not executed** in this review.

This gives a plausible and specifically cited argument for the pure-DP concurrent branch **when each child has a valid, nonnegative privacy guarantee, communication is finite, and the implementation preserves the paper's queryable/odometer semantics**. The `Partial` status remains because these assumptions and all error paths were not independently verified end to end. The outdated upstream proof document is a documentation/proof maintenance defect, not a confirmed privacy counterexample. See the [cross-file investigation](../../../../../investigations/fully-adaptive-pure-composition.md).

## Next checks

- Reconcile the upstream `MaxDivergence` proof pseudocode/table with the Rust implementation, citing Theorem 1.19(2) and its finite-communication and truncated-view conditions; audit any effects from error handling and child queryable lifetimes that could violate the paper-to-code correspondence.
- Check `InfCast`'s concrete `FBig` to `f64` conversion and add upstream boundary-case Rust tests for outward rounding and overflow if coverage is absent.
- Inspect other `CompositionMeasure` implementations and all caller paths for invalid signed or non-finite privacy distances; the summation result above is conditional on valid inputs.

No candidate defect was confirmed within the reviewed scope. GitHub audit-task and candidate-defect issues were not created because this run's instructions prohibit opening issues.
