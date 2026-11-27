"""Direct Grassmann Bingham feasibility on public synthetic spectra.

Idealized NumPy proposals, not production sampling or a privacy validation.
Estimate the acceptance rate as the mean conditional acceptance probability.
Report effective sample size to flag unreliable rare-event estimates.
For rank-one spike utility, use deterministic beta quadrature for Bingham
and Monte Carlo for SSCP; compare direction-only replacement privacy budgets.
"""
from functools import lru_cache

import numpy as np
from scipy.optimize import brentq
from scipy.special import logsumexp, multigammaln, roots_jacobi
from threadpoolctl import threadpool_limits


def high_log_acceptance(d, k):
    """High-concentration limit for k equally strong spikes."""
    m = k * (d - k)
    return (
        multigammaln(d / 2, k) - multigammaln(k / 2, k)
        + m / 2 * (1 + np.log(2 / d))
        + k * k / 2 * np.log(k / d)
    )


def macg(d, k, T, N=8192, seed=42):
    rng = np.random.default_rng(seed)
    a = np.r_[np.zeros(k), np.full(d - k, T)]
    b = brentq(lambda b: np.sum(1 / (b + 2 * a)) - 1, .999999, d + 1e-8)
    w = b + 2 * a
    u0 = (d - b) / 2

    def h(x):
        return -x + d / 2 * np.log1p(2 * x / b)

    # Bound each Ritz value using both sides of interlacing.
    logM = h(np.clip(u0, a[:k], a[d-k:])).sum()
    sum_p = sum_p2 = 0.
    for i in range(0, N, 512):
        n = min(512, N - i)
        y = rng.normal(size=(n, d, k)) / np.sqrt(w)[None, :, None]
        q = np.linalg.qr(y, mode="reduced")[0]
        u = np.linalg.eigvalsh(q.transpose(0, 2, 1) @ (a[None, :, None] * q))
        lp = h(u).sum(1) - logM
        assert lp.max() < 1e-9
        p = np.exp(lp)
        sum_p += p.sum()
        sum_p2 += p @ p
    return sum_p / N, sum_p**2 / sum_p2


@lru_cache(None)
def beta_quad(a, b, N=100):
    x, w = roots_jacobi(N, b-1, a-1)
    return (x+1)/2, np.log(w/w.sum())


def direct_loss(d, k, T):
    z, lw = beta_quad(k/2, (d-k)/2)
    return np.exp(lw+T*z-logsumexp(lw+T*z)) @ (1-z)


def seq_loss(d, T, f, p):
    z, lw = beta_quad(.5, (d-1)/2)
    z2, lw2 = beta_quad(.5, (d-2)/2)
    a, b = T*f**(1/p), T*(1-f)**(1/p)
    probs = np.exp(lw+a*z-logsumexp(lw+a*z))
    q = 1-z
    lp = lw2[None, :] + b*q[:, None]*z2
    p2 = np.exp(lp-logsumexp(lp, axis=1, keepdims=True))
    return probs @ (q*(p2@(1-z2)))


def sscp_loss(d, T, p, N=512):
    rng = np.random.default_rng(123)
    m = d*(d+1)//2
    # Replacement sensitivity: 2R² score range, sqrt(2)R² Frobenius.
    scale = (np.sqrt(m/2) if p == 1 else np.sqrt(2))/T
    i, j = np.triu_indices(d)
    draw = rng.laplace if p == 1 else rng.normal
    total = 0.
    for off in range(0, N, 32):
        n = min(N-off, 32)
        e = draw(size=(n, m))*scale
        e[:, i != j] /= np.sqrt(2)
        A = np.zeros((n, d, d))
        A[:, i, j] = A[:, j, i] = e
        A[:, 0, 0] += 1
        _, v = np.linalg.eigh(A)
        total += np.sum(1-np.sum(v[:, 0, -2:]**2, axis=1))
    return total/N


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        for d in (8, 32, 128, 512):
            for k in (1, 2, 4, 8):
                if 2*k > d:
                    continue
                print("limit", d, k, np.exp(high_log_acceptance(d, k)))
                if d <= 128:
                    for T in (1, 10, 100, 1000):
                        print("acceptance", d, k, T, *macg(d,k,T))
        for d in (8,32,128):
            for T in (1,10,100):
                for p in (1,2):
                    seq = min(seq_loss(d,T,f,p) for f in np.linspace(0,1,81))
                    print("utility", d,T,p,direct_loss(d,2,T),seq,sscp_loss(d,T,p))
