---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Partial
---

# Polars private means: bounded null fillers and unsigned noisy denominators

## Invariant, scope, and source dependencies

The non-deprecated Polars `dp_sum` and `dp_mean` combinators must generate stable, bounded expressions and count-noise output that matches the intended utility semantics. A valid typed integer clipping interval `[l,u]` should not cause a constructor panic merely because `l+u` overflows. A mean denominator intended to use symmetric additive integer noise should not be inadvertently biased by unsigned saturation. The privacy property examined here is narrower: public, deterministic fill-and-clip postprocessing must remain within the supplied bounds, and the unsigned saturation does not by itself raise privacy loss.

Upstream SHA: `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`.

- [`dp_sum` source audit](../source/rust/src/measurements/make_private_expr/expr_dp_sum/mod.rs.md), [pinned Rust](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_dp_sum/mod.rs).
- [`dp_mean` source audit](../source/rust/src/measurements/make_private_expr/expr_dp_mean/mod.rs.md), [pinned Rust](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_dp_mean/mod.rs).
- [`dp_len` counting shim source audit](../source/rust/src/measurements/make_private_expr/expr_dp_counting_query/mod.rs.md), [pinned Rust](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_dp_counting_query/mod.rs).
- [`match_shim` and `apply_plugin`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/mod.rs); [stable clipping](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_clip/mod.rs); [stable summation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_expr/expr_sum/mod.rs); [integer noise output saturation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/integer/mod.rs).
- [Independent standard-library test model](../tools/tests/test_polars_dp_mean_model.py).

## First finding: integer midpoint overflow

`make_expr_dp_sum` uses `get_midpoint<T>`, which evaluates `(lower+upper)/(1+1)` **before** clipping the filled values. No checked or widened addition is used. For `Int8` interval `[100,120]`, the mathematically intended fill is `110`; `100i8+120i8` overflows. In debug/checked-overflow Rust code, this is expected to panic instead of returning a `Fallible` error. In wrapping semantics, `100+120` becomes `-36` and division yields `-18`; after clipping it yields `100` instead of `110`. For `UInt32` interval `[2^31, 2^31+2]`, the wrapped filler is `1`, then clipping yields `2^31` rather than the intended `2^31+1`. Both are types supported by `make_expr_clip`. These are **source-level and independent-model** examples, not executions of the native OpenDP constructors.

For supported valid bounds, the final `clip(lower, upper)` enforces the same public bound even if the filler is wrong in an unchecked build. Consequently this finding is a correctness/utility and checked-constructor-robustness problem, **not a demonstrated privacy-sensitivity violation**. A checked panic is a public-parameter availability issue. This distinction depends on successful Polars clip semantics; no compiled Polars execution was performed.

## Second finding: unsigned noisy denominator

`make_expr_dp_mean` rewrites mean as a private sum divided by private length. It invokes `apply_plugin(vec![input, scale_denom], expr, DPLenShim)`, with **two** arguments. Although `make_expr_dp_len` destructures **three** values, `match_shim<_,3>` pads trailing args with `lit(NULL)`, so the third `signed` slot is null. The counting shim interprets `lit.bool().unwrap_or(false)` as **unsigned**, so no `.cast(DataType::Int64)` occurs. The length remains `UInt32`.

The integer noise pipeline is `T -> IBig -> (add symmetric noise) -> T::saturating_cast`. For an unsigned `T=u32`, a negative noisy count is clipped to zero. Under an ideal two-sided geometric (discrete Laplace) distribution, with `q=exp(-1/scale)` and `P(Z=k)=(1-q)/(1+q)*q^{|k|}`, a true count `c≥0` has strictly positive excess expectation:

`E[max(0,c+Z)] - c = q^(c+1)/(1-q²) > 0`.

The independent finite-tail model verifies this formula to `1e-12` for `c=0,1,2` at `scale=1`. The signed additive ideal noise has zero mean. This positive count bias can distort mean utility; a quantitative assertion about the mean itself requires specifying the numerator distribution. When the aggregation context declares `Invariant::Lengths`, `scale_denom=0`, so no count noise is introduced and this particular bias mechanism is absent.

Unsigned clipping is deterministic postprocessing and does not itself invalidate the noise mechanism's privacy bound. General privacy composition, exceptional errors, Polars optimization, and signed-denominator semantics remain **unverified**.

## Actual verification and upstream disposition

**Executed locally:** `python -m unittest -v /mnt/data/test_polars_dp_mean_model.py` completed **four passing model tests**, including checked/wrapping midpoint behavior for representative signed/unsigned types, thousands of seeded valid integer intervals, the shim's missing-argument convention, and finite-tail symmetric-Laplace expectations. The model uses a fixed-width reference implementation; **no OpenDP Rust, Polars, or FFI was compiled or run**.

**Upstream disposition:** Both midpoint overflow and unsigned noisy count bias are explicitly recorded in [OpenDP issue #3217](https://github.com/opendp/opendp/issues/3217) (“improve utility of polars means”). That issue is open on the pinned upstream revision; searches did not identify a matching merged corrective PR. These are not unreported defects and warrant **no new candidate-defect issue** in the audit repository. [Audit task #34](https://github.com/opendp/opendp-audit/issues/34) coordinates this bounded review.

## Conclusion and unresolved questions

Two previously reported correctness/utility defects are confirmed in the source-level chain and reproduced analytically. The clipping-after-fill and noise saturation architecture does not present a **demonstrated** privacy undercount within this scope; the full Polars execution/DP accounting proof remains **Partial**.

- Native debug and optimized Rust test for `Int8`/ `UInt32` bounds that overflow the intermediate midpoint, including a null input and exact expected fill.
- Native Polars test for `dp_mean` output dtype and distribution at small counts, with and without `Invariant::Lengths`, before/after an explicit signed denominator.
- Verify that sum-sensitivity and composition privacy maps remain conservative in exceptional Polars query and optimizer paths; model checks are not a substitute.
