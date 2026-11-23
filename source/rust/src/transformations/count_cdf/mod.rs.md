---
schema_version: 1
source: rust/src/transformations/count_cdf/mod.rs
updated: 2026-11-22
---

# `rust/src/transformations/count_cdf/mod.rs`

## Scope and assumptions

- **Scope:** Input-shape and numerical-parameter validation for the non-deprecated histogram postprocessors `make_cdf` and `make_quantiles_from_counts`, specifically whether successful construction followed by evaluation can panic on accepted inputs. This review does not assess the privacy of upstream noisy counts or the utility of interpolation on typical data.
- **Invariant:** For input shapes accepted by the constructor and its documented generic constraints, the returned `Fallible<Function>` must handle invalid or empty inputs with a returned error or a defined result, not an unchecked vector index panic. Quantile requests are expected to be finite and in `[0, 1]`, and bin edges must be strictly ordered.
- **Assumptions:** `TA` is a supported float for `make_cdf`; for the quantile witness, `TA = F = f64` and `Interpolation::Nearest` or `Linear` as supported by the function. The witnesses only require ordinary IEEE-754 NaN comparisons and Rust vector indexing behavior.
- **Pinned upstream:** [Rust postprocessors](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/count_cdf/mod.rs), [FFI constructors](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/count_cdf/ffi.rs), and [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/count_cdf/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_cdf` | correctness/empty-input-panic | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Empty CDF input](#empty-cdf-input) |
| `make_quantiles_from_counts` | correctness/degenerate-histogram-panic | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Accepted zero-interior-bin shape](#accepted-zero-interior-bin-shape) |
| `make_quantiles_from_counts` | correctness/quantile-parameter-validation | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [NaN validation bypass](#nan-validation-bypass) |
| `make_cdf` | correctness/zero-total-normalization | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Normalization assumptions](#normalization-assumptions) |

## Analysis

### Empty CDF input

`make_cdf::<f64>()` constructs a fallible function without restricting the input length. On evaluation with `arg = []`, `.scan(...).collect::<Vec<_>>()` produces an empty `cumsum`, then `let sum = cumsum[cumsum.len() - 1]` performs an unchecked index with `cumsum.len() == 0`. In Rust, this panics (via usize subtraction overflow or the out-of-bounds index) instead of returning `Err`. A valid, nonempty input does not encounter this particular index error. The FFI constructor exposes the same function and adds no length constraint. **Source-level panic witness:** `make_cdf::<f64>()?.eval(&vec![])`.

### Accepted zero-interior-bin shape

`make_quantiles_from_counts` only rejects an *empty* `bin_edges` vector. With `bin_edges = [5.0]`, `alphas = [0.5]`, and an input histogram `arg = [7.0, 9.0]`, the runtime `abs_diff(bin_edges.len(), arg.len()) == 1` guard passes. As `arg.len() == bin_edges.len() + 1`, the function removes the two presumed extremal bins, taking `&arg[1..arg.len() - 1]`, which is empty. The resulting empty `cumsum` is then accessed as `cumsum[cumsum.len() - 1]`, causing a panic. This witness does not depend on the values of the counts or alpha. **Source-level panic witness:** `make_quantiles_from_counts(vec![5.0], vec![0.5], Interpolation::Nearest)?.eval(&vec![7.0, 9.0])`.

### NaN validation bypass

`make_quantiles_from_counts` rejects non-increasing adjacent alphas by `w[0] >= w[1]`, a negative sign on the *first* alpha, and values greater than one in the *last* alpha. `alphas = [0.0, f64::NAN, 1.0]` passes all checks: comparisons involving NaN are false, and the endpoints are valid. This violates the implied valid-quantile range and breaks the assumed total ordering of `alphas` used by `count_lt_recursive`. Similarly, `bin_edges = [0.0, f64::NAN, 2.0]` passes the strictly increasing edge test because `>=` is false against NaN. These are constructor validation failures; their downstream interpolation result is not analyzed as a privacy leak.

### Normalization assumptions

`make_cdf` also divides the cumulative counts by their total without rejecting a zero total. For `[0.0, 0.0]`, the resulting `0.0/0.0` elements are NaN. The input is described as *noisy* counts and the implementation does not enforce nonnegativity or a positive total. Because these values may be valid outputs of a prior randomized mechanism, this requires a documented handling policy; the row remains `Partial` pending an explicit output contract and native regression.

## Evidence, disposition and limitations

- **Executed:** [Four dependency-free Python reference-model tests](../../../../../tools/tests/test_count_cdf_model.py) replicate the relevant guards, shape conditions and unguarded last-element access. They pass and confirm the listed source-level witnesses. They are **not** native OpenDP Rust executions or end-to-end FFI reproductions.
- **Upstream disposition:** **Unreported based on the current issue/PR searches**, subject to discovery of an equivalent historical report. [Upstream PR #455](https://github.com/opendp/opendp/pull/455) introduced these postprocessors but does not constitute a corrective fix; the source witnesses remain at the pinned upstream `main` revision. [Upstream issue #31](https://github.com/opendp/opendp/issues/31) is a broad Rust error-handling task, not a report of these specific paths.
- **Impact:** Availability, correctness and public API robustness; **no differential privacy violation demonstrated**. Postprocessing occurs after privacy-preserving measurement output, so no privacy-map undercount follows directly from these cases.

## Next checks

- Guard empty `cumsum` in both postprocessors and require at least two bin edges when interior bins are needed; return a structured `Fallible` error for unsupported histogram shapes.
- Explicitly reject NaN/non-finite quantile parameters and bin edges, and test partially ordered sequences.
- Define and test handling of zero/negative total noisy counts; execute compiled upstream Rust/FFI regressions for all witnesses.
- **Audit defect issues:** [#12 — empty CDF / zero-total normalization](https://github.com/opendp/opendp-audit/issues/12), [#13 — singleton-edge histogram panic](https://github.com/opendp/opendp-audit/issues/13), and [#17 — NaN quantile/edge constructor bypass](https://github.com/opendp/opendp-audit/issues/17). These are **audit-repository reports**, not matching upstream issues; upstream disposition remains **Unreported**.
