---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Polars private group-by: grouped-distance certificates and key release

## Invariant and threat model

The non-deprecated `make_private_group_by` constructs a release of private aggregates together with the grouping keys. Its privacy map must not underestimate the number of affected groups (`L0`), total changed rows (`L1`), or per-group changed rows (`L∞`). Independently, a release of **private** group keys needs a threshold with a joint failure probability accounted for in approximate DP, or a join against a genuinely **public** key set. This investigation checks the source-level bound normalization and release gates; it does **not** prove the privacy of noise samplers, Polars query execution, or arbitrary domain descriptors.

## Affected symbols and pinned evidence

- [Private group-by source report](../source/rust/src/measurements/make_private_lazyframe/group_by/mod.rs.md) and [implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/group_by/mod.rs): `make_private_group_by`, `contains_float`, `contains_categorical`, `integrate_discrete_noise_tail`.
- [Matcher](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/group_by/matching.rs): `match_group_by`, `find_len_expr`, `is_threshold_predicate`, `KeySanitizer`.
- [Domain margins and invariant definition](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/frame/mod.rs): `get_margin`, `Invariant::Keys`, `Invariant::Lengths`. Both invariant variants guarantee identical group keys; the stronger Lengths variant **also** fixes group lengths.
- [Native upstream group-by tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/group_by/test.rs) and [proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_lazyframe/group_by/make_private_group_by.tex).
- [Executable finite grouped-distance model](../tools/tests/test_private_groupby_distance_model.py).

## Source-level reasoning

### Aggregate privacy-map distance triple

The constructor first creates a stable transformation for the pre-grouped input, checks every grouping key through the row-wise stability rules, and builds per-aggregate private expressions. It composes the aggregate measurements, keeping their combined privacy map. The output key release is handled independently.

For any group-key tuple `by`, the map retrieves certified bounds from `d_in.get_bound(by)`: affected groups `b0` and per-group contributions `bi`. It retrieves total contributions `b1` from the bound over the empty key set. Independently, a public domain margin with at most `G` groups in either dataset limits affected groups to `2G`; when the **key set is invariant**, at most `G` groups can change. A public maximum group size `K` limits per-group symmetric difference to `2K`. These valid caps are combined by the minimum of available certificates.

The code fills missing bounds as follows: when `b1` is known, it provides a fallback upper bound for missing `L0` or `L∞`; when both `L0` and `L∞` are known, it can set `L1 ≤ L0 * L∞`. Without either combination it fails with `FailedMap`. Once concrete, it tightens `L0` and `L∞` by `L1`, then `L1` by their product. All multiplications use checked error paths. A returned triple must **dominate the true grouped distances**; it need not be a self-consistent least solution because the last tightening can reduce `L1` after the other bounds have been fixed. No such loose tuple was interpreted as a privacy undercount.

### Finite executable evidence

The independent [four-test Python model](../tools/tests/test_private_groupby_distance_model.py) faithfully represents the **integer normalization branch** but does not invoke native Rust. It enumerates all 84 row multisets of size at most three over three grouping keys and two distinguishable values, every ordered pair of these datasets, and eight independently chosen combinations of certificate availability, public margin caps, and valid key-set invariants. It verifies the returned `L0/L1/L∞` bounds dominate each pair's **exact multiset symmetric differences**, including pairs whose group sets differ.

**56,448 paired input/configuration checks passed locally**, with no returned bound below the actual grouped distance. Three further tests verify: missing necessary certificates fail closed; overflow when doubling public caps or multiplying large contributions is rejected; and a threshold `T` must exceed `L∞`, while the joint key-failure probability `1-(1-p)^L0` for rational `p=1/7` stays between zero and the union bound `min(1,L0*p)`. The model tests the algebraic probability expression, **not** the conservativeness of the native discrete noise tail or floating-point implementation.

### Key sanitization and privacy cost

Grouping-key dtypes containing Float16/32/64 (including nested Array/List/Struct) are rejected because Polars may output an original representative of signed zero or NaN. Data-dependent Categorical key encodings are likewise rejected recursively; deterministic public Enum mappings are not categoricals. The native Rust tests cover these rejections.

The matcher recognizes either an outer public-key join or a filtering threshold around the group-by. For a public join it requires supported Left/Right options, coalesced **column** join keys matching *all* grouping columns, no collisions with aggregate output columns and no join slicing; the constructor deduplicates public keys and imputes aggregates for groups absent in the private input. These guards are visible in source and verified by native *test definitions* but were not executed by this review.

For unknown private key sets without a public join, the constructor requires a DP length expression and a positive gap `T - L∞` before computing a discrete Laplace/Gaussian upper-tail bound `p`. It adds `delta_joint = 1-(1-p)^L0` to an **approximate** privacy measure; pure `MaxDivergence` and `ZeroConcentratedDivergence` reject private key-release deltas. If neither a threshold nor a suitable public key join is supplied, construction fails. Invariant key sets skip this extra delta because they are shared across neighboring datasets.

### Related existing fixes and nonoverlap

The historical Polars expression-based grouping/truncation key mismatch was reported as [upstream #3082](https://github.com/opendp/opendp/issues/3082) and fixed by merged [PR #3087](https://github.com/opendp/opendp/pull/3087). Separate current audit [task #91](https://github.com/opendp/opendp-audit/issues/91) studies `FrameDomain::get_margin` tie-break/overflow inference. This investigation **assumes provided domain margins are valid**, rather than re-auditing the correctness of their inference; it does not duplicate either concern.

## Findings

**No new defect confirmed** in the finite group-distance conversion, source-visible key dtype guards, threshold/join branches, or missing-certificate paths. The 56,448-case model offers numerical support only for small keys, short datasets, and valid certificates. This is a **Partial** privacy review, not proof of the full group-by mechanism or a statement that compiled OpenDP passed.

## Next decisive checks

Run pinned native OpenDP/Polars grouping tests, including the pure-versus-approximate key-release gate, public-join deduplication and imputation, threshold-tail calibration at very small deltas, nested key dtypes, and large `u32` boundaries. Verify any changes to `FrameDomain::get_margin` separately under the existing #91 claim.
