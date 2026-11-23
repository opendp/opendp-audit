---
schema_version: 1
upstream_commit: 7acfb2cdcee7d39fc26a6ade7edac15249c52f4b
updated: 2026-11-23
status: Partial
---

# Negative epsilon in Python DP eigenvector sampling

## Invariant and threat model

For any successfully constructed `MaxDivergence` measurement and any valid distance `d >= 0`, the privacy map must conservatively upper-bound the actual divergence and must not be negative. The lower-level `make_private_eigenvector`/ `then_private_eigenvector` API is reachable by a caller supplying public `unit_epsilon`; downstream composition may trust the resulting reported privacy loss. The scope excludes the full correctness proof of the Bingham sampler, `make_np_sscp_projection` contractivity (separately claimed in audit task #107), and the ordinary sklearn wrapper's budget validation.

## Affected symbols and source audits

- [`make_private_eigenvector`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/python/src/opendp/extras/sklearn/_make_eigenvector/__init__.py) accepts `unit_epsilon` without a nonnegativity/finite-value check. The privacy callback is `lambda d_in: d_in / 2 * unit_epsilon`; the sampler computes `A = unit_epsilon / 4 * (lambda_max(C)*I-C)` and samples based on `A`.
- [`_make_measurement` C adapter](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/internal/mod.rs) forwards this callback to Rust `Measurement::new` without validating privacy bounds.
- [`Measurement::new` / `Measurement::check`](https://github.com/opendp/opendp/blob/7acfb2cdcee7d39fc26a6ade7edac15249c52f4b/rust/src/core/mod.rs) only validate the metric space at construction; `check` compares the caller's allowance against the callback's negative output.
- Local source report: [`source/python/src/opendp/extras/sklearn/_make_eigenvector/__init__.py.md`](../source/python/src/opendp/extras/sklearn/_make_eigenvector/__init__.py.md).

## Reasoning and evidence

**Construction-level witness (source-confirmed):**

```python
import opendp.prelude as dp
from opendp.extras.numpy import _sscp_domain
from opendp.extras.sklearn._make_eigenvector import then_private_eigenvector

dp.enable_features("contrib", "idealized-numerics")
domain = _sscp_domain(num_features=2, norm=1.0, p=2, T=float)
meas = (domain, dp.symmetric_distance()) >> then_private_eigenvector(-0.2)
assert meas.map(2) == -0.2
assert meas.check(2, 0.0)
```

This is a **proposed** OpenDP regression; native OpenDP was **not** run in this audit.

**Distribution-level independent numerical witness (executed using NumPy/SciPy, not OpenDP):** Consider bounded singleton samples with row vectors `(1,0)` and `(0,1)`, represented by `C0=diag(1,0)` and `C1=diag(0,1)`; one replacement corresponds to the intended input distance 2. For `unit_epsilon=-0.2`, the sampler computes `A0=diag(0,-0.05)` and `A1=diag(-0.05,0)`. The Bingham target density is proportional to `exp(-u.T @ A @ u)`, so at `u=(1,0)` its ratio `p(u|C1)/p(u|C0)=exp(0.05)=1.0512710963760241`. Since the densities are continuous, a small positive-measure neighborhood also has positive likelihood ratio. Hence the actual privacy loss cannot be upper-bounded by `-0.2` (or any negative value). The symmetry of the two matrices makes their normalization constants equal.

The parameterized rejection sampler remains algebraically well-formed in this example. Solving the source's equation `sum_i 1/(b+2*A_eigval_i) = 1` within its search window gives `b=2.0512492197250394`; `eig(Omega)=(0.95124922,1)`, and the acceptance probabilities at the two basis axes lie between `0.9996772447063392` and `0.9996980481369335`. These were numerical checks of the formulas only; no full distribution test or library execution was performed.

**Impact:** This is a privacy-map underestimation rather than solely an availability bug. A negative reported epsilon can be combined with positive loss, potentially reducing the accounted total of a composite measurement. The ordinary `make_private_pca` float-budget path invokes `_smaller`, which rejects negative values; exploitation through that particular path has not been demonstrated.

## Findings

- [Audit defect #112](https://github.com/opendp/opendp-audit/issues/112): **source-confirmed** violation, **unreported upstream**, pending native regression and remediation.
- [Bounded audit task #109](https://github.com/opendp/opendp-audit/issues/109).

## Unresolved questions

1. Execute the proposed OpenDP regression in an environment with the native library and Python extras installed.
2. Add guards for nonnegative finite `unit_epsilon` in the lower-level constructor and validate entries in `make_private_eigenvectors`/structured `PCAEpsilons` paths.
3. Audit edge cases `0`, NaN, and infinity, plus whether the existing composition API makes negative accounting externally exploitable in a concrete end-to-end example.
