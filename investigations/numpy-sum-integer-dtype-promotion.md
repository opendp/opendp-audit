---
schema_version: 1
upstream_commit: 7acfb2cdcee7d39fc26a6ade7edac15249c52f4b
updated: 2026-11-23
status: Partial
---

# NumPy sum's declared integer carrier versus NumPy accumulator promotion

## Invariant and threat model

For every input accepted by `array2_domain(T=...)`, the `make_np_sum` transformation must return a member of its declared `VectorDomain<AtomDomain<T>>`, and the return value must be serializable as the claimed FFI carrier `Vec<T>`. This is a correctness and availability invariant. A data-dependent failure side channel would require additional evidence; it is **not claimed** here. The scoped threat model is a public, legitimate narrow integer type, not adversarial control of type metadata.

## Affected symbols and source audits

- [`make_np_sum` implementation](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/_make_np_sum/__init__.py): advertises output `dp.vector_domain(dp.atom_domain(T=input_desc.T, nan=False))` and uses `lambda arg: arg.sum(axis=0)`.
- [`array2_domain` membership](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/__init__.py): accepts fixed-width integer ndarray members, checks row norm and public shape.
- [`_make_transformation` bridge](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/internal/mod.rs): callback `rust_type` is derived from the output domain's carrier.
- [`_convert._vector_to_slice` and `_numpy_to_slice`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/_convert.py): an ndarray entering `Vec<i8>` serialization takes the NumPy path, which requires exact `val.dtype == dtype(i8)`.
- [`with_privacy`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/_utilities.py): chains the sum constructor with noise; therefore the same type contract is inherited by `make_private_np_sum`.
- [Existing proof](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/_make_np_sum/make_np_sum.tex) asserts that `sum(axis=0)` returns the same atomic type; this is false for narrow integer arrays.
- [Source audit](../source/python/src/opendp/extras/numpy/_make_np_sum/__init__.py.md).

## Reasoning and evidence

**Counterexample (executed in standalone NumPy 2.3.5, not OpenDP):**

```python
import numpy as np

x = np.ones((128, 1), dtype=np.int8)
x_prime = x.copy()
x_prime[0, 0] = 0

assert x.sum(axis=0).dtype == np.dtype("int64")
assert x.sum(axis=0).tolist() == [128]
assert x_prime.sum(axis=0).tolist() == [127]
assert x_prime.sum(axis=0).dtype == np.dtype("int64")
```

Both arrays have the same public shape, are non-NaN, and each row has L1 norm at most one. They fit an `array2_domain(T="i8", size=128, num_columns=1, norm=1.0, p=1, nan=False)`. The source claims the output domain holds `i8` values; both outputs are actually `int64`. For `x`, the *value* 128 is also outside the signed-i8 range. This remains a domain-contract counterexample even under idealized arithmetic, since the relevant issue is NumPy's actual output type.

Other executed promotion checks: `int16/int32 -> int64`, `uint8/uint16/uint32 -> uint64`; `int64`, `uint64`, `float32`, and `float64` retained their dtypes on the tested platform.

**FFI consequence, based on inspected source only:** The generated transformation callback is typed by the declared `Vec<i8>` carrier. For ndarray output, `_vector_to_slice` delegates to `_numpy_to_slice`, whose exact-dtype guard rejects `int64` for `i8`. Thus a callback error is expected for even the value-127 case. This mismatch is type-dependent, not an established data-dependent distinguishing event. A native integration test is needed to observe the actual exception path and verify that constructor paths accept the example.

**Negative results and duplicates:** Upstream [#3153](https://github.com/opendp/opendp/issues/3153) / merged [#3188](https://github.com/opendp/opendp/pull/3188) address missing public column count, and upstream [#3195](https://github.com/opendp/opendp/issues/3195) addresses non-idealized floating-point sum calibration. Neither addresses NumPy integer dtype promotion. No equivalent open/closed audit issue was found before filing.

## Findings

- [Audit defect #123](https://github.com/opendp/opendp-audit/issues/123): **source-confirmed correctness/output-domain mismatch** and independently reproduced NumPy behavior; upstream disposition **Unreported**.
- [Audit task #120](https://github.com/opendp/opendp-audit/issues/120) scopes this review.
- Severity: **correctness/availability**, not demonstrated privacy underaccounting.
- Fix direction: either construct an output domain and metric matching a proven, safe NumPy accumulator type, or reject unsupported integer types. Any promotion fix needs to check value range, overflow semantics, and noise compatibility as separate obligations.

## Unresolved questions

1. Run OpenDP native Python with `T="i8"`, then invoke `make_np_sum` and `make_private_np_sum` for valid arrays; capture the exact constructor/invocation error.
2. Determine supported signed/unsigned integer types for `LpDistance<T>` and the noise constructor in this pipeline.
3. Add a regression asserting both actual output membership and successful private release for each supported `T`, or explicit construction-time rejection for unsupported types.
