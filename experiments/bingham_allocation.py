"""Deterministic quadrature for rank-two sequential Bingham PCA utility.

Public synthetic spectra, idealized distribution. The objective is excess
rank-two reconstruction loss, not ordered eigenvector or whitening error.
The grid plus local refinement is a numerical search, not a proof of global
optimality. Set N higher to check quadrature convergence for large T.
"""
from functools import lru_cache

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import logsumexp, roots_jacobi
from threadpoolctl import threadpool_limits


@lru_cache(None)
def simplex_quad(d, N):
    # Squared Haar sphere coordinates are Dirichlet(1/2,...,1/2).
    nodes, weights = [], []
    for m in range(d, 1, -1):
        x, w = roots_jacobi(N, (m-3)/2, -.5)
        nodes.append((x+1)/2)
        weights.append(np.log(w/w.sum()))
    z = np.stack(np.meshgrid(*nodes, indexing="ij"), -1).reshape(-1, d-1)
    lw = np.stack(np.meshgrid(*weights, indexing="ij"), -1).reshape(-1, d-1).sum(1)
    rem = np.cumprod(np.c_[np.ones(len(z)), 1-z], axis=1)
    return np.c_[z*rem[:, :-1], rem[:, -1]], lw


def prepare(spectrum, N):
    # The conditional compressed spectrum depends only on squared
    # coordinates in the eigenbasis, not their signs.
    l = np.asarray(spectrum, dtype=float)
    d = len(l)
    z, lw = simplex_quad(d, N)
    u = np.sqrt(z)
    v = u.copy()
    v[:, 0] += 1
    Q = np.eye(d)[None, :, :] - 2*v[:, :, None]*v[:, None, :] / np.sum(v*v, axis=1)[:, None, None]
    P = Q[:, :, 1:]
    eig = np.linalg.eigvalsh(P.transpose(0, 2, 1) @ (l[None, :, None]*P))
    z2, lw2 = simplex_quad(d-1, N)
    return z@l, lw, eig@z2.T, lw2, sum(sorted(l)[-2:])


def loss(f, T, p, prep):
    # f is the first vector's fraction of privacy expenditure, p is
    # the concentration norm (1 for pure DP and 2 for zCDP).
    ray, lw, ray2, lw2, optimal = prep
    a, b = T*f**(1/p), T*(1-f)**(1/p)
    l1 = lw+a*ray
    l1 -= logsumexp(l1)
    l2 = lw2+b*ray2
    l2 -= logsumexp(l2, axis=1, keepdims=True)
    return optimal - np.exp(l1) @ (ray+np.einsum("ij,ij->i", np.exp(l2), ray2))


def optimize(T, p, prep):
    fs = np.linspace(0, 1, 13)
    ls = np.array([loss(f, T, p, prep) for f in fs])
    i = ls.argmin()
    f, val = fs[i], ls[i]
    if 0 < i < len(fs)-1:
        result = minimize_scalar(lambda f: loss(f, T, p, prep),
                                 bounds=(fs[i-1], fs[i+1]), method="bounded",
                                 options={"xatol": 1e-4})
        f, val = result.x, result.fun
    return f, val, loss(.5, T, p, prep)


@lru_cache(None)
def beta_quad(m, N=80):
    x, w = roots_jacobi(N, (m-3)/2, -.5)
    return (x+1)/2, np.log(w/w.sum())


def spike_loss(d, T, f, p, N=80):
    a, b = T*f**(1/p), T*(1-f)**(1/p)
    z, lw = beta_quad(d, N)
    z2, lw2 = beta_quad(d-1, N)
    prob = np.exp(lw+a*z-logsumexp(lw+a*z))
    q = 1-z
    logp = lw2[None, :] + b*q[:, None]*z2
    prob2 = np.exp(logp-logsumexp(logp, axis=1, keepdims=True))
    return prob @ (q*(prob2@(1-z2)))


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        print("spectrum, privacy norm, signal, first share, optimum loss, ratio to equal")
        for spectrum in ([1,0,0,0], [1,1,0,0], [1,.2,.1,0], [1,.8,.4,0]):
            prep = prepare(spectrum, 16)
            for p in (1,2):
                for T in (3,10,30,100):
                    f, val, equal = optimize(T, p, prep)
                    print(spectrum, p, T, f, val, val/equal)
        print("rank-one signal: dimension, privacy norm, signal, share, loss, ratio")
        for d in (4,8,32):
            for p in (1,2):
                for T in (.1,1,3,10,30,100,300):
                    fs = np.linspace(0,1,41)
                    vals = np.array([spike_loss(d,T,f,p) for f in fs])
                    i = vals.argmin()
                    f,val = fs[i],vals[i]
                    if 0<i<len(fs)-1:
                        result = minimize_scalar(lambda f: spike_loss(d,T,f,p),
                                                 bounds=(fs[i-1],fs[i+1]),method="bounded")
                        f,val = result.x,result.fun
                    print(d,p,T,f,val,val/spike_loss(d,T,.5,p))
