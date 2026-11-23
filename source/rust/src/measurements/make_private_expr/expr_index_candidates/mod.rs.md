---
schema_version: 1
source: rust/src/measurements/make_private_expr/expr_index_candidates/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/make_private_expr/expr_index_candidates/mod.rs`

## Scope and assumptions

- **Scope:** Non-deprecated `make_expr_index_candidates`, `match_index_candidates`, `IndexCandidatesShim`, `IndexCandidatesPlugin`, and `index_candidates_udf`, including the normal `dp_quantile` caller and `Measurement >> Function` postprocessing semantics. This review covers public candidate lookup, output schema, and privacy-map preservation, **not** the underlying noisy-max selection guarantee.
- **Invariant:** Lookup must depend only on a DP-released index and a public, fixed candidate `Series`; the lookup must not modify the underlying measurement's privacy guarantee. A valid index returns the corresponding candidate. Invalid indices may return errors, but those errors must be a function of already-released indices and public candidates, not of unreleased source data.
- **Assumptions:** The `candidates` expression is a public literal extracted by `literal_value_of::<Series>`; the `PrivacyMap` of the prior measurement is sound; Polars `Series::take` implements indexed selection; the plugin is executed as postprocessing only after the private expression is rewritten.
- **Pinned source:** [Index-candidates implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_index_candidates/mod.rs), [quantile caller](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_dp_quantile/mod.rs), [postprocessing composition](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/mod.rs), [upstream Rust tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_index_candidates/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_expr_index_candidates` | privacy/postprocessing-map-preservation | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Privacy map](#privacy-map) |
| `match_index_candidates` | correctness/public-candidate-precondition | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Candidate construction](#candidate-construction) |
| `IndexCandidatesPlugin::get_field` | correctness/schema-consistency | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Schema and evaluation](#schema-and-evaluation) |
| `index_candidates_udf` | correctness/index-lookup-and-errors | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Schema and evaluation](#schema-and-evaluation) |

## Analysis

### Privacy map

`make_expr_index_candidates` first calls `input.clone().make_private(...)`, obtaining a private measurement of the **index**. It then composes `m_prior >> Function::then_expr(...)`. The `Shr<Function>` implementation invokes `make_chain_pm`; that constructor chains the functions but **clones** the original measurement's privacy map. The resulting `IndexCandidatesPlugin` receives the already-private index expression and a `Series` extracted from the public expression literal. Thus no new private-data access or privacy charge is introduced in the audited construction. The argument is conditional on the upstream private-index measurement being sound; the noisy-max mechanism itself is out of scope.

A finite rational probability model confirmed that deterministic candidate-value mapping, including duplicate candidate labels, does not increase maximal probability ratios for 729 ordered pairs of 3-point positive distributions (three candidate maps each). This is a supporting mathematical check, not a proof of OpenDP's mechanism-level privacy guarantee. See [investigation](../../../../../../investigations/polars-index-candidates-postprocessing.md) and [reference tests](../../../../../../tools/tests/test_index_candidates_postprocessing_model.py).

### Candidate construction

`match_index_candidates` requires a recognized shim and exactly two arguments, with `candidates` extractable as `literal_value_of::<Series>`. It therefore **does not accept** an arbitrary data-dependent candidate series as a runtime input. The `dp_quantile` caller additionally computes a median and rejects missing/empty candidates before building the score and noisy-max pipeline. The generic helper does not itself reject an empty candidate series; with an actual index this can lead to an out-of-bounds Polars error, but that error is deterministic postprocessing of the private index and public candidates. Without evidence of an unguarded supported caller requiring a nonempty candidate set, this is recorded as an API limitation rather than a distinct confirmed defect.

### Schema and evaluation

`IndexCandidatesPlugin::get_field` announces the stored public candidates' dtype and preserves the index expression's column name. The FFI `index_candidates_plugin_type_udf` additionally checks for `UInt32` inputs. At evaluation, `index_candidates_udf` checks for exactly one `Column`, calls `column.u32()?`, uses `kwargs.candidates.0.take(...)` and returns the selected values with the index column's name. Out-of-bounds indices and non-u32 inputs are handled as Polars errors rather than unchecked indexing. The index is produced by `NoisyMaxPlugin` in the standard `dp_quantile` pipeline; the structural equal-length candidate/score premise was inspected but not exhaustively proved for every Polars optimizer rewrite.

**Executed:** Six Python standard-library tests covering valid candidate indices up to length five, duplicate candidates, invalid values, nullable-index model semantics, finite rational postprocessing ratios, and identity of the privacy-map model. **Not executed:** Native OpenDP/Polars, FFI serialization, chunked data, or actual `Series::take` error propagation. The existing upstream native tests were inspected, not run. This limits the non-privacy correctness claims to **Partial**.

## Next checks

- Run native Polars UDF tests for out-of-range/null indices, empty candidates, chunked columns, and nested candidate dtypes, including FFI output schema.
- Verify that candidate length matches score-array length after Polars optimizer rewrites in the full `dp_quantile` pipeline; this report does not certify arbitrary custom private-index generators.
- **Finding:** No distinct correctness or privacy bug established within the stated scope. No new candidate issue filed. The standard path meets the source-level deterministic-postprocessing invariant, conditional on the prior index mechanism.
