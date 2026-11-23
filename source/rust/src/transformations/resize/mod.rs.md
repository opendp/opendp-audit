---
schema_version: 1
source: rust/src/transformations/resize/mod.rs
updated: 2026-11-22
---

# `rust/src/transformations/resize/mod.rs`

## Scope and assumptions

- **Audit scope:** Ordered-to-ordered prefix resizing plus unordered-input reservoir sampling with either `SymmetricDistance` or `InsertDeleteDistance` output. Ordered-to-unordered conversion is not reviewed.
- **Invariants:** Every successful output has length `size` and valid atoms. Ordered-to-ordered outputs deterministically satisfy `d_ID(output(x), output(y)) <= 2 * d_ID(x,y)`. For the two randomized unordered-input routes, the output distributions must admit a coupling with metric distance at most twice the input multiset symmetric distance; multiset-equivalent inputs must induce identical output laws modulo the output metric.
- **Assumptions:** `size > 0`; `constant` is in the element domain; input vectors satisfy `input_domain`; `TA::clone` preserves values and membership. The unordered-input argument is conditional on exact-uniform, independent reservoir-index draws and a uniform final permutation. It excludes entropy failures, timing channels, panics, and failed allocation.
- **Reviewed upstream revision:** `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` (2026-11-22 audit snapshot).
- **Source links:** [resize implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/resize/mod.rs), [metric definitions](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/mod.rs), [stability-map implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs), and [upstream resize tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/resize/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `transformations::resize::make_resize` | privacy/stability | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Ordered-to-ordered stability argument](#ordered-to-ordered-stability) |
| `transformations::resize::make_resize` | correctness/domain-membership | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Output domain argument](#output-domain-membership) |
| `transformations::resize::make_resize` | privacy/stability-unordered-unordered | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Coupling investigation](../../../../../investigations/resize-unordered-stability.md) |
| `transformations::resize::make_resize` | privacy/stability-unordered-ordered | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Coupling investigation](../../../../../investigations/resize-unordered-stability.md) |

## Analysis

### Ordered-to-ordered stability

**Conclusion (scoped):** No violation of the factor-two insert-delete stability map was identified for `MI = MO = InsertDeleteDistance`, provided the function returns successfully.

The `IsMetricOrdered` implementation sets `MI::ORDERED = true` and `MO::ORDERED = true`. Consequently, the reservoir-sampling branch (`arg.len() > size && !MI::ORDERED`) and the final shuffle (`!MI::ORDERED && MO::ORDERED`) are both unreachable. The result is the first `size` input elements, padded with copies of `constant` if shorter. It is deterministic.

For a single insertion into a valid input `x` to obtain `y`, consider the two equal-length outputs of length `s = size`:

- If `len(x) >= s`, inserting before the truncation boundary either leaves the prefix unchanged or inserts one element and displaces at most the final prefix element. The outputs share an order-preserving subsequence of length at least `s - 1`.
- If `len(x) < s`, the old output contains `x` followed by padding. The new output contains the same `x` as a subsequence, plus one inserted element and one fewer padding element. Again the outputs share a subsequence of length at least `s - 1`.

Since both outputs have length `s`, a common subsequence of length `s - 1` implies insert-delete distance at most 2. Deletions are symmetric. A path of `k` insertions/deletions and the triangle inequality give `d_ID(resize(x), resize(y)) <= 2k`. The constructor's `StabilityMap::new_from_constant(2)` implements upward-checked distance scaling, returning an error if arithmetic cannot provide the bound.

The constant is tight: with `size = 2`, `constant = 0`, `x = [1, 2]`, and `y = [0, 1, 2]`, the input distance is 1, whereas outputs `[1, 2]` and `[0, 1]` have insert-delete distance 2.

**Executed evidence:** An independent Python reimplementation of only this deterministic branch exhaustively checked 85,296 insert-one neighbor/target combinations: input lengths 0 through 6, alphabet `{0, 1, 2}`, targets `{1, 2, 3, 4}`. An edit-distance dynamic program checked that each output pair is at distance at most 2; all checks passed. The same model checked output length and element membership. These are model checks, **not Rust executions or differential tests against compiled OpenDP**.

**Existing upstream context:** [Issue #2927](https://github.com/opendp/opendp/issues/2927) described an earlier order-dependent shuffling failure, fixed by merged [PR #3080](https://github.com/opendp/opendp/pull/3080). The reviewed revision contains the conditional shuffle. The earlier stability-constant correction is [issue #355](https://github.com/opendp/opendp/issues/355). [Issue #120](https://github.com/opendp/opendp/issues/120) tracks a broader resize proof.

### Output domain membership

**Conclusion (scoped):** The successful result has the declared output length and element-domain membership in all three reviewed metric combinations, assuming the input-domain and `Clone` contracts hold.

Construction rejects `size == 0` and checks `input_domain.element_domain.member(&constant)`. The declared output domain uses `input_domain.with_size(size)`. The execution first reserves space for `size` elements, copies at most the first `size` valid input atoms, and pads any remainder with validated copies of `constant`. For unordered input, reservoir replacement preserves length and selects only input atoms, while final shuffling permutes the vector. Hence every successful result has length `size` and contains only members of the element domain. The reviewed Rust tests cover ordered prefix preservation and excessive requested size returning a `FailedFunction` error; they are not newly executed tests in this audit.

**Limitations:** The separate [unordered-input investigation](../../../../../investigations/resize-unordered-stability.md) addresses sampling distributions and their two output metrics under ideal-uniform sampling. It remains Partial because upstream `Shuffle`/entropy assumptions were not independently validated in a compiled Rust execution. Ordered-to-unordered conversion, timing channels, cloning panics, FFI conversions, and allocation failures remain unchecked. No upstream Rust test target was executed.

## Unordered-input investigation

For `MI = SymmetricDistance`, the implementation uses reservoir sampling without replacement only when input length exceeds the target. With `MO = InsertDeleteDistance`, it additionally shuffles the resulting vector. Under independent, exact-uniform randomness, adjacent multiset inputs can be coupled to outputs differing in at most one replacement (symmetric metric) or one insertion and deletion (ordered metric). Equal-multiset input permutations induce the same output law after shuffle. The [cross-file investigation](../../../../../investigations/resize-unordered-stability.md) gives an explicit coupling by shared labeled-record permutations, examines padding/truncation boundaries, and records exact finite checks.

**Executed checks, 2026-11-22:** A local Python reference model (not compiled Rust) passed 28 exact-rational reservoir-uniformity cases; 520 multiset-equivalence distribution comparisons; and 784 adjacency distribution-coupling feasibility checks using rational probabilities and integral max flow. The previously described 85,296 ordered insert-neighbor checks were also independently executed using an LCS-based insert-delete distance. There were no counterexamples within these finite cases.

**Status:** Partial for both unordered-input stability properties until actual Rust sampler/shuffle contracts and error behavior are checked. No new candidate defect was identified.

## Next checks

- Run compiled upstream Rust resize tests and supplement with metric-specific adjacent-input property tests.
- Independently validate the uniformity/error semantics of the sampler and `Shuffle`; see [existing sampler coverage](../../../../../source/rust/src/traits/samplers/mod.rs.md).
- Review ordered-to-unordered conversion and separately assess entropy, timing, custom clone, and resource-failure behavior.
- No new defect was identified in the stated source-level scopes. No audit-task issue or exclusive claim was created for this run.
