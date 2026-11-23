---
schema_version: 1
source: rust/src/measurements/make_private_expr/expr_noisy_max/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/make_private_expr/expr_noisy_max/mod.rs`

## Scope and assumptions

- **Scope:** Groupwise privacy-map calibration in `rnm_privacy_map`, positive-scale per-row selection in `noisy_max_udf`, and shape/type validation in `noisy_max_plugin_type_udf`. This is the non-deprecated Polars `noisy_max` expression path; older deprecated count/index APIs are excluded.
- **Invariants:** Changing at most `l0` public-shape arrays, each at coordinatewise distance no more than `li`, must incur at most `l0` times the conservative one-array top-1 privacy loss. Each successful nonempty array must produce an index within its array width.
- **Assumptions:** Per-array `noisy_top_k` has the documented sampler law; output arrays have public, fixed positive width and valid non-null, non-NaN numeric elements; each row's sampler uses independent entropy. We do not assume differing-width arrays are finite-distance neighbors. The full Polars planner and Rust binary were not run.
- **Pinned code:** [Polars noisy-max expression](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_noisy_max/mod.rs), [top-k core](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noisy_top_k/mod.rs), [scalar noisy-max wrapper](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noisy_max/mod.rs), [upstream tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_noisy_max/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::make_private_expr::expr_noisy_max::rnm_privacy_map` | privacy/groupwise-composition | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Groupwise distributional investigation](../../../../../../investigations/polars-noisy-max-groupwise-calibration.md) |
| `measurements::make_private_expr::expr_noisy_max::make_expr_noisy_max` | privacy/scale-calibration | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Scale and metric trace](#analysis) |
| `measurements::make_private_expr::expr_noisy_max::noisy_max_udf` | correctness/selection-index | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Index bound analysis](#analysis) |
| `measurements::make_private_expr::expr_noisy_max::noisy_max_plugin_type_udf` | correctness/array-shape-validation | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Shape and dtype checks](#analysis) |

## Analysis

### Groupwise calibration

`make_expr_noisy_max` stabilizes the input expression, extracts an `ArrayDomain`, and builds a row mechanism through `rnm_privacy_map`. This helper invokes `make_noisy_max` with `LInfDistance::default()` (non-monotonic), the original scale, and matching `negate` and output measure. Thus a per-array `L-infinity` bound `d` is charged as `2d/scale` for `MaxDivergence` (permute-and-flip) or `(2d/scale)^2 / 8` for `ZeroConcentratedDivergence` (exponential-mechanism proposals); this is the `k=1` case of the [separate top-k audit](../../noisy_top_k/mod.rs.md).

The outer map takes `(l0, li)`, converts `li` conservatively upward to the numeric atom type `T`, invokes the scalar mechanism privacy map, and multiplies its result outward by `f64::inf_cast(l0)`. Under a public fixed-width array shape and the standard sequential-composition theorem, this is conservative for the ordered vector of up to `l0` changed-row outputs. The distributional model [here](../../../../../../investigations/polars-noisy-max-groupwise-calibration.md) found no violation for the declared small-grid parameter set. This result does **not** establish the preconditions of `approximate_c_stability`, the validity of every composite Polars expression, or numeric soundness for extreme f64 values. Therefore the calibration rows remain **Partial**.

### Scale, execution, and index bounds

If the expression omits a local scale, `make_expr_noisy_max` derives it from `approximate_c_stability`, provided a global scale is supplied; otherwise it uses the explicitly supplied local scale. The chosen scale is multiplied by `global_scale` (default one). NaN/negative parameters are rejected; nonfinite effective scales are subsequently rejected by `make_noisy_max`. This is a source-level trace rather than a general proof of calibrated default scales.

`noisy_max_udf` runs `noisy_top_k(&scores, scale, 1, negate, replacement)` for every array row and reads output index zero. The shared top-k peeling loop emits exactly one index in `0..n` for `n>0`. The plugin converts this index to `u32`. The type UDF rejects array width zero, rejects non-numeric types and unsupported `u8`/`u16`, and declares `UInt32` output; the ordinary accepted widths are representable in `u32` in practical Polars execution, but **this audit did not prove** a hard `n <= u32::MAX` check. The latter is a residual extreme-shape question, not a demonstrated defect.

The native upstream tests cover a three-index zero-scale selection and one quantile-derived expression, plus a NaN-scale failure. An independent finite model checks positive-scale probability laws and zero-scale argmax/argmin semantics, but does **not** invoke the actual Polars plugin or validate Arrow null-bitmaps.

## Findings

**No defect identified** in groupwise `L0` composition, one-array index bounds, or the observed shape/type checks within the stated assumptions. All tested finite distributional comparisons satisfy the claimed bounds. No candidate-defect issue was warranted; [audit task #30](https://github.com/opendp/opendp-audit/issues/30) tracks this bounded scope only.

## Next checks

- Run the compiled Polars tests for `MaxDivergence` and `ZeroConcentratedDivergence`, including nested nullable array values, very large declared array widths, and zero scale.
- Audit `approximate_c_stability` and nontrivial expression composition end-to-end; this report does not certify all derived scales.
- Check that future backend changes preserve the per-row entropy/independence assumptions, and revalidate extreme f64 arithmetic.
