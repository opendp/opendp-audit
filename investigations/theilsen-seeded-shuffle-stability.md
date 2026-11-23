---
schema_version: 1
upstream_commit: a010591f55b1713c926f8e355091471634480307
updated: 2026-11-23
status: Partial
---

# Theil-Sen: public NumPy shuffle seed violates a pointwise stability map

## Property and scope

The current non-deprecated Theil-Sen estimator uses `make_pairwise_predict` to turn an input multiset of `(x,y)` rows into a multiset of two-column secant predictions. With `size=None` and `runs=1`, it declares `stability_map=lambda d_in: 2*d_in` under symmetric (insert/delete) distance. In particular, one added input record is charged **2** output insertions/deletions. The construction subsequently privately selects quantiles of the two prediction columns.

This audit asks whether that **claimed pointwise bound** holds under the concrete, externally seedable `np.random.shuffle(data)` implementation. The answer is no. This is *not* a proof that the whole randomized estimator violates its DP guarantee when using a hidden, independent uniform shuffle: probabilistic coupling can potentially justify a bound in distribution. However, OpenDP's transformation API is presented as a deterministic stability contract, and the actual shuffle is governed by a public, globally settable NumPy PRNG state. This makes conditional/private-map reasoning require additional assumptions that the transformation constructor does not document.

The earlier [Theil-Sen warning side-channel audit](theil-sen-private-warning-side-channel.md) is a separate defect: it concerns data-dependent warnings before the private quantile. This investigation concerns the **size-dependent pairing permutation** and public seed, and uses only finite nondegenerate rows without warnings.

## Cross-file source and existing upstream coverage

- [Current `pairwise_predict` and `make_pairwise_predict`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/sklearn/linear_model/_make_private_theil_sen/__init__.py): calls `np.random.shuffle(data)`, truncates odd-sized data, splits its first/second halves, and predicts from each pair. The map is `2*d_in*runs` when `size=None`.
- [OpenDP's related upstream issue #2928](https://github.com/opendp/opendp/issues/2928): notes the framework describes transformations as **deterministic**, with randomized stability/coupling not formally specified. This is the existing broader issue; no duplicate candidate was filed.
- [Upstream issue #2950](https://github.com/opendp/opendp/issues/2950): specifically recognized add-one-row instability in the earlier truncation implementation and was closed after the stability map changed; its text explicitly references #2928. The present counterexample demonstrates that a 2-bound **still fails pointwise for a globally seeded shuffle**.
- [Open PR #2845](https://github.com/opendp/opendp/pull/2845) replaces `np.random.shuffle` with `get_np_csprng().shuffle(indices)` in a refactored `pairwise_slopes`. This prevents the user's `np.random.seed` from directly determining the pairing. It is **pending**, not present in the audited `main`, and does not by itself formalize randomized transformations or establish a general pointwise 2-bound for independent random draws.

## Executed minimal witness

Run the following against NumPy 2.3.5, using the same public seed before each neighboring execution:

```python
from collections import Counter
import numpy as np

def pairwise_predict(data, x_cuts):
    # Exact arithmetic, shuffle, truncation and pairing from pinned source.
    data = np.array(data, copy=True, dtype=np.float64)
    np.random.shuffle(data)
    data = data[:len(data) // 2 * 2]
    p1, p2 = np.array_split(data, 2)
    dx, dy = (p2 - p1).T
    x_bar, y_bar = (p1 + p2).T / 2
    points = dy / dx * (x_cuts[None].T - x_bar) + y_bar
    return points.T[dx != 0]

X = np.array([[float(i), float(i * i)] for i in range(1, 11)])
Y = np.vstack([X, [11., 121.]])
cuts = np.array([0., 2.])
np.random.seed(42)
a = pairwise_predict(X, cuts)
np.random.seed(42)
b = pairwise_predict(Y, cuts)

ac, bc = Counter(map(tuple, a)), Counter(map(tuple, b))
actual = sum((ac - bc).values()) + sum((bc - ac).values())
assert actual == 10            # source model: five old and five new pairs, disjoint
assert 2 * 1 * 1 == 2          # declared map(1), runs=1, size=None
assert actual > 2
```

Output from the executed Python/NumPy check:

```text
X predictions:
[[-27., -3.], [-20., 4.], [-30., -8.], [-4., 6.], [-56., -26.]]
Y predictions:
[[-12., 4.], [-9., 11.], [-50., -20.], [-88., -50.], [-12., 2.]]
input symmetric distance: 1
output symmetric distance: 10
declared map(1): 2
```

The values are finite and no `dx==0` degenerate-pair warnings occur. Their distinct secant outputs form multisets, hence output distance 10. The only changed private data is one added row `(11,121)`, and all original input rows persist identically. The NumPy global `seed(42)` is public and reproducible.

**Control:** Replacing `(10,100)` with `(20,400)` without changing the input length, then resetting seed 42, changes only one matching pair; the output symmetric distance is 2, matching the fixed-size replacement map `2*(2//2)=2`. The severe mismatch specifically exploits the **batch-size-dependent permutation of existing records**.

Independent [source-equivalent audit regression](../tools/tests/test_theilsen_seeded_shuffle_model.py) tests the witness and a same-size control, preserving the caller's NumPy global state. On alternative NumPy kernels where this specific seed produces a different permutation, the failing-witness test skips rather than asserting a universal 10-distance outcome.

## Privacy interpretation and limitations

The map's **pointwise** stability claim is violated for a legitimate, externally selected NumPy RNG state. If the global seed is predictable to an adversary controlling the environment or observable through another process component, the random shuffle is not a secrecy resource. A downstream private quantile calibrated solely to the alleged 2-change guarantee may therefore be undercalibrated for that fixed execution. This investigation **does not quantify any full measurement's likelihood ratio or show an unconditional (ε,δ)-DP failure**; that requires analyzing the actual quantile mechanism and the distribution/reachability of the random pairing state.

A different proof may hold in a model that treats the shuffle as hidden independent randomization and establishes a stochastic coupling of neighboring executions. Such a model is not the simple deterministic `Transformation` stability law and is the subject of [upstream #2928](https://github.com/opendp/opendp/issues/2928). Replacing the PRNG with a CSPRNG as in pending [PR #2845](https://github.com/opendp/opendp/pull/2845) reduces public-seed predictability; however, formal random-transformation semantics and end-to-end accounting still require validation.

**Executed:** NumPy 2.3.5 full pairwise source-equivalent function on two neighboring datasets and a replacement control, output multiset comparison. **Not executed:** native OpenDP FFI, `make_user_transformation.map`, the downstream private-quantile distribution, or the pending PR's actual CSPRNG integration.

## Findings and follow-up

**Disposition:** Reproduced source-model counterexample. **Upstream status:** Existing broader issue [#2928](https://github.com/opendp/opendp/issues/2928) and pending mitigation [PR #2845](https://github.com/opendp/opendp/pull/2845); do not file a duplicate candidate issue.

1. Native regression: call `make_pairwise_predict` with `size=None` using both datasets, invoke it under the same external NumPy seed, and compare output distances against `map(1)`.
2. Check that pending #2845's `get_np_csprng` is not manipulable through `np.random.seed` and that its revised stability map is justified by a formally specified probabilistic coupling.
3. Either move randomized pairing into a measurement with explicit randomization and privacy analysis, or extend the transformation proof framework to formalize the intended coupling.
4. Evaluate whether source-exposed RNG state can be observed, fixed or shared by adversaries in supported environments. Avoid assuming an unobserved seed is always secret.
