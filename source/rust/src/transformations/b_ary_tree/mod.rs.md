---
schema_version: 1
source: rust/src/transformations/b_ary_tree/mod.rs
updated: 2026-11-23
---

# `rust/src/transformations/b_ary_tree/mod.rs`

## Scope and assumptions

- **Scope:** `make_b_ary_tree`, `checked_num_nodes_from_num_layers`, and `BAryTreeMetric` for output length, saturating-count arithmetic, and L1/L2 norm stability. This review explicitly examines the *current* implementation following [merged PR #3068](https://github.com/opendp/opendp/pull/3068).
- **Invariants:** For pairs of equal-length input integer vectors, changing a coordinate by magnitude `d` can change at most one tree node per layer, by at most `d` each; the vector output difference therefore has L1 norm at most `h*d` and L2 norm at most `sqrt(h)*d`, where `h` is the computed tree height. For arbitrary equal-length inputs, the bounds extend by coordinate replacement/triangle inequality with `d = ||x-y||_1`. The tree output's length equals the computed complete-tree node count minus omitted padding leaves.
- **Assumptions:** `TA` is a built-in integer with standard saturating-add semantics; the input `LpDistance` is finite only for **equal-length vectors**, per [its proof definition](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/mod.rs). We assume successful construction and allocation. This is **not** an audit of random noise or the complete DP pipeline.
- **Pinned sources:** [Tree implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/b_ary_tree/mod.rs), [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/b_ary_tree/test.rs), [metric definition](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/mod.rs), and [saturating arithmetic trait](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/arithmetic/mod.rs).
- **Coordination:** [Audit-task claim #24](https://github.com/opendp/opendp-audit/issues/24).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_b_ary_tree` | correctness/tree-output-shape | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Output shape and overflow guards](#output-shape-and-overflow-guards) |
| `checked_num_nodes_from_num_layers` | correctness/tree-node-overflow | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Output shape and overflow guards](#output-shape-and-overflow-guards) |
| `make_b_ary_tree` | privacy/tree-norm-stability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Saturating norm stability](#saturating-norm-stability) |
| `BAryTreeMetric::stability_constant` | privacy/tree-norm-stability | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Saturating norm stability](#saturating-norm-stability) |

## Analysis

### Output shape and overflow guards

The constructor rejects `leaf_count == 0` and `branching_factor < 2`. It computes `h = ceil(log_b(leaf_count)) + 1` with a saturating multiplicative search; then `checked_num_nodes_from_num_layers` uses `checked_mul` and `checked_add` to reject complete-tree node totals exceeding `usize`. Once that sum fits, the last-layer power `b^(h-1)` fits as well because it is a summand of the node count. The input function retains the first `leaf_count` supplied atoms, pads its final layer to the complete tree with zero values, computes ancestors, then drops exactly `num_leaves - min(leaf_count, input.len())` trailing padding leaves. The resulting length is `num_nodes - pad_length`.

The resulting output length can depend on the public input-vector length when that differs from `leaf_count`, but this is **not** an adjacent-dataset length leak under `LpDistance`: the metric definition assigns infinite distance to unequal-length vectors. Both equal-length input datasets have the same `pad_length` and output shape.

**Conclusion:** No node-count or shape discrepancy found for successful construction and integer vectors. **Audited** is limited to that arithmetic and shape invariant; huge allocations and platform-specific `usize` boundaries were not executed in compiled Rust.

### Saturating norm stability

For a fixed tree node, its value is a fold of `saturating_add` over a subset of leaves, possibly containing zeros. A saturating add with the other operand held fixed is a 1-Lipschitz map on integers; composing such operations preserves the single-coordinate bound. Each leaf contributes to exactly one ancestor in each of the `h` layers. Therefore replacing one leaf by a value at integer distance `d` can change at most `h` output nodes by at most `d` each. The output difference obeys `||Δtree||_1 <= h*d` and `||Δtree||_2 <= sqrt(h)*d`. Arbitrary input pairs of the same length follow by replacing changed leaves one by one and applying the triangle inequality. Inputs beyond `leaf_count` are ignored; zero padding and dropping unused final leaves are non-expansive operations.

The source returns `h` for `L1Distance` and `inf_sqrt(inf_cast(h))` for `L2Distance`; its directed rounding is conservative if the `InfCast` and `InfSqrt` contracts hold. For a negative input distance, the stability map's arithmetic may error, rather than implying a valid adjacency bound. This review does not independently verify all numeric conversion backends.

**Independent executed model:** A Python 3 standard-library model of the *source algorithm*, using signed `i8` saturation, enumerated `leaf_count=1..5`, branching factors `b=2..4`, input lengths from zero through `min(leaf_count+2, 4)`, and per-coordinate mutations over values `{-128,-127,-1,0,1,126,127}`. It checked **793,548** single-coordinate changes: every output length matched the node-count formula and every L1 and squared L2 difference satisfied the stated bounds. No counterexample was found. A shorter **102,060-case regression slice** is checked in at [`tools/tests/test_bary_tree_stability_model.py`](../../../../../tools/tests/test_bary_tree_stability_model.py) for automated audit-repository execution.

**Limitations:** The model is not a compiled OpenDP Rust invocation; all `TA` types, `QI/QO` combinations, extreme directed rounding, heap allocation errors, and the related consistency postprocessor remain untested. Hence the full norm property is **Partial**.

## Findings

No new defect established under the declared equal-length L1/L2 stability and output-shape conditions. The earlier [upstream issue #2924](https://github.com/opendp/opendp/issues/2924) (L2 map) and [#2925](https://github.com/opendp/opendp/issues/2925) (integer overflow) were fixed by [merged PR #3068](https://github.com/opendp/opendp/pull/3068) before the pinned upstream revision. [PR #3076](https://github.com/opendp/opendp/pull/3076) was closed without merge; it must not independently be counted as a merged fix. No new defect issue was warranted within this scope.

## Next checks

- Run the pinned OpenDP Rust test suite, particularly signed extrema, incomplete trees, and `L1Distance` to `L2Distance` cases.
- Independently verify `saturating_add`, `InfCast`, and `InfSqrt` numeric contracts for all supported input/output types at extreme parameter values.
- Review the separate `make_consistent_b_ary_tree` postprocessor and finite-dtype handling in a distinct audit.
