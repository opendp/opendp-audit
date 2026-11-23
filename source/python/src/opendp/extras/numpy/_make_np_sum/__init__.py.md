---
schema_version: 1
source: python/src/opendp/extras/numpy/_make_np_sum/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/numpy/_make_np_sum/__init__.py`

## Scope and assumptions

- **Audit scope:** `make_np_sum` output-domain construction and integer NumPy summation dtype, with the generated private wrapper and typed callback conversion followed across module boundaries. A previous audit independently addressed public column-count validation.
- **Invariant:** The emitted array belongs to the advertised vector output domain and is compatible with the FFI callback's promised carrier type for every valid input.
- **Assumptions:** `idealized-numerics` and `contrib` enabled; well-formed fixed-shape arrays; supported integer input types. The NumPy accumulator type is observed directly; native OpenDP has not been executed.
- **Source links:** [`make_np_sum`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/_make_np_sum/__init__.py), [domain implementation](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/__init__.py), [FFI adapter](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/internal/mod.rs), [FFI conversion](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/_convert.py), [proof](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/numpy/_make_np_sum/make_np_sum.tex).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `opendp.extras.numpy._make_np_sum.make_np_sum` | correctness/output-domain-membership | Audited | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | [Counterexample and cross-file investigation](../../../../../../../investigations/numpy-sum-integer-dtype-promotion.md); [defect #123](https://github.com/opendp/opendp-audit/issues/123). |
| `opendp.extras.numpy._make_np_sum.make_private_np_sum` | correctness/noise-chain-input-carrier | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Generated via `with_privacy`, so the sum type mismatch enters composition; native invocation and exact error are untested. |
| `opendp.extras.numpy._make_np_sum.make_np_sum` | privacy/integer-sum-stability | Partial | `7acfb2cdcee7d39fc26a6ade7edac15249c52f4b` | Reviewed the declared metric and type only; full integer overflow/stability and complete native execution not established. |

## Analysis

### `make_np_sum` — `correctness/output-domain-membership`

The constructor declares `VectorDomain<AtomDomain<T>>` using `input_desc.T`, but the callback returns `arg.sum(axis=0)` without specifying `dtype`. NumPy widens `int8`, `int16`, and `int32` to `int64`, and narrower unsigned integers to `uint64`. Consequently the returned array violates its declared element dtype for ordinary valid narrow-integer input arrays. Independently, a sum may exceed the `T` representable range (e.g., 128 unit-valued `int8` rows sum to 128).

A standalone NumPy 2.3.5 execution confirmed this behavior and the specific `int8` value/dtype counterexample. Inspection of the callback conversion additionally showed exact dtype comparison, suggesting invocation failure rather than silent coercion. No native OpenDP test was executed; distinguish this source-level proof from an observed OpenDP exception or proven privacy leak.

The [investigation](../../../../../../../investigations/numpy-sum-integer-dtype-promotion.md) records the full witness, supporting modules, and the limitation. [Upstream #3153](https://github.com/opendp/opendp/issues/3153), fixed by [#3188](https://github.com/opendp/opendp/pull/3188), is a separate unknown-output-width problem and does not fix dtype promotion.

## Next checks

Execute OpenDP end-to-end for `make_np_sum` and `make_private_np_sum` with `T="i8"` and a fixed column count. Choose a supported output type or reject narrow integers explicitly, then add regression tests for output-domain membership and private composition.
