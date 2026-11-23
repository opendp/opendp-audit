---
schema_version: 1
source: rust/src/metrics/polars/mod.rs
updated: 2026-11-23
---

# `rust/src/metrics/polars/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated `Bounds::get_bound` inference from public `Bound::num_groups` and `Bound::per_group`; reachability of the shared `find_min_covering` comparator defect. The definitions of `SymmetricIdDistance`, `ChangeOneIdDistance`, and `FrameDistance` are context, not fully audited for their privacy guarantees here.
- **Invariant:** Querying a valid bound descriptor must not panic for an arbitrary `u32` bound. The inferred `num_groups` value may be loose but must not be incorrectly tightened by signed arithmetic.
- **Assumptions:** The bound descriptors are public and may contain any `u32` value; `Bound::with_num_groups` does not range-restrict. `find_min_covering` is the pinned helper in `domains/polars/frame/mod.rs`.
- **Pinned upstream:** [Metrics implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/polars/mod.rs), [covering helper](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/frame/mod.rs), [FFI get-bound endpoint](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/polars/ffi.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `Bounds::get_bound` | correctness/u32-weight-overflow | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Shared comparator reachability](#shared-comparator-reachability) |
| `Bounds::get_bound` | correctness/unsigned-bound-tie-break | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Shared comparator reachability](#shared-comparator-reachability) |
| `Bound::with_num_groups` | correctness/public-bound-range | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Shared comparator reachability](#shared-comparator-reachability) |
| `Bounds::get_bound` | privacy/conservative-frame-distance | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Limitations and privacy interpretation](#limitations-and-privacy-interpretation) |

## Analysis

### Shared comparator reachability

`Bound::with_num_groups` stores any `u32` in `Option<u32>`. `Bounds::get_bound(&by)` builds `all_mips` from all available bound descriptors with a known `num_groups`, then passes it to `find_min_covering(by.clone(), all_mips)`. The helper ranks tied candidate sets by `-(*weight as i32)`, so the valid bound `Bound::by(["A"]).with_num_groups(2_147_483_648)` triggers checked-build integer-negation overflow when querying the nonempty `{A}` grouping. No large dataset is needed. The C FFI endpoint `opendp_metrics___get_bound` accepts public `Bounds` and key expressions and invokes this function; the bug is therefore not restricted to internal optimizer code.

For two size-two descriptor sets covering `{A}`, with weights `1` and `2_147_483_649`, the signed comparison favors the larger, weaker bound even though the intended tie-break is the smaller number of groups. The downstream `try_fold` multiplies the chosen weights using checked/outward multiplication and returns `None` if that result is unrepresentable, so this path **does not** show a privacy-bound underestimate. It can trigger an unnecessary loss of usable public bounds.

See the [cross-file investigation](https://github.com/opendp/opendp-audit/blob/main/investigations/polars-covering-u32-weight-overflow.md), the [frame source audit](https://github.com/opendp/opendp-audit/blob/main/source/rust/src/domains/polars/frame/mod.rs.md), and [issue #92](https://github.com/opendp/opendp-audit/issues/92).

### Limitations and privacy interpretation

The `per_group` calculation takes the minimum of known bounds for coarser or equal groupings; the selected `num_groups` covering uses a product of public limits. These formulas were inspected to trace the signed-comparator problem, but were not exhaustively proved for all identifier metrics, multigroup adjacency semantics, or dataframes. The status for the overall conservative frame-distance property is `Partial`. The demonstrated failure is checked-build **availability** and unchecked-build **loss of precision**, not a known privacy guarantee violation.

**Executed:** Six Python tests modeling the shared comparator and covering. **Not executed:** OpenDP Rust, C FFI, real frame-metric composition, or group-by query execution.

## Next checks

- Add native regression tests to both caller APIs, including the public FFI endpoint if available.
- Change the helper's numeric tie-break to `std::cmp::Reverse(weight)` without signed narrowing; test both overflow configurations.
- Investigate the broader contribution-bound privacy theorem separately; [audit issue #92](https://github.com/opendp/opendp-audit/issues/92) tracks only the demonstrated boundary.
