---
schema_version: 1
source: rust/src/combinators/sequential_composition/non_adaptive/mod.rs
updated: 2026-11-23
---

# `rust/src/combinators/sequential_composition/non_adaptive/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated `make_composition`, covering input compatibility, static composition-map accounting, sequential child queryable retirement, and fallible evaluation. This review is limited to the Rust constructor and ordinary (non-panicking) invocation paths, not adaptive or fully adaptive composition.
- **Invariants:** Every component accepted into the composition is included in the announced privacy map; a successful invocation evaluates the components in order; when `CompositionMeasure::composability(NonAdaptive)` requires `Sequential`, no child queryable from an earlier component remains queryable after a later component begins.
- **Assumptions:** Child measurements and privacy maps honor their contracts, source values are in the common input domain, `CompositionMeasure` correctly describes the measure's interactive theorem, and queryables are created through the wrapper-aware `Queryable::new` rather than internal raw constructors. No arbitrary user callback or panicking execution is assumed sound.
- **Pinned sources:** [Constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/non_adaptive/mod.rs), [composition modes](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/mod.rs), [interactive wrappers](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/interactive/mod.rs), [measurement invocation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs), and [native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/sequential_composition/non_adaptive/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `combinators::sequential_composition::non_adaptive::make_composition` | privacy/nonadaptive-map-accounting | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [All-child map trace](#static-accounting-and-failure) |
| `combinators::sequential_composition::non_adaptive::make_composition` | privacy/interactive-sequentiality | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Cross-file wrapper investigation](../../../../../../investigations/nonadaptive-composition-interactive-retirement.md) |

## Analysis

### Static accounting and failure

Construction rejects the empty list, requires all child input domains, input metrics and output measures to match, clones every child function and privacy map, and checks `composability(NonAdaptive)`. The output map evaluates **every** cloned child map at the supplied input distance and passes the resulting list to `output_measure.compose`. It is independent of runtime success, count, or ordering. Therefore an error after an earlier component has emitted a private value does not omit that component from the advertised map. Indeed, even children that have not yet run are still counted: conservative static allocation, not an odometer of realized usage.

At invocation, `functions.iter().map(|f| f.eval(arg)).collect()` (or the equivalent sequential-wrapper branch) executes in original order and stops on the first error. All functions receive the same `arg`. This review establishes the **routing and inclusion** invariant assuming the individual maps and measure's composition theorem are sound; it does not independently prove numerical or interactive composition. Relevant pre-existing [measure audit](../mod.rs.md).

### Sequential child retirement

For `Composability::Sequential` the per-invocation `Rc<RefCell<usize>>` counter starts at zero and is incremented **before** each child function call. Each child's recursive wrapper captures that value as `child_id`. Its pre-hook permits an evaluation only while `active_id == child_id`. When the next child starts, its increment invalidates the previous child's token. `interactive::wrap` installs the hook while the function creates queryables; `Wrapper::new_recursive_pre_hook` reapplies the hook to queryables spawned during later child queries.

For a successful composition of N interactive children, the counter is N before the returned `Vec<TO>` becomes visible. As a result, **only the Nth child's returned queryable can still be used** under a sequential-only measure. Earlier children can be used within their own function/postprocessing before the next child starts; retired queryables reject further queries. Under `Composability::Concurrent` no retirement wrapper is installed, as required by that stronger theorem. At this revision, `Approximate<ZeroConcentratedDivergence>` requests `Sequential`; the other built-in measures in the reviewed composition module request `Concurrent`.

Ordinary `Err` returns restore the wrapper because `wrap` finishes normally, even though the `Fallible` value is an error. Panics are **not** protected by a guard in current `wrap`, and may leave the thread-local wrapper installed. This is already targeted by [open upstream PR #3277](https://github.com/opendp/opendp/pull/3277). [Open PR #3276](https://github.com/opendp/opendp/pull/3276) separately addresses unsafe exclusive borrowing in FFI reentrant queryable evaluation. These are pending upstream fixes, not newly discovered bugs.

### Evidence and limitations

Static inspection of the pinned constructor, composition-measure implementation, `Queryable` wrapper/type-erasure path, and upstream tests. **No native OpenDP test was executed** in this audit. Existing upstream tests check scalar composition, a composed RDP map, and interactive postprocessing performed *before* the next child begins; they do not directly assert that earlier returned queryables (or nested descendants) are rejected. The latter remains `Partial` pending native end-to-end regression coverage and a check of host-language wrappers. The model depends on the accuracy of child privacy maps and an external interactive composition theorem.

## Next checks

- Add a pinned-upstream native regression that returns two `Queryable` values under `Approximate<ZeroConcentratedDivergence>` and verifies the first is retired and the second usable; check a child-spawned nested queryable and a failing component.
- Reassess the panic and FFI reentrancy paths after upstream PRs [#3277](https://github.com/opendp/opendp/pull/3277) and [#3276](https://github.com/opendp/opendp/pull/3276) merge.
- No new defect was confirmed within the ordinary-path, stated-assumption scope; see [investigation](../../../../../../investigations/nonadaptive-composition-interactive-retirement.md).
