---
schema_version: 1
upstream_commit: a010591f55b1713c926f8e355091471634480307
updated: 2026-11-23
status: Partial
---

# Float32 SSCP overflow produces nonfinite matrices and pre-noise warnings

## Invariant and threat model

A valid `NPArray2Domain` with an `L2` bound on each row should yield an SSCP matrix `X.T @ X` belonging to the declared finite `NPSSCPDomain`; a transformation relied on by a differentially private measurement must not expose private-input-dependent warnings or errors **before** noise. This review covers the non-deprecated `make_np_sscp` and its composition into private eigendecomposition.

For the warning side channel, the observer is a Python caller who can capture warnings (e.g. `warnings.catch_warnings(record=True)`, `warnings.simplefilter("always")`) or explicitly configure `np.errstate(over="raise")`. The prospective privacy violation is conditional on actual native OpenDP callbacks not suppressing the warning; this runtime propagation has not been tested. The simpler **output-domain contract failure** is established by arithmetic alone.

## Affected symbols and source audits

- [`make_np_sscp` source report](https://github.com/opendp/opendp-audit/blob/main/source/python/src/opendp/extras/numpy/_make_np_sscp/__init__.py.md), [pinned implementation](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_make_np_sscp/__init__.py): `lambda arg: arg.T @ arg`, returning the array from its input dtype.
- [Input `array2_domain` and output `_sscp_domain`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/__init__.py): accepts bounded finite rows, requires finite SSCP matrix entries.
- [`_rows_within_norm`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/numpy/_norm.py): computes scaled row norm and compares against a public norm bound without squaring it.
- [`make_private_np_eigendecomposition`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/sklearn/_make_eigendecomposition/__init__.py): constructs the SSCP transformation as `t_sscp`, composes it before private eigenvalue and eigenvector mechanisms.
- [`make_eigenvalues`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/sklearn/_make_eigenvalues/__init__.py) applies `np.linalg.eigvalsh` to intermediate SSCP matrices; it expects a finite matrix domain.
- [Audit issue #168](https://github.com/opendp/opendp-audit/issues/168), [task #155](https://github.com/opendp/opendp-audit/issues/155), [standalone regression](https://github.com/opendp/opendp-audit/blob/main/tools/tests/test_numpy_sscp_float32_overflow_model.py).

## Reasoning and evidence

### Valid neighboring input datasets

Take a public `NPArray2Domain(norm=1e21,p=2,size=1,num_columns=2,nan=False,T=f32)`. Let

```python
x0 = np.array([[1e10, 0]], dtype=np.float32)
x1 = np.array([[1e20, 0]], dtype=np.float32)
```

Both `x0` and `x1` have the required dtype, shape, size, finite entries, and row Euclidean norm bounded by `1e21`. The source's scaled predicate `_rows_within_norm` compares `norm_of_row/scale <= norm/scale`, avoiding squaring the original element; a standalone exact copy returned `True` for both. They differ by one row replacement; under `SymmetricDistance` this is a distance at most 2.

This witness does **not** require invalid input or a fabricated SSCP matrix. The origin is the default public zero and is accepted by the transformation's origin restriction.

### Data-dependent overflow at SSCP execution

The actual transformation function is `lambda arg: arg.T @ arg` without any cast to `float64` and without an `np.errstate` guard. In NumPy 2.3.5 the `float32` multiplication computes:

| Input | `X.T @ X` | Overflow warning |
| --- | --- | --- |
| `x0` | `[[1e20,0],[0,0]]` | None |
| `x1` | `[[inf,0],[0,0]]` | `RuntimeWarning: overflow encountered in matmul` |

The `float32` maximum finite value is about `3.4e38`; `(1e20)^2 = 1e40` therefore overflows, while the declared mathematical bound `(1e21)^2 = 1e42` is finite in Python's usual `float64` scale. In a standalone `warnings.catch_warnings` context with `simplefilter("always")`, `x0` produced no warnings and `x1` produced an overflow warning. Under `np.errstate(over="raise")` the former succeeded and the latter raised `FloatingPointError`, before any DP noise.

The invalid `x1.T @ x1` output violates the explicitly stated `_sscp_domain` predicate requiring `np.isfinite(matrix).all()`. The same value fed to local `np.linalg.eigvalsh` returned NaN eigenvalues. Thus even with warning handling, the declared output-domain invariant fails.

**Execution boundary:** This is a standalone NumPy reproduction following the precise constructor and membership arithmetic, **not** a native OpenDP or complete private eigendecomposition invocation. The native FFI's treatment of warnings and the behavior of downstream noise on nonfinite values are not established here.

### Privacy side-channel scope

If the standard NumPy warning or the configured `FloatingPointError` escapes the transformation callback while it is composed into `make_private_np_eigendecomposition`, an observer can distinguish the two adjacent datasets independently of the subsequently sampled private release. With always-enabled warning capture, the event `an overflow warning occurred` is deterministic for the tested multiplication, giving probability 0 on `x0` versus 1 on `x1`. No nontrivial DP guarantee on the full observer-visible behavior can hold with this event. The observation is **conditional on native callback propagation**; do not state that the native measurement has been successfully exploited.

### Deduplication and pending upstream refactor

- [Audit #141](https://github.com/opendp/opendp-audit/issues/141): NumPy `float32` **summation** overflow under row-bound sensitivity; distinct implementation, albeit the same general unsafe narrow arithmetic class.
- [Audit #115](https://github.com/opendp/opendp-audit/issues/115): the old `_sscp_domain` accepts **fabricated overlarge finite PSD matrices**; resolved as pending [upstream PR #3281](https://github.com/opendp/opendp/pull/3281). That finding does not involve genuine bounded dataset execution or warnings.
- Upstream [PR #3281](https://github.com/opendp/opendp/pull/3281), open/draft, changes the matrix domain and metric but **retains `lambda arg: arg.T @ arg`**. Its new bound checks compute `row_norm_sq = input_desc.norm * input_desc.norm` and require it be finite; `1e42` passes this f64-style check, while the actual `float32` matrix multiplication still overflows. The PR thus does not address this witness. Other pending PCA PRs were checked for an equivalent repair, and upstream/audit issues were searched for SSCP float32 execution overflow.
- No upstream OpenDP issue/PR was identified that fixes the data-dependent matrix-multiplication overflow. [Candidate defect #168](https://github.com/opendp/opendp-audit/issues/168) is therefore recorded as **Unreported** on the reviewed main revision, not fixed by the draft refactor.

## Findings

**Confirmed in standalone NumPy:** valid same-domain neighboring `float32` rows produce finite versus infinite SSCP matrices, and no warning versus an overflow warning/exception. The output-domain postcondition is contradicted by source-level arithmetic and observed execution.

**Privacy relevance (native verification outstanding):** a warning or exception before DP noise, if observable through the composed OpenDP measurement, is a complete distinguishing side channel. The exact FFI callback propagation and a compiled OpenDP end-to-end regression were not executed; therefore this investigation's overall status is **Partial**.

## Unresolved questions

1. Run native OpenDP `array2_domain.member`, `make_np_sscp` construction, and invocation for `x0`/`x1`; capture warnings and test `np.errstate(over="raise")`.
2. Invoke `make_private_np_eigendecomposition` (and the PCA estimator pathway) at a valid positive privacy budget. Verify whether the warning/error escapes before noise and how nonfinite intermediates are handled.
3. Re-run on draft PR #3281's head to verify that its finite-`row_norm_sq` guard does not protect the actual `float32` matmul.
4. Implement wide accumulation (and matching output dtype) or a rigorous representability check for every supported dtype; validate that the release path is warning-safe for all allowed bounded data.
