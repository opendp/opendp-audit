---
schema_version: 1
source: rust/src/measurements/make_private_expr/expr_dp_mean/mod.rs
updated: 2026-11-22
---

# `rust/src/measurements/make_private_expr/expr_dp_mean/mod.rs`

## Scope and assumptions

Reviewed non-deprecated `make_expr_dp_mean` at upstream `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`, restricted to its `dp_sum` numerator, `dp_len` denominator, the implicit `signed` flag, and behavior under known-length invariants. The overall privacy theorem for the composition and noise plugins was not re-proved; compiled OpenDP/Polars was not run.

**Invariant:** The mean denominator should have a noise distribution consistent with the intended signed integer count, with no unnecessary saturation-induced bias when the true count is near zero. Public known-length invariants should remove unnecessary denominator noise.

- [Pinned source](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_dp_mean/mod.rs), [counting shim](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_dp_counting_query/mod.rs), [cross-file investigation](../../../../../../investigations/polars-dp-mean-filler-and-denominator.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::make_private_expr::expr_dp_mean::make_expr_dp_mean` | correctness/unsigned-noisy-denominator | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Unsigned denominator trace](#unsigned-denominator-trace) |
| `measurements::make_private_expr::expr_dp_mean::make_expr_dp_mean` | privacy/mean-noise-composition | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Privacy and execution limits](#privacy-and-execution-limits) |

## Analysis

### Unsigned denominator trace

The mean expands to `DPSumShim` for the numerator and `DPLenShim` for the denominator, with `Operator::TrueDivide` afterward. It constructs the length plugin with `apply_plugin(vec![input, scale_denom], expr, DPLenShim)`, omitting the optional third `signed` argument. `match_shim::<DPLenShim,3>` **accepts two arguments and pads the third with `lit(NULL)`**; the counting shim evaluates `signed = lit.bool().unwrap_or(false)`, hence `signed=false`. The resulting `len()` expression remains unsigned `UInt32`, not `Int64`.

For noisy counts, the integer noise mechanism samples symmetric integer noise and **saturates** back into unsigned `u32`, clipping negative releases to zero. This introduces positive bias for small true counts. The [idealized discrete-Laplace model](../../../../../../tools/tests/test_polars_dp_mean_model.py) gives `E[max(0,c+Z)]-c = q^(c+1)/(1-q^2) > 0`, with `q=exp(-1/scale)` and symmetric two-sided geometric `Z`; it checked counts `c=0,1,2`. The actual OpenDP noise sampler was not executed. This output-distribution mismatch can affect a mean computed as numerator divided by noisy denominator; no universal quantitative mean-bias claim follows without assumptions on the numerator.

If the input aggregation context has `Invariant::Lengths`, the code passes `scale_denom=0` and the denominator is deterministic; unsigned noise saturation then causes no noise bias. The public count's type remains unsigned. This exception matters for the issue's scope.

**Upstream disposition:** [OpenDP issue #3217](https://github.com/opendp/opendp/issues/3217) explicitly identifies the need to cast noisy counts to signed to avoid bias. The midpoint overflow in the same issue is also relevant to this caller's `dp_sum` numerator. No separate new issue is warranted.

### Privacy and execution limits

The signed-versus-unsigned saturation choice is deterministic postprocessing of the noisy integer release, so it does not itself increase divergence beyond the noise mechanism's privacy claim. The mean combines two private expressions, whose cumulative privacy accounting and data-dependent error paths are separate obligations. This audit inspected the source dispatch and the known-length branch, but did not validate all Polars optimizer behavior, compiled execution, or the joint composition privacy map. Overall compositional privacy status remains **Partial**.

## Next checks

- Add native Polars integration tests for a small-count mean with a positive denominator noise scale and compare signed/unsigned denominator distributions.
- Pass an explicit `lit(true)` signed argument for noisy count, then verify `NoisePlugin` output dtype, end-to-end privacy accounting, and behavior when a signed noisy denominator crosses zero.
- Verify `Invariant::Lengths` mode uses a deterministic count with no unnecessary denominator noise.
