---
schema_version: 1
source: rust/src/utilities/search/mod.rs
updated: 2026-11-23
---

# `rust/src/utilities/search/mod.rs`

## Scope and assumptions

- **Scope:** Automatic bound inference for monotone finite floating-point predicates via `Bands::bands`, `signed_band_search`, `fallible_signed_band_search`, `resolve_bounds`, and `fallible_exponential_bounds_search`. This is a bounded audit of the *probe horizon*, not the entire binary-search algorithm.
- **Invariant:** When the search begins at zero or from a one-sided known endpoint, a finite representable threshold cannot be incorrectly classified as nonexistent solely because the finite probe sequence stops prematurely. Explicit two-sided bounds are a control.
- **Assumptions:** Pure, monotone predicate with a single finite decision boundary; no callback exceptions, NaNs, or infinite values; `f32` occupies four bytes and `f64` eight bytes on supported Rust platforms.
- **Pinned source:** [Rust search utilities](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/utilities/search/mod.rs), [FFI dispatch](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/internal/mod.rs), [Python public search](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/mod.py).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `Bands for f32::bands` | correctness/search-bound-inference | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Probe horizon](#probe-horizon): finite thresholds beyond 512 are unobservable from zero |
| `Bands for f64::bands` | correctness/search-bound-inference | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Probe horizon](#probe-horizon): finite thresholds beyond 2^49 are unobservable from zero |
| `signed_band_search` | correctness/search-bound-inference | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Propagation](#propagation); other sign/center cases not fully audited |
| `fallible_signed_band_search` | correctness/search-bound-inference | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Propagation](#propagation); callback-error recovery not audited |
| `resolve_bounds` | correctness/search-bound-inference | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Propagation](#propagation); inspected missing-bound branches only |
| `fallible_exponential_bounds_search` | correctness/search-bound-inference | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Propagation](#propagation); successful-center path checked, exceptional-center path not audited |

## Analysis

### Probe horizon

`impl_bands_float!` is instantiated for `f32` and `f64`. Its band list is `[center, center ± 0.5]` followed by `center ± 2^(k*k)` for `k in 0..std::mem::size_of::<Self>()`. This is *byte count*, not the floating exponent width.

From center = 0, positive `f32` probes end at `2^9 = 512` (four iterations); positive `f64` probes end at `2^49` (eight iterations). Negative probes are symmetric. Thus the monotone, everywhere-defined predicates `x >= 1024_f32` and `x >= 2^50_f64` are false at every positive and negative automatically generated probe, although each predicate has a finite true region. The same issue affects inferring the upper endpoint from `Above(0)`.

The control predicates evaluated at explicit endpoints `(0, 2048)` (`f32`) and `(0, 2^51)` (`f64`) have different Boolean values. The binary-search core can therefore enter its normal bracketing loop. This does not rely on a narrow floating-point rounding edge case; all cited numbers are exactly representable powers of two.

### Propagation

`signed_band_search`/`fallible_signed_band_search` compare each adjacent probe with the predicate value at center. Since none changes, both return `None`. With no bounds, `fallible_exponential_bounds_search` tries positive then negative directions, yielding `None`; `resolve_bounds` returns `Err(Search, "unable to infer bounds")`. With `Above(0)`, it returns `Err(Search, "the decision boundary is below the lower bound or the predicate does not change above it")`, although the boundary lies *above* the known lower bound.

[`opendp_internal___binary_search`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/internal/mod.rs) dispatches both `f32` and `f64` to these search helpers. The public Python [`binary_search` and `binary_search_param`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/mod.py) propagate missing-bound inference to Rust; `T=float` uses an `f64` search. This is a correctness/availability limitation in calibration, not evidence of privacy-budget undercounting.

### Evidence and limitations

- [Independent five-test source-level witness](../../../../../tools/tests/test_float_search_band_horizon_model.py) was executed with Python standard-library `unittest`; all five tests passed. It enumerates the pinned Rust probe formula and compares successful explicit brackets.
- **No native OpenDP Rust or Python bindings were executed.** The inference is deterministic from the reviewed source; the model is not a native differential test.
- Existing upstream [issue #443](https://github.com/opendp/opendp/issues/443) concerns a different, older Python exception at an extreme endpoint, not this finite probe-horizon defect.
- [Cross-file investigation](../../../../../investigations/float-search-band-inference.md) and [candidate issue #102](https://github.com/opendp/opendp-audit/issues/102).

## Next checks

1. Add native Rust tests for `f32` threshold `1024` and `f64` threshold `2^50`, both with no bounds, `Above(0)`, and explicit two-sided bounds.
2. Repair float band generation to reach the largest finite magnitude in each direction, with overflow/progress guards; add public Python/R coverage for large-scale inference.
3. Audit nonzero center, callback exceptions, NaN/infinite probe behavior, and whether downstream parameter-calibration code supplies user bounds.
