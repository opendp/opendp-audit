---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Open-issue root-cause generalization sweep (2026-11-23)

## Invariant and threat model

This is a **bounded cross-file generalization review** of the 22 open defect reports present at review time, not a globally maintained issue index or a certification of their independent validity. The questions are whether a reported failure extends to sibling constructors, metrics, or output adapters, and whether apparently similar reports should share an upstream repair. Pin checked OpenDP source to `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` and pinned Polars source to `py-1.36.1` (`2a151c10fa76790711c2f75e6d012dd69c627ddd`). GitHub issue and PR states may change after this snapshot.

A generalization is **established only at its stated evidence level**. Directly inspecting control flow is not native execution; an output-domain precondition mismatch alone does not prove an end-to-end privacy underestimate. This sweep did not run new compiled OpenDP tests; it reviewed source and previously recorded CI results.

## A newly identified shared failure: duplicate public replacement keys

[Audit #56](https://github.com/opendp/opendp-audit/issues/56) originally concerns `make_expr_replace`. The sibling non-deprecated [`make_expr_replace_strict`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_replace_strict/mod.rs) also materializes public `old` and `new` lists, validates their lengths and types, and builds an expression **without checking uniqueness of `old`**.

The same-version [Polars runtime implementation](https://github.com/pola-rs/polars/blob/py-1.36.1/crates/polars-ops/src/series/ops/replace.rs) calls `validate_old(&old)?` in `replace`, `replace_strict`, and `replace_or_default`; this enforces `old.n_unique()? == old.len()`. Therefore a malformed public mapping `old=[1,1], new=[10,20]` has the **same deferred public-validation failure** in both OpenDP constructors. The ordinary [native OpenDP integration and CI-only repair tests](https://github.com/opendp/opendp-audit/actions/runs/45107956499) have passed. The strict sibling is **source-confirmed only**; do not infer that its full native constructor-to-collection path was executed.

The open upstream [PR #3214](https://github.com/opendp/opendp/pull/3214) edits both constructors for distinct hardening concerns but does not implement this shared uniqueness predicate. The report has been **consolidated into existing #56**, not split into another issue. A corrective implementation should use a shared public-literal guard and test both `replace_strict` variants, including an explicit default, NULL and NaN duplicates, and cast-equivalent keys.

## A related metric-space precondition: nested float arrays

[Audit #57](https://github.com/opendp/opendp-audit/issues/57) establishes that `ExprDomain` accepts NaN-permitting float `LpDistance<1/2>` spaces, whereas the vector metric-space validator rejects them. The same [`ExprDomain` implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/expr/mod.rs) validates `LInfDistance<Q>` for array columns by **outer nullability and primitive numeric array dtype only**, omitting the nested domain's NaN/null permissions. `L0InfDistance<LInfDistance<Q>>` delegates to that check.

[`SeriesDomain::new_element_domain`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/series/mod.rs) builds `ArrayDomain` with default `AtomDomain<f32/f64>` elements when supplied an array float dtype; default float atoms permit NaNs. The outer `SeriesDomain.nullable` flag does not certify that every nested element is finite. **Limitation:** the same `SeriesDomain::member` implementation does not yet implement array membership. A real array-valued `LInfDistance` constructor or privacy-measurement failure has **not** been demonstrated. This is a **candidate extension** to #57 requiring compiled metric-space and reachability tests, not a separate confirmed privacy issue.

## Existing reports with a shared repair surface, but distinct public failures

| Reports | Common failure and review result | Tracking decision |
| --- | --- | --- |
| [#12](https://github.com/opendp/opendp-audit/issues/12), [#13](https://github.com/opendp/opendp-audit/issues/13), [#17](https://github.com/opendp/opendp-audit/issues/17) | [`count_cdf/mod.rs`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/count_cdf/mod.rs) indexes the final element of a cumulative sum in **two functions**, which can each receive an empty effective count vector (empty `make_cdf` input versus singleton-bin `make_quantiles_from_counts` with two extremal counts). The same quantiles constructor has a **separate** partial-order NaN guard gap. | Keep three distinct API-contract reports, but share regression helpers and guard patterns. Neither empty-input path is fixed merely by adding NaN guards. |
| [#44](https://github.com/opendp/opendp-audit/issues/44) | Float `then_deintegerize_hashmap` and integer `then_saturating_cast_hashmap` both apply a lossy native conversion **after** the internal strict threshold predicate. | Already consolidated under one canonical issue; production fix and tests must cover both adapters. |
| [#32](https://github.com/opendp/opendp-audit/issues/32), [#56](https://github.com/opendp/opendp-audit/issues/56), [#66](https://github.com/opendp/opendp-audit/issues/66) | Fallible constructors defer validation of **public parameters** until invocation/collection (inverted clamp interval, nonunique replacement keys, invalid temporal-function/dtype pairs). | Shared design principle—enforce known public preconditions at construction—but **different source locations, conditions and fixes**. Keep them distinct; the #56 strict sibling is included in #56. |
| [#37](https://github.com/opendp/opendp-audit/issues/37), [#57](https://github.com/opendp/opendp-audit/issues/57), [#78](https://github.com/opendp/opendp-audit/issues/78) | Metric or output-domain invariants are insufficiently checked: invalid `LpDistance<0>` exponent, NaN-permitting domain under `Lp`, or grouped `len()` output `max_groups=1`. | Separate fixes: supported exponents, nested value-domain admissibility, and per-group output metadata. Do not confuse source-level preconditions with demonstrated privacy-accounting undercounts. |

## Explicit negative checks and boundaries

- [#78](https://github.com/opendp/opendp-audit/issues/78): [`make_expr_len`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_len/mod.rs) hardcodes `max_groups: Some(1)` when grouped. Direct siblings [`make_expr_count`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_count/mod.rs) and [`make_expr_sum`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_sum/mod.rs) correctly preserve input `margin.max_groups`. The reviewed literal pattern occurs only in `make_expr_len` among these constructors. Existing upstream [#3152](https://github.com/opendp/opendp/issues/3152) concerns **pairwise sensitivity derived from input** `max_groups`, not this **output-domain postcondition**; no duplicate closure is justified.
- [#27](https://github.com/opendp/opendp-audit/issues/27): direct [`make_metric_unbounded`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/cast_metric/mod.rs) sibling `make_metric_bounded` uses `d_in / 2`, which does not exhibit the same overflow. The multiplication defect applies to **both metric-pair instantiations** of the one unbounded constructor, already covered by its [native debug/release CI](https://github.com/opendp/opendp-audit/actions/runs/45102835887). This is **not** a repo-wide proof that all stability maps use checked arithmetic.
- [#17](https://github.com/opendp/opendp-audit/issues/17): the nearby [quantile candidate validator](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/quantile_score_candidates/mod.rs) uses `partial_cmp` with an explicit unordered case, rather than the bad `>=` guard. This does not remediate NaNs in the separate count-quantiles constructor.
- [#28](https://github.com/opendp/opendp-audit/issues/28): the reviewed [PSRN module](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/psrn/mod.rs) exposes one `greater_than` comparator with a missing equality/overlapping-point-mass termination case; no independent `less_than` implementation was found in that module. Generalizing to other distribution comparisons requires new caller/reachability evidence.
- [#4](https://github.com/opendp/opendp-audit/issues/4) and [#33](https://github.com/opendp/opendp-audit/issues/33) remain **different** overflow mechanisms (signed-width integer subtraction versus float summation/cancellation). Both require width-aware arithmetic, but one repair does not imply the other is fixed.
- [#9](https://github.com/opendp/opendp-audit/issues/9), [#18](https://github.com/opendp/opendp-audit/issues/18), [#21](https://github.com/opendp/opendp-audit/issues/21), [#48](https://github.com/opendp/opendp-audit/issues/48) are distinct proof/Rustdoc drift patterns; the common process improvement is matching executable code with proof/specification during review, not assuming a single runtime defect.
- [#7](https://github.com/opendp/opendp-audit/issues/7) already consolidates two nested-opaque R FFI tuple failures; the evidence examined here does not justify extending it to other bindings.

## Findings

- **New source-confirmed sibling**: `make_expr_replace_strict` shares #56's missing duplicate public-key validation. Issue #56 was updated; no duplicate defect issue filed.
- **New candidate sibling**: `LInfDistance`/delegated `L0InfDistance` for nested array values may share #57's missing NaN-domain guard. Issue #57 was updated with explicit membership/reachability limitations.
- **Shared helper opportunity**: #12/#13's cumulative-sum indexing and #44's two output adapters call for coordinated regression coverage, without collapsing distinct public API failures.
- **Negative controls**: sibling count/sum metadata, the bounded metric cast, and the neighboring NaN-aware quantile validator do **not** show the particular defects sought in this sweep.

## Unresolved questions

1. Execute compiled OpenDP/Polars `replace_strict` duplicate-public-key tests both with and without explicit default. Expand the existing CI-only fix to a shared constructor guard, respecting public casts and NULL/NaN equality.
2. Construct a reachable float-array `ExprDomain` and exercise `LInfDistance` and delegated `L0InfDistance` metric-space checks in native Rust; resolve unimplemented array membership before claiming an end-to-end measurement problem.
3. Add native grouped-`len()` two-group output-domain membership and downstream composition regressions for #78; separately test #12/#13's empty cumulative sums.
4. Track the effects of upstream PRs and re-evaluate if their code changes materially; a pending PR is not an upstream-main fix. This is a bounded one-time review, **not** an exhaustive assertion that no other siblings exist.
