---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Partial
---

# Resize with unordered inputs: sampling and metric conversion

## Invariant and threat model

The reviewed constructor is `make_resize` with `MI = SymmetricDistance`, public target length `s > 0`, and `MO` either `SymmetricDistance` or `InsertDeleteDistance`. Input and output domains contain vectors of the same atom type, with a validated public padding constant. This audit is restricted to successful invocations with well-behaved atom cloning and ideal independent uniform random draws.

**Invariant:** For adjacent inputs with multiset symmetric distance 1, the output distributions admit a coupling supported entirely on pairs of outputs whose `MO` distance is at most 2. Input multiset distance 0 must induce the same output distribution, modulo output metric. A chain of `k` single-record edits then admits a coupling of output distance at most `2k`. Importantly, this is an *existential coupling* and **not** a bound on two independently randomized invocations.

## Affected symbols and source audits

- [Resize source audit](../source/rust/src/transformations/resize/mod.rs.md) and [upstream resize implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/resize/mod.rs).
- [Uniform integer sampler](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/uniform/mod.rs) (`sample_uniform_uint_below`), and [shuffle sampler](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/mod.rs) (`Shuffle`).
- [Existing sampler coverage](../source/rust/src/traits/samplers/mod.rs.md) assesses the shuffle/entropy prerequisites as Partial; this investigation does not upgrade their status.
- [Metric definitions](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/mod.rs) and [stability-map constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs).

## Reasoning and evidence

### Reservoir sampling and output law

The code initializes its reservoir to the first `s` entries. For each input index `i >= s`, it samples `j` uniformly from `[0, i]`, replacing reservoir slot `j` only if `j < s`. Induction over `i` proves that each labeled `s`-element subset of `n >= s` records is selected with probability `1 / C(n,s)`. The internal reservoir slot order is **not** necessarily uniform; that is harmless for the unordered output metric. If output is ordered, `Shuffle` makes the conditional ordering uniform.

When `n < s`, the function pads the original `n` elements with `s-n` copies of the public constant. With ordered output, it shuffles all `s` positions uniformly. Values with the same atom representation are treated as distinct labeled occurrences for the proof.

### Coupling proof across all target boundaries

Consider neighboring input multisets `X` and `Y=X+{z}`, using labels to distinguish repeated records.

- **`|X| >= s`:** Draw one uniform permutation of the labeled `Y` elements. For `Y`, take the first `s` labels. For `X`, remove the new label `z` from this permutation and take the first `s` remaining labels. Both marginals are uniform ordered samples of the appropriate multiset. If `z` fell beyond position `s`, outputs coincide; otherwise deleting `z` from the `Y` prefix and inserting the next surviving element yields the `X` prefix, with ordered insert-delete distance at most 2.
- **`|X| < s`:** Pad each input to `s` labeled slots. Pair all shared records and all but one padding label. The last padding label in `X` corresponds to `z` in `Y`. Apply the same uniform permutation to both padded lists. The outputs differ at one position, giving insert-delete distance at most 2.

Projecting these coupled ordered samples onto multisets yields a symmetric-distance cost of at most 2. Symmetric edit paths extend the result to distance `k` via the triangle inequality. For `d=0`, two input permutations share the same labeled multiset; reservoir selection (for unordered output) and reservoir selection followed by uniform shuffle (for ordered output) have identical laws. The constructor's `StabilityMap::new_from_constant(2)` returns a conservative checked bound where arithmetic succeeds.

The output domain property also follows: every successful output consists solely of valid input atoms and copies of the validated constant, with exactly `s` positions.

### Executed finite model checks (2026-11-22)

A Python 3 independent model was actually executed locally. It used `fractions.Fraction` for exact reservoir-state and output probabilities; enumerated candidate ordered samples and permutations; computed insert-delete distance via longest common subsequence; and checked whether an integer-capacity maximum-flow network could transport all output probability mass across edges with output distance at most 2.

| Check | Coverage | Result |
| --- | --- | --- |
| Ordered-prefix insert-one edits | Inputs length 0 through 6, alphabet {0,1,2}, targets 1 through 4 | 85,296 passed |
| Reservoir subset uniformity | All `1 <= s <= n <= 7`, rational probabilities | 28 passed |
| Equal-multiset output law | Unordered input pairs over {0,1}, length at most 4, targets 1 through 4, both output metrics | 520 passed |
| One-edit output coupling | Same domain/targets, both output metrics, rational max-flow feasibility | 784 passed |

An initial exploratory edit-distance recurrence was incorrect and was replaced with the LCS-based metric **before** these passing counts were obtained. This was independent Python modeling only: no Rust code was compiled or invoked.

## Findings

No counterexample or new defect was identified in the examined source-level model, under independent exact-uniform sampling. The previously discovered ordered-to-ordered shuffle defect [issue #2927](https://github.com/opendp/opendp/issues/2927) was fixed by merged [PR #3080](https://github.com/opendp/opendp/pull/3080), while a broader resize proof is still tracked as upstream [issue #120](https://github.com/opendp/opendp/issues/120).

## Unresolved questions

- Verify sampler and `Shuffle` uniformity in the actual configured Rust runtime. Existing [sampler audit](../source/rust/src/traits/samplers/mod.rs.md) is Partial, so the present status also remains Partial.
- Run upstream Rust resize regression tests and add randomized, metric-specific property checks.
- Audit ordered-to-unordered conversion separately, and treat entropy errors, timing, allocation failures, and user-supplied clone behavior as distinct properties.
