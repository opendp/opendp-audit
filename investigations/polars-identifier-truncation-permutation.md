---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Polars identifier truncation: permutation invariance and rank provenance

## Scope, invariant and existing upstream tracking

This investigation reviews the **current non-deprecated** identifier-truncation matcher and its measurement-free stable-transformation consumer at `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`. Under `SymmetricIdDistance`, datasets differing only by row permutation *within the same identifier* have distance zero. A deterministic stable truncation must therefore produce an equivalent output at distance zero. Merely bounding the number of retained rows or groups is insufficient if the identity of retained records depends on order.

- [Matcher source audit](../source/rust/src/transformations/make_stable_lazyframe/truncate/matching/mod.rs.md), [pinned source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/truncate/matching/mod.rs).
- [Truncation constructor audit](../source/rust/src/transformations/make_stable_lazyframe/truncate/mod.rs.md), [pinned source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/truncate/mod.rs).
- [Metric definition](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/polars/mod.rs), [native matcher tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/truncate/matching/test.rs).
- [Independent reference model](../tools/tests/test_polars_truncation_permutation_model.py).
- Already open [upstream issue #3157](https://github.com/opendp/opendp/issues/3157) (“Permutation invariance should be enforced within truncation ops”), open [PR #3158](https://github.com/opendp/opendp/pull/3158) (“enforce permutation invariance in truncation”), and open [PR #3270](https://github.com/opendp/opendp/pull/3270) (“harden truncation matching”). Earlier computed-key bug [#3082](https://github.com/opendp/opendp/issues/3082) was fixed in merged [PR #3087](https://github.com/opendp/opendp/pull/3087).

## Source-level counterexample 1: ordinal within-partition truncation

The matcher accepts a predicate of the form `int_range(0,len(),1,Int64).over([identifier,key]) < k` and recognizes it as a per-identifier/per-key row cap. The associated numeric bound can be correct: at most `k` rows per identifier/key survive. Nevertheless, row positions are not inherent in a bag-of-rows identifier metric.

Consider identical unordered records belonging to identifier 7, group `a`, with private values `10,20,30`. With `k=1`, a positional enumeration keeps the first row. In order `[10,20,30]`, the retained sum is 10; in order `[30,20,10]`, the retained sum is 30. The input unordered-id distance is zero, yet the deterministic post-truncation aggregate differs. Thus a bound on **the number** of contributions does not establish the necessary permutation-invariant function.

This is an exact counterexample in an independent positional-enumeration model and a source-supported issue: the source admits that shape and the consumer replays the original predicate. No native OpenDP/Polars runtime was exercised, so exact execution semantics and exploitability on the pinned library are not asserted. The deficiency is specifically tracked in upstream **#3157 / PR #3158**.

## Source-level counterexample 2: untracked rank field

For dense-rank num-groups truncations, the matcher accepts a struct whose first field hashes a second struct of grouping keys, then describes the returned bound using only those inner grouping keys. At the pinned revision it does not require exactly two outer fields or a single hash input before ignoring the outer rank struct. A third positional field can therefore distinguish rows with identical keys. An idealized dense rank over `(hash(key),key,position)` with threshold 1 selects the first among two same-key records with values 10 and 20. Reordering those records can select the other value. This is another conditional violation of permutation invariance; the extra field is absent from the asserted certificate.

Open **PR #3270** adds a shape/arity check and schema-based categorical-key rejection; it also validates matched bounds against the stabilized schema and compares stabilized grouping expressions to their executed forms. These changes target the identified matcher-contract risk. This audit does not claim the PR has been merged or passed every integration test.

## Numeric sanity: thresholds and conjunctions

The comparison parser normalizes `<k` (or reversed `k>over`) to bound `k`, and `<=k` (or reversed `k>=over`) to `k+1` using fallible directed addition. On a zero-based per-group ordinal, these are exact upper cardinality limits. On a one-based dense rank, the current bounds are conservative by one; open PR #3270 tightens dense ranks. Positive upper-bound slack is a utility issue, not a privacy undercount.

Four independent `unittest` tests **passed locally**:
1. Six permutations of a three-row same-ID/same-group dataset and caps `k∈{1,2}` yielded different retained sums despite equal unordered records; every retained set still honored its row cap.
2. Two permutations of same-key values `10,20` with an extra positional rank field yielded different retained values.
3. **9,792** bound comparisons across row/group counts 0–33, thresholds 0–35, four comparator orientations, and both zero-/one-based indexes; **all conservative**. Additional checks cover `u32::MAX` inclusive overflow rejection.
4. Conjunction recognition only yields both modeled certificates if all child predicates are recognized.

The [Python model](../tools/tests/test_polars_truncation_permutation_model.py) does not execute Polars rank/window semantics, native type coercion, or the full stable-truncation constructor.

## Disposition and privacy status

**Source-supported existing privacy defect, not newly unreported.** Upstream issue #3157 and open PRs #3158/#3270 already address the relevant hardening, so **no duplicate defect issue** should be created in the audit repository. [Audit task #67](https://github.com/opendp/opendp-audit/issues/67) coordinates this review.

Current privacy status is **Partial**, with a demonstrated mathematical zero-distance counterexample under source-accepted positional semantics. The decisive next step is executing native Rust/Polars tests on two row permutations, and then verifying that the proposed PRs reject or safely transform these inputs. No upstream code was modified.
