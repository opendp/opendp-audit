---
schema_version: 1
upstream_commit: a010591f55b1713c926f8e355091471634480307
updated: 2026-11-23
status: Partial
---

# NumPy float32 finite-row sum overflow breaks certified privacy sensitivity

## Invariant

`opendp.extras.numpy.make_private_np_sum` composes a bounded-row sum transformation with the discrete Laplace or Gaussian noise mechanism. Its per-row Lp norm is at most `norm`; for a publicly fixed dataset size, a one-record replacement is at `SymmetricDistance=2`, and the emitted **noise input** must differ by at most `2*norm`. The sum transformation's advertised `VectorDomain<AtomDomain<T,nan=False>>` must contain every output for every admissible input.

This review uses concrete `float32` execution, even though the feature gate `idealized-numerics` explicitly requests an idealized numerical model. That distinction is material: it demonstrates a privacy-relevant implementation/proof gap in real arithmetic, not a contradiction to the proof under its idealized assumptions.

## Source links and trust boundary

1. [`array2_domain` row membership](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/__init__.py) uses `_rows_within_norm`, which checks each row independently using scaled floating norms and admits finite rows with magnitude `float32(1e38)` under `norm=1e38,p=2`.
2. [`make_np_sum`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_sum/__init__.py) constructs an output vector with input dtype and `nan=False`, but its pure callback computes `arg.sum(axis=0)` **without widening**. Fixed-size stability map is `d_in // 2 * 2 * norm`.
3. [`with_privacy`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/_utilities.py) composes the exact sum with Laplace or Gaussian noise; the sum occurs first and can trigger floating warnings/errors before noise.
4. [Rust `make_float_to_bigint`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/noise/nature/float/mod.rs) uses `RBig::try_from(x_i.clamp(T::MIN_FINITE, T::MAX_FINITE)).unwrap_or(RBig::ZERO)`. Therefore, if a nonfinite `float32` sum reaches this function, `-inf` maps to `-f32::MAX_FINITE`, while `NaN` maps to 0. The conversion is infallible by falling back, but its output-domain precondition (`nan=false`) was violated.
5. [Existing upstream NumPy tests](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/test/extras/test_sum_numpy.py) cover moderate data and integer shape constraints, not `float32` sum overflow. [Source-equivalent regression](../tools/tests/test_numpy_float32_sum_overflow_model.py); [finding #141](https://github.com/opendp/opendp-audit/issues/141).

## Executed counterexample A: underreported noise input sensitivity

The following is executable using NumPy 2.3.5:

```python
import numpy as np

v = np.float32(1e38)
A = np.array([v, v, v, -v, -v, -v, -v, -v], dtype=np.float32).reshape(8, 1)
B = A.copy()
B[3, 0] = v
with np.errstate(all="ignore"):
    print(A.sum(axis=0), B.sum(axis=0))   # [-inf], [nan]
```

Both are members of the domain `array2_domain(size=8,num_columns=1,norm=1e38,p=2,nan=False,T=f32)` according to the exact scaled membership predicate; they differ by **one replacement**, `d_in=2`. The source map reports `d_out=(2//2)*2*1e38 = 2e38`.

| Value | `A` | `B` |
| --- | --- | --- |
| NumPy `float32` sum | `-inf` | `nan` |
| Source-model float-to-bigint pre-rounding center | `-3.4028234663852886e38` | `0` |
| Widened `float64` sum (reference) | `-1.9999999360571385e38` | `0` |

The rationalized centers are **`3.4028234663852886e38` apart**, exceeding the public `2e38` L2 stability map by factor **1.701411733**. The NaN original sum also lies outside the declared non-NaN intermediate domain. Under ideal continuous Laplace with scale `1e38`, the shift would induce worst-case pure-DP loss about `3.4028`, not the map-implied `2`. The exact discretized native measurement output distribution was **not** sampled or independently analyzed; this is a conclusive source-equivalent transformation/pre-noise-contract counterexample, not a measured end-to-end DP violation.

## Executed counterexample B: private-data-dependent error

For `size=4` and the same public norm/dtype, compare `[v,v,v,-v]` with `[v,v,v,v]`: both valid, differ by one substitution. NumPy 2.3.5 yields a finite sum for the first and overflow for the second:

```python
A = np.array([v,v,v,-v], dtype=np.float32).reshape(-1,1)
B = np.array([v,v,v,v], dtype=np.float32).reshape(-1,1)
with np.errstate(over="raise", invalid="raise"):
    A.sum(axis=0)  # [2.0000001e+38]
    B.sum(axis=0)  # FloatingPointError: overflow encountered in reduce
```

Under this public NumPy error policy, the callback can fail depending on private data **before noise**, directly distinguishing neighboring inputs if that error is exposed. Under ordinary warning settings, a dataset-dependent `RuntimeWarning` can be emitted. End-to-end FFI error propagation was not executed.

## Validation and deduplication

**Executed independently:** NumPy `2.3.5` sum calculation, source-matched row membership, `SymmetricDistance` comparison, fixed-size map arithmetic, a numeric model of the pinned Rust clamp/rational-fallback conversion, and a `FloatingPointError` reproduction. The two source-equivalent regression cases are checked by [`tools/tests/test_numpy_float32_sum_overflow_model.py`](../tools/tests/test_numpy_float32_sum_overflow_model.py), which skips when NumPy is unavailable in audit CI. **Not executed:** native OpenDP `Domain.member`, `Transformation.invoke`, `Measurement.invoke`, its FFI, or native discrete noise. The result may depend on NumPy reduction-order/version; the executed witness uses 2.3.5 and tests pin that behavior.

**Distinct from prior art:** [upstream #2941](https://github.com/opendp/opendp/issues/2941) is Polars float32 cast/sum, not NumPy `make_np_sum`; [upstream #3024](https://github.com/opendp/opendp/issues/3024) is `np.linalg.norm` and clipping overflow, not accumulation. [Audit #123](https://github.com/opendp/opendp-audit/issues/123) covers integer dtype promotion; [audit #131](https://github.com/opendp/opendp-audit/issues/131) covers unsized L2 origin-norm underflow. No equivalent NumPy float32 sum issue or upstream PR was found in targeted searches.

## Disposition

- **Finding:** [Open privacy/important issue #141](https://github.com/opendp/opendp-audit/issues/141).
- **Coordinated audit:** [Task #139](https://github.com/opendp/opendp-audit/issues/139).
- **Suggested correction:** Ensure a provably bounded/no-NaN accumulation algorithm for float inputs (e.g. widen small floating dtypes to `float64` with matching output-domain/metric and conservative overflow guards, or reject parameter combinations that can overflow). The calculation must not emit data-dependent errors/warnings before the DP mechanism. A blanket `np.errstate(ignore)` does not fix the incorrect sensitivity and domain contract.
- **Next native regression:** Check domain membership, `make_np_sum(...).map(2)`, release input/output domains, and the two NumPy witnesses inside the actual OpenDP Python/FFI runtime. Verify Laplace/Gaussian privacy accounting after introducing safe aggregation.
