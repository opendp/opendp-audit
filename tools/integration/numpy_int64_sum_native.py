"""Native-wheel diagnostic for NumPy int64 summation.

Requires opendp==0.16.0a20261122001 and numpy.
This runs actual OpenDP Python/FFI objects and prints exact outcomes.
A failed privacy map is reported rather than mistaken for a DP violation.
"""
from __future__ import annotations

import numpy as np
import opendp.prelude as dp
from opendp.extras.numpy._make_np_sum import make_np_sum, make_private_np_sum


V = 1 << 60
X = np.full((8, 1), V, dtype=np.int64)
XP = X.copy()
XP[0, 0] = 0


def probe(label, f):
    try:
        result = f()
        print(f"{label}: SUCCESS: {result!r}", flush=True)
        return (True, result)
    except Exception as err:
        print(f"{label}: ERROR: {type(err).__name__}: {err}", flush=True)
        return (False, err)


def main():
    print(f"OpenDP version: {getattr(dp, '__version__', 'unknown')}", flush=True)
    print(f"NumPy version: {np.__version__}", flush=True)
    dp.enable_features("contrib", "idealized-numerics")

    domain = dp.numpy.array2_domain(
        T="i64", norm=float(V), p=1, size=8, num_columns=1, nan=False
    )
    metric = dp.symmetric_distance()
    print("Declared space:", domain, metric, flush=True)

    for label, data in (("x", X), ("x_prime", XP)):
        accepted, value = probe(f"domain.member({label})", lambda data=data: domain.member(data))
        assert accepted and value is True, f"domain did not accept {label}"

    ok, trans = probe("make_np_sum", lambda: make_np_sum(domain, metric))
    if not ok:
        raise AssertionError("The reported transformation cannot be constructed") from trans

    for label, data, expected in (
        ("x", X, -(1 << 63)),
        ("x_prime", XP, 7 * V),
    ):
        result_ok, output = probe(f"sum({label})", lambda data=data: trans(data))
        assert result_ok, f"native invocation failed on {label}: {output}"
        assert int(np.asarray(output)[0]) == expected

    map_ok, mapped = probe("transformation.map(d_in=2)", lambda: trans.map(2))
    if map_ok:
        # An integer map return is required, but the current source callback
        # computes a Python float. Flag accepted maps for manual scrutiny.
        print("MAP_SUCCEEDED; compare returned bound to 15*2**60", flush=True)
        assert mapped >= 15 * V, "Native map underestimates actual output change"
    else:
        print("MAP_REJECTED; this blocks an advertised native epsilon witness", flush=True)

    # Construction does not necessarily invoke the privacy map; probe it
    # separately to avoid claiming a valid private release if checking fails.
    m_ok, measurement = probe(
        "make_private_np_sum",
        lambda: make_private_np_sum(
            domain, metric, dp.max_divergence(), float(V)
        ),
    )
    if m_ok:
        _, _ = probe("private_sum.map(d_in=2)", lambda: measurement.map(2))


if __name__ == "__main__":
    main()
