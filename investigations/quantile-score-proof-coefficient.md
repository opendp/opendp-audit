---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Quantile score coefficient differs between Rust and proof theorem

## Invariant and threat model

Quantile candidate score calculations and their stability proofs must describe the same function. A proof that establishes a formula different from the implementation does not by itself certify the implementation, even if the implemented sensitivity bound happens to be safe. The relevant property is the `LInfDistance` sensitivity of the score vector, which affects the privacy map of private quantile selection.

## Affected symbols and source audits

- [Source audit of `score_candidates` and `score_candidates_map`](../source/rust/src/transformations/quantile_score_candidates/mod.rs.md).
- [Upstream Rust implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/quantile_score_candidates/mod.rs).
- [Incorrect proof theorem](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/quantile_score_candidates/score_candidates.tex), [constructor proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/quantile_score_candidates/make_quantile_score_candidates.tex), and [sensitivity proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/quantile_score_candidates/score_candidates_map.tex).
- [Private quantile caller](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/private_quantile/mod.rs).

## Reproduction and evidence

1. Rust returns the absolute difference of `(alpha_den - alpha_num) * min(lt, l)` and `alpha_num * min(gt, l)`, where `lt=#(x<c)` and `gt=#(x>c)`.
2. The theorem in `score_candidates.tex` states the first term as `alpha_den * min(lt, l)`. For `x=[0]`, candidate `c=1`, `alpha_num=1`, `alpha_den=2`, and cap `l=1`, Rust produces score `1`, whereas the theorem states `2`.
3. The introduction of `make_quantile_score_candidates.tex` initially derives the rank-distance formula correctly but later repeats the inconsistent truncated-score equation. The independent sensitivity proof in `score_candidates_map.tex` also uses the equivalent expression `alpha_den * lt - alpha_num * (n - count_eq)` before truncation; this matches `(alpha_den - alpha_num)*lt - alpha_num*gt` without independent capping. The proof artifacts therefore need to be reconciled rather than mechanically copying one equation.
4. [Independent executable Python tests](../tools/tests/test_quantile_score_model.py) translate the Rust histograms and independently evaluate the desired score formula. All 600 small dataset/alpha/cap cases agree. Exhaustive comparison of 24,000 ordered pairs also found no violation of the unsized stability bound `d * max(alpha_num, alpha_den-alpha_num)` or the fixed-size bound `(d//2)*alpha_den` for equal-size datasets.
5. The stability result is supported analytically: a single added or removed record changes one of the capped `<` or `>` counts by at most one, so its effect is at most the relevant coefficient. A fixed-size replacement can be charged as one deletion and one insertion, hence the bound `alpha_den` per replacement. This is evidence for soundness within the stated model, not a compiled regression nor a proof of all upstream numeric and constructor assumptions.

## Finding and disposition

**Proof artifact mismatch confirmed at pinned upstream `main`**, with a one-record counterexample. The implementation's stated sensitivity bound passed independent finite-model testing, so **no privacy violation was confirmed**. Impact is proof correctness and reviewability; no release behavior defect was established for the reviewed scoring function. **Upstream disposition: Unreported.** No matching issue or corrective PR was identified for this specific missing-coefficient discrepancy. [OpenDP issue #2075](https://github.com/opendp/opendp/issues/2075) requests general proof review and removal of `\\contrib`, but its body does **not** describe this coefficient mismatch and must not be treated as an equivalent defect report. [PR #2105](https://github.com/opendp/opendp/pull/2105) closed without merge; [PR #2357](https://github.com/opendp/opendp/pull/2357) merged other scoring changes, but this proof discrepancy persists in the pinned upstream revision. No new issue or PR was opened under this audit's restrictions.

## Unresolved questions

- Align the theorem's first coefficient and constructor proof's truncated formula with the Rust scorer, including the correct `lt` and `le` histogram descriptions.
- Compile and run the upstream Rust proof witness, and extend tests to large numeric boundaries and `score_candidates_constants`' denominator approximation.
- Verify all dependencies of private quantile selection end to end; this investigation is `Partial` rather than a formal privacy certification.
