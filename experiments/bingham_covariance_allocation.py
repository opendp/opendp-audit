"""Rank-two sequential Bingham allocation, with privately released eigenvalues.

Compare uniform allocation, Amin-style square-root eigenvalue weighting,
and cumulative eigengap weighting derived for excess covariance error.
Conditional sphere integrals account for propagation through deflation.
Only the Laplace eigenvalue release is Monte Carlo. Public synthetic spectra,
idealized arithmetic; this is not a privacy test or a universal utility claim.
"""
from functools import lru_cache

import numpy as np
from scipy.special import logsumexp, roots_jacobi
from threadpoolctl import threadpool_limits

from bingham_allocation import simplex_quad


@lru_cache(None)
def spiked_quad(d, n):
    # Squared coordinates of two distinguished axes, with isotropic bulk.
    x, w = roots_jacobi(n, (d - 3) / 2, -.5)
    y, v = roots_jacobi(n, (d - 4) / 2, -.5)
    a, b = np.meshgrid((x + 1) / 2, (y + 1) / 2, indexing="ij")
    z = np.stack([a, (1 - a) * b, (1 - a) * (1 - b)], axis=-1).reshape(-1, 3)
    lw = (np.log(w / w.sum())[:, None] + np.log(v / v.sum())[None, :]).ravel()
    return z, lw


def overlaps(spectrum, d, concentration, shares, n, spiked=False):
    """Expected squared coordinates of each of two sequential draws."""
    l = np.asarray(spectrum, dtype=float)
    quad = spiked_quad if spiked else simplex_quad
    z, lw = quad(d, n)
    u = np.sqrt(z)
    v = u.copy()
    v[:, 0] += 1
    P = (
        np.eye(len(l))[None, :, :]
        - 2 * v[:, :, None] * v[:, None, :] / (v * v).sum(1)[:, None, None]
    )[:, :, 1:]
    eig, Q = np.linalg.eigh(P.transpose(0, 2, 1) @ (l[None, :, None] * P))
    z2, lw2 = quad(d - 1, n)
    if spiked:
        eig, Q = eig[:, ::-1], Q[:, :, ::-1]
        ray2 = eig @ z2[:, :2].T + l[2] * z2[:, 2]
        z2 = z2[:, :2]
    else:
        ray2 = eig @ z2.T
    basis = (P @ Q) ** 2
    ray = z @ l
    out = []
    for f in shares:
        lp = lw + concentration * f * ray
        w = np.exp(lp - logsumexp(lp))
        lp2 = lw2[None, :] + concentration * (1 - f) * ray2
        prob2 = np.exp(lp2 - logsumexp(lp2, axis=1, keepdims=True))
        v2 = (basis @ (prob2 @ z2)[:, :, None])[:, :, 0]
        if spiked:
            v2[:, 2] = 1 - v2[:, :2].sum(1)
        out.append(np.stack([w @ z, w @ v2]))
    return np.array(out)


def project_spectrum(a, cap):
    a = np.sort(a, axis=1)[:, ::-1]
    tau = np.maximum(0, ((a.cumsum(1) - cap) / np.arange(1, a.shape[1] + 1)).max(1))
    return np.maximum(a - tau[:, None], 0)


def first_share(w):
    return np.divide(w[:, 0], w.sum(1), out=np.full(len(w), .5), where=w.sum(1) > 0)


def evaluate(l, d, T, curve, rng, cap):
    """Return orientation loss, total covariance error, subspace loss, axis error."""
    spectrum = np.r_[l[:2], np.repeat(l[2], d - 2)] if len(l) == 3 else l
    # Equal eigenvalue and eigenvector epsilon: Laplace scale = 1/T.
    mu = project_spectrum(
        spectrum + rng.laplace(scale=1 / T, size=(10000, d)), cap
    )
    gaps = np.maximum(
        np.stack([(d - 1) * mu[:, 0] - mu[:, 1], (d - 2) * mu[:, 1]], axis=1), 0
    )
    policies = {
        "uniform": np.full(len(mu), .5),
        "gaps": first_share(np.sqrt(gaps)),
        "sqrt eigenvalue": first_share(np.sqrt(mu[:, :2])),
        "regularized gaps": first_share(np.sqrt(gaps + d / T)),
    }
    row = {}
    for name, f in policies.items():
        q = np.clip(f, 0, 1) * (len(curve) - 1)
        i = np.minimum(q.astype(int), len(curve) - 2)
        r = (q - i)[:, None, None]
        c = curve[i] * (1 - r) + curve[i + 1] * r
        ray = c @ l
        orientation = 2 * np.mean(np.sum(mu[:, :2] * (l[:2] - ray), axis=1))
        total = (
            np.mean(np.sum((mu[:, :2] - l[:2]) ** 2, axis=1))
            + np.sum(spectrum[2:] ** 2) + orientation
        )
        subspace = np.mean(l[:2].sum() - ray.sum(1))
        axes = np.mean(2 - c[:, 0, 0] - c[:, 1, 1])
        row[name] = np.array([orientation, total, subspace, axes])
    return row


def report(rows):
    for name in ("gaps", "sqrt eigenvalue", "regularized gaps"):
        ratios = np.array([r[name] / r["uniform"] for r in rows])
        print(name, "mean", ratios.mean(0), "max", ratios.max(0),
              "wins", (ratios < 1 - 1e-8).sum(0))


if __name__ == "__main__":
    shares = np.linspace(0, 1, 41)
    print("metrics: orientation, total covariance, subspace, ordered axes")
    with threadpool_limits(limits=1):
        rng = np.random.default_rng(801)
        rows = []
        for l in np.array([
            [1, 0, 0, 0], [1, 1, 0, 0], [1, .2, .1, 0],
            [1, .8, .4, 0], [1, .9, .8, .7], [1, .2, .19, .18],
            [1, .5, .49, 0],
        ]):
            for T in (1, 3, 10, 30, 100):
                c = overlaps(l, 4, T, shares, 16)
                rows.append(evaluate(l, 4, T, c, rng, l.sum()))
        print("general spectra, d=4")
        report(rows)
        rng = np.random.default_rng(802)
        for d in (8, 32):
            rows = []
            for g in (0, .1, .5, 1):
                l = np.array([1, g, 0])
                for t in (.125, .5, 1, 2, 5):
                    T = d * t
                    n = 40 if d == 32 and t >= 2 else 24
                    c = overlaps(l, d, T, shares, n, spiked=True)
                    row = evaluate(l, d, T, c, rng, 2 * l.sum())
                    rows.append(row)
                    print(d, g, t, row["gaps"] / row["uniform"],
                          row["sqrt eigenvalue"] / row["uniform"])
            print("spiked spectra, d=", d)
            report(rows)
