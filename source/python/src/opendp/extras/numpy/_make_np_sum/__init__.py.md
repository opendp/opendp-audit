---
schema_version: 1
source: python/src/opendp/extras/numpy/_make_np_sum/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/numpy/_make_np_sum/__init__.py`

## Scope and assumptions

- **Audit scopes:** (1) `make_np_sum` output-domain construction and integer NumPy summation dtype, with the generated private wrapper and typed callback conversion; (2) independently, the unsized-data nonzero-origin L2 sensitivity calculation and its Gaussian calibration path. A previous audit addressed public column-count validation. (3) A 2026-11-23 review additionally covers concrete `float32` accumulator overflow, the consequent input domain breach before noise, and source-equivalent sensitivity/error-channel counterexamples.
- **Invariants:** The emitted array belongs to its advertised vector output domain; and the reported unsized-data L2 stability map conservatively bounds the actual change in summed row vectors for all admitted neighboring arrays.
- **Assumptions:** `idealized-numerics` and `contrib` enabled; well-formed arrays and supported integer input types for the first scope. The second scope uses float64 data, `size=None`, `p=2`, one column, public origin `[1e-200]`, public radius `1e-200` or `0`, and NumPy 2.3.5 semantics. Only independent NumPy calculations, not native OpenDP, were executed. The new third scope uses finite `float32` single-column rows of magnitude `1e38` in publicly fixed eight- or four-row datasets under NumPy 2.3.5; the Rust float-noise integerization behavior is modeled from pinned source.
- **Source links:** [`make_np_sum`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/_make_np_sum/__init__.py), [domain implementation](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/__init__.py), [FFI adapter](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/internal/mod.rs), [FFI conversion](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/_convert.py), [proof](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/_make_np_sum/make_np_sum.tex).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `opendp.extras.numpy._make_np_sum.make_np_sum` | correctness/output-domain-membership | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Counterexample and cross-file investigation](../../../../../../../investigations/numpy-sum-integer-dtype-promotion.md); [defect #123](https://github.com/opendp/opendp-audit/issues/123). |
| `opendp.extras.numpy._make_np_sum.make_private_np_sum` | correctness/noise-chain-input-carrier | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Generated via `with_privacy`, so the sum type mismatch enters composition; native invocation and exact error are untested. |
| `opendp.extras.numpy._make_np_sum.make_np_sum` | privacy/integer-sum-stability | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Reviewed the declared metric and type only; full integer overflow/stability and complete native execution not established. |
| `opendp.extras.numpy._make_np_sum.make_np_sum` | privacy/unsized-sum-origin-norm-rounding | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [New analysis](#unsized-sum-origin-norm-rounding), [investigation](../../../../../../../investigations/numpy-unsized-sum-origin-norm-underflow.md), [defect #131](https://github.com/opendp/opendp-audit/issues/131). |

| `opendp.extras.numpy._make_np_sum.make_np_sum` | privacy/float32-sum-overflow-stability | Audited | `a010591f55b1713c926f8e355091471634480307` | [Floating overflow and sensitivity](#float32-sum-overflow-and-pre-noise-privacy); [investigation](../../../../../../../investigations/numpy-float32-sum-overflow-privacy.md); [privacy issue #141](https://github.com/opendp/opendp-audit/issues/141). |
| `opendp.extras.numpy._make_np_sum.make_np_sum` | correctness/float32-sum-non-nan-output | Audited | `a010591f55b1713c926f8e355091471634480307` | [Floating overflow and sensitivity](#float32-sum-overflow-and-pre-noise-privacy); output `nan` contradicts `nan=False` intermediate vector domain. |
| `opendp.extras.numpy._make_np_sum.make_private_np_sum` | privacy/float32-sum-prenoise-error | Partial | `a010591f55b1713c926f8e355091471634480307` | [Floating error side channel](#float32-sum-overflow-and-pre-noise-privacy); the source-equivalent NumPy callback errors, native FFI error observability not executed. |

## Analysis

### `make_np_sum` — `correctness/output-domain-membership`

The constructor declares `VectorDomain<AtomDomain<T>>` using `input_desc.T`, but the callback returns `arg.sum(axis=0)` without specifying `dtype`. NumPy widens `int8`, `int16`, and `int32` to `int64`, and narrower unsigned integers to `uint64`. Consequently the returned array violates its declared element dtype for ordinary valid narrow-integer input arrays. Independently, a sum may exceed the `T` representable range (e.g., 128 unit-valued `int8` rows sum to 128).

A standalone NumPy 2.3.5 execution confirmed this behavior and the specific `int8` value/dtype counterexample. Inspection of the callback conversion additionally showed exact dtype comparison, suggesting invocation failure rather than silent coercion. No native OpenDP test was executed; distinguish this source-level proof from an observed OpenDP exception or proven privacy leak.

The [investigation](../../../../../../../investigations/numpy-sum-integer-dtype-promotion.md) records the full witness, supporting modules, and the limitation. [Upstream #3153](https://github.com/opendp/opendp/issues/3153), fixed by [#3188](https://github.com/opendp/opendp/pull/3188), is a separate unknown-output-width problem and does not fix dtype promotion.

### Unsized sum origin-norm rounding

**Conclusion:** `make_np_sum` uses `norm += np.linalg.norm(origin, ord=p)` when the dataset size is unknown. For `p=2` the normal NumPy norm implementation can underflow to zero for a finite nonzero origin because it squares small coordinates. The row domain, however, uses [a scaled norm-membership routine](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/_norm.py), so its admitted rows can have larger norms than the numerical stability map.

**Counterexample:** With `norm=1e-200`, `p=2`, `size=None`, `origin=np.array([1e-200])`, and `T=f64`, compare the empty `(0,1)` array to a one-row array `[[2e-200]]`. Both pass the explicit scaled membership predicates, and are one insertion apart under `SymmetricDistance`. The implementation's `np.linalg.norm(origin, 2)` returns **0**, so the reported `map(1)` is `1e-200`; the actual one-dimensional output L2 distance is `2e-200`. With zero radius and the same origin, the reported map is exactly zero despite a nonzero possible sum.

Under ideal Gaussian noise with scale `sigma=1e-200`, the output shift corresponds to `rho=2` rather than claimed `rho=0.5`, a fourfold privacy-parameter underestimate. The source-level wrapper `with_privacy` routes the L2 sum output to Gaussian noise. This is **not** a native OpenDP or complete measurement execution. The constructor requires the `idealized-numerics` feature, whose existing mathematical proof explicitly ignores machine rounding; this audit exhibits the difference between that proof model and concrete NumPy arithmetic.

**Executed:** Independent NumPy 2.3.5 checks of the exact scaled membership predicate, the `np.linalg.norm` underflow, the sum outputs and numerical map; an analytic Gaussian zCDP calculation. [Standalone regression](../../../../../../../tools/tests/test_numpy_sum_origin_norm_model.py). No native OpenDP invocation, FFI conversion or Gaussian sampling was executed.

**Deduplication:** Separate from the integer dtype [audit #123](https://github.com/opendp/opendp-audit/issues/123) and the now-closed [upstream clamp underflow issue #2953](https://github.com/opendp/opendp/issues/2953). See [cross-file investigation](../../../../../../../investigations/numpy-unsized-sum-origin-norm-underflow.md) and [audit #131](https://github.com/opendp/opendp-audit/issues/131).

### Float32 sum overflow and pre-noise privacy

**Pinned new review:** [upstream `a010591f55b1713c926f8e355091471634480307`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_sum/__init__.py), [cross-file investigation](../../../../../../../investigations/numpy-float32-sum-overflow-privacy.md), [source-equivalent test](../../../../../../../tools/tests/test_numpy_float32_sum_overflow_model.py), [audit privacy finding #141](https://github.com/opendp/opendp-audit/issues/141). For a valid `array2_domain(norm=1e38,p=2,size=8,num_columns=1,T=f32,nan=False)`, one-record replacement changes row-sign sequence `+++-----` into `++++----`. The actual `arg.sum(axis=0)` on NumPy 2.3.5 is `-inf` versus `nan` while the fixed-size map reports `2e38`. `nan` is not in the declared `vector_domain(atom_domain(T=f32,nan=False))`.

The Rust [float-to-bigint noise input converter](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/noise/nature/float/mod.rs) converts the `-inf` to `-f32::MAX_FINITE` and `nan` to zero through finite clamping and `unwrap_or(RBig::ZERO)`. This yields source-equivalent pre-rounding rational centers **`3.4028234663852886e38` apart**, 1.7014× the claimed L2 stability map. The exact native noise distribution and end-to-end privacy loss were **not** executed; the source-backed pre-noise stability contract is violated.

A second valid adjacent pair `[v,v,v,-v]` versus `[v,v,v,v]`, `v=float32(1e38)`, gives a finite result versus `FloatingPointError` in `np.errstate(over="raise",invalid="raise")`. This error originates within the sum callback **before** noise and is private-data-dependent if propagated. Under default settings a data-dependent overflow warning is possible. No upstream issue or PR specifically for NumPy `float32` sum overflow was found; the prior Polars overflow issue [#2941](https://github.com/opendp/opendp/issues/2941), NumPy integer dtype issue [audit #123](https://github.com/opendp/opendp-audit/issues/123), and unsized origin-norm underflow issue [audit #131](https://github.com/opendp/opendp-audit/issues/131) concern different paths.

**Executed:** independent NumPy 2.3.5 calculations, scaled row-membership source model, fixed-size map arithmetic, noise-conversion source model, and a reproducer under raise-on-overflow policy. **Not executed:** OpenDP native FFI, actual `Domain.member`, noise sampling or the private release. The constructor is gated by `idealized-numerics`; this review exhibits the limitation of that assumption in actual `float32` arithmetic. Fix by safe accumulation with a matching declared output dtype and conservative map, or by precluding unsafe parameter/dtype combinations; merely hiding warnings does not fix the stability contract.

## Next checks

For the dtype mismatch, execute OpenDP end-to-end with `T="i8"` and a fixed column count, and choose a compatible sum output type. Independently, run a native OpenDP regression of the unsized nonzero-origin L2 counterexample, including domain membership, transformation map and Gaussian composition; replace the NumPy origin norm with a conservatively rounded, underflow-safe computation.

For float32 aggregation, add native OpenDP regression tests for the two neighboring-array witnesses and ensure the typed sum output is always a non-NaN member of its certified domain; audit overflow/underflow for other floating dtypes and public sizes.
