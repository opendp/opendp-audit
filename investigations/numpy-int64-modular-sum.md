---
schema_version: 1
upstream_commit: a010591f55b1713c926f8e355091471634480307
updated: 2026-11-23
status: Partial
---

# NumPy int64 sum: modular overflow invalidates finite row-norm stability

## Invariant

The Python `make_np_sum` transformation on publicly sized, row-norm-bounded `int64` NumPy arrays advertises output under `VectorDomain<AtomDomain<i64>>` and `L1Distance<i64>`. For a one-record replacement (symmetric input distance 2), its map returns `2 * norm`. The actual `np.ndarray.sum(axis=0)` must not change by more than this amount on any valid neighboring arrays; an overflow must be prevented or accounted for.

The claim fails for finite, valid `int64` input arrays because NumPy performs fixed-width modular arithmetic.

## Sources and related findings

- [`make_np_sum` at pinned upstream main](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_sum/__init__.py): uses `arg.sum(axis=0)` with no integer overflow check; sized sensitivity is `(d_in // 2) * 2 * norm`
- [`array2_domain` and its norm membership predicate](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/__init__.py): permits `int64` input, public `size=8`, bounded L1 rows
- [`_rows_within_norm`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_norm.py): scaled norm check used for valid rows
- [Callback bridge](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/internal/mod.rs) and [Python scalar type conversion](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/_convert.py): show why map evaluation may fail for a Python float result expected to be an `i64` distance
- [Audit finding #143](https://github.com/opendp/opendp-audit/issues/143), [standalone regression](../tools/tests/test_numpy_int64_sum_modular_overflow.py), and [source audit](../source/python/src/opendp/extras/numpy/_make_np_sum/__init__.py.md)

## Executed counterexample

Take `v = 2**60` and fixed `size=8`, `num_columns=1`, `norm=float(v)`, `p=1`, `T=i64`, `nan=False`. Let `x` be eight rows with the value `v` and `x'` replace one row by zero. Both satisfy the actual scaled row-norm membership predicate. The two arrays differ by one substitution, so `d_in=2`.

Standalone NumPy 2.3.5 returns:

```text
sum(x)               = -9223372036854775808 = -2**63
sum(x')              =  8070450532247928832 = 7*2**60
represented diff     = 17293822569102704640 = 15*2**60
advertised bound     =  2305843009213693952  =  2*2**60
ratio                = 7.5
```

Both outputs have `int64` dtype. The first value is the wraparound of the mathematical sum `2**63`, not the actual mathematical sum. The second is in range. This refutes the *mathematical stability claim* with ordinary valid inputs without relying on dtype promotion or nonfinite floats.

## Unsigned counterexample with representable output distance

A second independent NumPy 2.3.5 experiment uses `uint64` rather than signed integers. Let `v=2**60` and `size=16`. Dataset `x` has sixteen rows `[v]`, and `x'` replaces one row with zero. Both arrays satisfy the same finite row-norm constraint with `T=u64`, `p=1`, `norm=float(v)`.

NumPy computes `sum(x) = 0_u64` (because `16*v=2**64` wraps) and `sum(x') = (15*v)_u64`, maintaining `uint64` dtype. The actual represented difference `15*v = 17293822569102704640` **fits** in `u64`, whereas the formula claims only `2*v=2305843009213693952`. The 7.5× mismatch therefore does **not** rely on an output distance too large for the declared integer-distance type. See the unsigned tests in [regression](../tools/tests/test_numpy_int64_sum_modular_overflow.py) and native [probe script](../tools/integration/numpy_int64_sum_native.py).

## Privacy interpretation and limit

This is an intended-map underestimation, but **not a measured privacy breach of the generated private measurement**. The constructor's callback computes a Python `float` sensitivity from the domain's floating `norm`; its output metric is `L1Distance<i64>` whose callback serialization expects `i64`. The inspected conversion code rejects float-to-integer type mismatches. Consequently a native `make_np_sum.map(2)` might fail before returning the incorrect bound, and `make_private_np_sum` may be unusable. Native validation must establish the exact FFI behavior and whether any private composition can be invoked or certified.

Even if the callback's type is repaired, modular sum cannot safely be treated as an ordinary real/integer Lipschitz map. The actual represented-output difference here exceeds `i64::MAX`, so no `i64` distance value can bound this pair.

## Duplicates and next work

- [Audit #123](https://github.com/opendp/opendp-audit/issues/123) is narrow-integer accumulation dtype **promotion**, whereas `int64` retains dtype and wraps.
- [Audit #141](https://github.com/opendp/opendp-audit/issues/141) is `float32` accumulation to Inf/NaN, not modular integer overflow.
- [Upstream #458](https://github.com/opendp/opendp/issues/458) describes preexisting Rust constructor overflow safeguards, not this Python implementation.

**Verification completed:** Exact source-equivalent NumPy sum, replicated domain membership, and map formula; the test runs independently of native OpenDP. **Open:** native callback return-type behavior, constructor rejection/acceptance, and downstream noise invocation under the same inputs.

A safe repair must either certify that all permitted sums remain representable in the declared accumulator or use a different mathematically sound accumulation domain/noise model. A map-type correction alone is insufficient.
