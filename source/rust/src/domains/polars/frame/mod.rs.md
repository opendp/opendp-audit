---
schema_version: 1
source: rust/src/domains/polars/frame/mod.rs
updated: 2026-11-23
---

# `rust/src/domains/polars/frame/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated `find_min_covering` greedy set-cover helper, the `FrameDomain::get_margin` caller, and the admission of `Margin::max_groups` via `with_max_groups` and `FrameDomain::with_margin`. Review the neighboring `Bounds::get_bound` caller only to establish shared reachability. This is not a full audit of `FrameDomain::member`, all grouping semantics, or private query planning.
- **Invariant:** Set-cover selection must not panic for any valid `u32` public group-count bound. Among equal-coverage, equal-size sets, smaller weights should be preferred as the code comment specifies. Inferred group-count bounds should be conservative; selecting a larger valid descriptor is a utility issue, not automatically an undercount of privacy loss.
- **Assumptions:** `max_groups` is a public `Option<u32>`; `Margin::with_max_groups` accepts every `u32` without narrowing. Rust's `as i32` cast reinterprets the low 32 bits and checked negation of `i32::MIN` panics; ordinary unchecked release negation wraps. The set of column expressions can be as small as one column; no large dataframe is needed.
- **Pinned upstream:** [Frame source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/frame/mod.rs), [frame native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/frame/test.rs), [metrics caller](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/polars/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `domains::polars::frame::find_min_covering` | correctness/u32-weight-overflow | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Checked arithmetic panic](#checked-arithmetic-panic) |
| `domains::polars::frame::find_min_covering` | correctness/unsigned-weight-order | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Unsigned priority inversion](#unsigned-priority-inversion) |
| `FrameDomain::get_margin` | correctness/large-group-bound-inference | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Caller reachability](#caller-reachability) |
| `Margin::with_max_groups` | correctness/public-bound-range | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Caller reachability](#caller-reachability) |
| `domains::polars::frame::find_min_covering` | privacy/conservative-cover-bound | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Privacy and proof limits](#privacy-and-proof-limits) |

## Analysis

### Checked arithmetic panic

For each candidate set, `find_min_covering` evaluates a three-component comparison key:

```rust
(
    set.intersection(&must_cover).count(),
    -(set.len() as i32),
    -(*weight as i32),
)
```

The third entry converts a public `u32` bound to `i32` and negates it. At `weight = 2_147_483_648u32 = 2^31`, the cast produces `i32::MIN = -2_147_483_648`; the unary negation overflows. With overflow checks enabled, `max_by_key` panics while building the key, even for **one candidate set and one grouping column**. The helper returns an `Option` but the failure is a panic rather than `None` or a structured error. On unchecked builds this negation wraps to `i32::MIN`. The bug is a narrow arithmetic contract failure, not dependent on private data.

### Unsigned priority inversion

For `2^31 + 1 <= weight <= u32::MAX`, the cast produces a negative `i32`, so `-(weight as i32)` becomes **positive**. If two available sets have the same number of newly covered columns and the same set size, the larger invalidly signed weight wins. Example: infer `by={A}` from available descriptors `by={A,B}, max_groups=1` and `by={A,C}, max_groups=2_147_483_649`. Both candidates cover exactly `{A}` and have size two. The key for weight `1` is `-1`; the key for weight `2_147_483_649` is `2_147_483_647`. The helper therefore selects the latter and infers `max_groups=2_147_483_649` instead of `1`. This is a **weaker, still conservative** upper bound. If multiplied with other bounds it can also lose a useful finite result through the caller's checked multiplication and fallback to `None`.

The smallest direct repair is to compare unsigned values without negating or narrowing: `Reverse(set.len())` and `Reverse(*weight)` inside the tuple (`std::cmp::Reverse`). The first key, number of newly covered columns, remains unchanged.

### Caller reachability

`Margin::with_max_groups` stores an arbitrary `u32` without special treatment of `2^31`. `FrameDomain::with_margin` validates that grouping root columns occur in the schema, then accepts the descriptor without inspecting the value. `FrameDomain::get_margin(&by)` collects the public `max_groups` descriptors and calls `find_min_covering`, yielding the panic directly for an ordinary nonempty `{A}` query with an `A` descriptor at `2^31`.

The independent `Bounds::get_bound` function in [the metrics source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/polars/mod.rs) passes `Bound::num_groups: Option<u32>` into the **same** helper. Both paths have the same boundary. No special dataset size or private-value-dependent branch is needed. Existing upstream native covering tests use small weights (`1`, `10`, `11`) and do not exercise this signed threshold.

### Privacy and proof limits

The helper selects sets whose **union** covers the requested grouping keys; the callers multiply valid public upper bounds, falling back to `None` on checked product overflow. Choosing an inappropriately *larger* number can worsen utility or overstate the bound, but this inspection did not find a way for the signed comparator to produce a false **smaller** bound. No underreported DP privacy cost or private-dependent exception was demonstrated. Full compositional proof obligations for arbitrary margin sets and query optimization were not re-established; this property remains `Partial`.

**Executed locally:** Six Python 3 standard-library reference-model tests representing the exact `u32 -> i32` conversion, checked/unchecked negation, the two caller-equivalent set configurations, valid small covers, and a finite safety check of the proposed unsigned comparison. No compiled OpenDP Rust binary was executed in the local audit runtime. See [cross-file investigation](https://github.com/opendp/opendp-audit/blob/main/investigations/polars-covering-u32-weight-overflow.md), [reference tests](https://github.com/opendp/opendp-audit/blob/main/tools/tests/test_polars_covering_weight_model.py), and [audit issue #92](https://github.com/opendp/opendp-audit/issues/92).

## Next checks

- Add native debug/release regressions in the pinned upstream checkout at weights `2^31 - 1`, `2^31`, `2^31 + 1`, and `u32::MAX`, through both `FrameDomain::get_margin` and `Bounds::get_bound`.
- Replace the signed negations with `std::cmp::Reverse` ordering and verify the tie-break prioritizes smaller unsigned group counts, without changing the number-of-covered-columns heuristic.
- Separately test the remaining group-count and contribution-bound composition logic before asserting a global privacy certificate. **Disposition:** Source-confirmed availability/correctness defect [#92](https://github.com/opendp/opendp-audit/issues/92); upstream unreported after matching audit/upstream issues and fix PRs.
