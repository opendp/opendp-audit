---
schema_version: 1
source: rust/src/measurements/make_private_lazyframe/group_by/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/make_private_lazyframe/group_by/mod.rs`

## Scope and assumptions

- **Scope:** The non-deprecated Polars `make_private_group_by` measurement, its `L0/L1/L∞` certificate normalization, public/invariant/threshold key release paths, and nested grouping key dtype checks. The matcher is a dependency, not separately given complete symbol coverage here.
- **Invariant:** Every returned distance triple dominates the actual grouped symmetric differences, and a private grouping-key set is not released for free: it requires a valid threshold with delta accounting or a join with a truly public, sanitized key set. Unsupported encodings or query shapes must be rejected rather than silently certified.
- **Assumptions:** Earlier `StableDslPlan` and `PrivateExpr` contracts hold; all supplied `Bounds` and domain margins are valid; the source-matched Polars executor observes the declared query semantics. `Invariant::Keys` and `Invariant::Lengths` both imply a shared key set by [domain definition](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/frame/mod.rs). The numerical model does not execute the compiled library.
- **Pinned sources:** [implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/group_by/mod.rs), [matcher](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/group_by/matching.rs), [Rust tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/group_by/test.rs), [proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/group_by/make_private_group_by.tex).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_private_group_by` | privacy/grouped-distance-normalization | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Distance normalization](#distance-normalization), [finite model](../../../../../../tools/tests/test_private_groupby_distance_model.py), [investigation](../../../../../../investigations/polars-private-groupby-bounds-and-key-sanitization.md) |
| `make_private_group_by` | privacy/keyset-sanitization | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Public, invariant and threshold branches](#public-invariant-and-threshold-branches) |
| `contains_float` | correctness/unsafe-grouping-key-rejection | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Nested key dtype guards](#nested-key-dtype-guards), [upstream native tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/group_by/test.rs) |
| `contains_categorical` | correctness/unsafe-grouping-key-rejection | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Nested key dtype guards](#nested-key-dtype-guards) |
| `integrate_discrete_noise_tail` | privacy/keyset-tail-delta-bound | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Threshold tail accounting](#threshold-tail-accounting) |
| `ApproximateMeasure::add_delta` | privacy/approximate-only-delta | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Threshold tail accounting](#threshold-tail-accounting) |

## Analysis

### Distance normalization

The constructor invokes `match_group_by`, constructs a stable pre-grouped plan, and composes per-aggregate private expressions. The aggregate privacy map expects `(L0,L1,L∞)` group-distance bounds.

For the selected grouping keys, it reads `d_in.get_bound(by).num_groups` and `.per_group`, and reads total symmetric contributions from the empty-key grouping `d_in.get_bound(empty).per_group`. Independently, any domain `max_groups=G` caps changed group keys by `2G` (or `G` for a key-set invariant), and `max_length=K` caps per-group symmetric difference by `2K`. The implementation takes the minimum of independently valid bounds. If the total-change certificate is available, it supplies missing affected-group/per-group bounds; otherwise both those bounds are needed so the total can be bounded by their product. Insufficient bounds return an error. Checked multiplication means large certified bounds can result in an error instead of a wrapped small distance.

The code tightens `L0=min(L0,L1)`, `L∞=min(L∞,L1)`, then `L1=min(L1,L0*L∞)`. These ordered assignments need not produce the unique smallest mutually consistent triple; they need only remain conservative relative to the **true** distances. The [finite reference test](../../../../../../tools/tests/test_private_groupby_distance_model.py) evaluated **56,448** dataset/configuration pairs with explicit symmetric-multiset grouped differences and detected zero underestimates in the tested scope. The proof, dependency certificates and full `u32` execution remain unverified.

### Nested key dtype guards

The constructor certifies each grouping expression as stable, then rejects any resulting `Float16/Float32/Float64` key dtype, recursively including Array, List and Struct members, because Polars may reveal one original representative of signed zero or a NaN payload. It likewise rejects `Categorical` recursively because code assignment depends on input data. An explicitly cast non-floating/Enum key is considered under its resulting stable domain. The [existing upstream test source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/group_by/test.rs) includes direct/aliased float keys, nested float/categorical forms and permitted non-floating casts. This audit inspected those tests but did not run native Rust.

### Public, invariant and threshold branches

For an invariant key set (either `Keys` or `Lengths`) or an authorized public-key join, the map does not add a private key-release delta. The source matcher requires column-wise coalesced join keys covering **all** materialized grouping columns, excludes unsafe join options and aggregate-column collisions, and accepts Left/Right public-key joins. The constructor deduplicates the public key frame before joining and imputes absent private groups; this reduces disclosure through differing multiplicities. These are source-level guards, not a compiled Polars regression.

Otherwise the source requires an existing supported noisy-length filter or a constructor-provided threshold, and rejects a release lacking both a threshold and a public join. A threshold from an existing plan is preserved, with additional predicates conjunctively retained. If a constructor threshold is used, the plan adds a strict `count > threshold` filter.

### Threshold tail accounting

The privacy map rejects `threshold <= L∞`, computes the positive distance to instability `threshold - L∞`, and derives an upper probability `delta_single` for exceeding that bound from a discrete Laplace or Gaussian tail. Across `L0` potentially unstable group keys it charges `delta_joint = 1 - (1 - delta_single)^L0`. Only approximate measures can accept that extra delta: the pure-`MaxDivergence` and pure-`ZeroConcentratedDivergence` implementations of `ApproximateMeasure` reject it. The [finite model](../../../../../../tools/tests/test_private_groupby_distance_model.py) checks the exact rational joint-failure expression and the threshold-gap condition but **not** floating-point rounding or native noise-tail calculations.

## Findings and next checks

**No new confirmed defect in this bounded source and finite-model audit.** Its positive evidence is the 56,448-case group-distance reference model and source-visible rejection/sanitization paths, not a native OpenDP execution. The separate [upstream grouping-key issue #3082](https://github.com/opendp/opendp/issues/3082) was already resolved by [PR #3087](https://github.com/opendp/opendp/pull/3087); current audit [#91](https://github.com/opendp/opendp-audit/issues/91) independently reviews upstream `FrameDomain::get_margin` inference.

Run native OpenDP/Polars threshold and public-join tests, prove the complete noise-tail and composition contracts, and check large or inferred mixed grouping bounds. Source verification status remains **Partial** for privacy properties.
