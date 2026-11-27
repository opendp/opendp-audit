"""Public synthetic, idealized-numerics PCA utility comparison.

This is not a sampler validation or a privacy test. Compare at fixed count,
unit clipping radius, equal privacy loss, public origin for solver comparison.
For centering, compare against the centered scatter of originally clipped rows.
Run with numpy, scipy, threadpoolctl installed.
"""
import numpy as np
from scipy.linalg import null_space
from scipy.optimize import brentq
from threadpoolctl import threadpool_limits


def symmetric_noise(rng, d, scale, gaussian):
    upper = np.triu_indices(d)
    offdiag = upper[0] != upper[1]
    draw = rng.normal if gaussian else rng.laplace
    values = draw(size=len(offdiag)) * scale
    values[offdiag] /= np.sqrt(2)
    E = np.zeros((d, d))
    E[upper] = values
    E[(upper[1], upper[0])] = values
    return E


def clip(X):
    return X / np.maximum(np.linalg.norm(X, axis=-1, keepdims=True), 1)


def centered_comparison(rng, d, n, offset, rho, trials=100):
    X = clip(rng.normal(size=(n, d)) * np.r_[np.ones(3), np.full(d-3, .2)])
    X *= np.sqrt(1-offset**2)
    X[:, -1] = offset
    S, G = X.sum(axis=0), X.T @ X
    mu = S / n
    C = G - n * np.outer(mu, mu)
    U = np.linalg.eigh(C)[1][:, -3:]
    for method, r in [
        ("adaptive", None),
        ("joint-equal", np.sqrt(2)),
        ("joint-weighted", max(1, (d/4)**.25)),
    ]:
        errors = []
        for _ in range(trials):
            if r is None:
                m = clip(mu + rng.normal(size=d) * 2 / np.sqrt(2*rho/3) / n)
                Z = clip(X - m)
                A = Z.T @ Z + symmetric_noise(rng, d, np.sqrt(2)/np.sqrt(4*rho/3), True)
            else:
                scale = np.sqrt((2+2/r**2+.5/r**4)/(2*rho))
                s = S + rng.normal(size=d) * r * scale
                m = clip(s/n)
                A = G + symmetric_noise(rng, d, scale, True)
                A += n*np.outer(m,m) - np.outer(s,m) - np.outer(m,s)
            V = np.linalg.eigh(A)[1][:, -3:]
            errors.append([
                np.linalg.norm(A-C, "fro") / np.linalg.norm(C, "fro"),
                1-np.linalg.norm(U.T@V, "fro")**2/3,
                np.linalg.norm(m-mu),
            ])
        print("moments", d, n, offset, rho, method, np.mean(errors, axis=0))


def bingham(rng, C, k, concentration):
    d = len(C)
    P = np.eye(d)
    basis = []
    for _ in range(k):
        if P.shape[1] == 1:
            basis.append(P[:, 0])
            break
        l, Q = np.linalg.eigh(P.T @ C @ P)
        a = concentration * (l[-1]-l)
        n = len(l)
        b = brentq(lambda b: np.sum(1/(b+2*a))-1, .9, n+.1)
        w = b+2*a
        while True:
            z = rng.normal(size=n)/np.sqrt(w)
            u = z/np.linalg.norm(z)
            t = np.dot(w, u*u)/n
            if np.log(rng.random()) <= n/2*(np.log(t)+1-t):
                break
        basis.append(P@Q@u)
        P = null_space(np.array(basis))
    return np.array(basis).T


def solver_comparison(rng, d, n, k, loss, gaussian, trials=30):
    X = clip(rng.normal(size=(n,d))*np.r_[np.ones(k), np.full(d-k,.25)])
    C = X.T@X
    l, Q = np.linalg.eigh(C)
    U = Q[:, -k:]
    m = d*(d+1)//2
    nvec = min(k,d-1)
    if gaussian:
        scale = np.sqrt(2)/np.sqrt(2*loss)
        concentration = np.sqrt(8*(loss/2)/nvec)/2
        eig_scale = np.sqrt(2)/np.sqrt(loss)
        draw = rng.normal
    else:
        scale = np.sqrt(2*m)/loss
        concentration = (loss/2)/nvec/2
        eig_scale = 2/(loss/2)
        draw = rng.laplace
    errors = []
    for _ in range(trials):
        a, V = np.linalg.eigh(C+symmetric_noise(rng,d,scale,gaussian))
        B = bingham(rng,C,k,concentration)
        noisy_l = np.sort(l+draw(size=d)*eig_scale)
        errors.append([
            1-np.linalg.norm(U.T@V[:, -k:], "fro")**2/k,
            1-np.linalg.norm(U.T@B, "fro")**2/k,
            np.linalg.norm(np.maximum(a,0)-l)/np.linalg.norm(l),
            np.linalg.norm(np.maximum(noisy_l,0)-l)/np.linalg.norm(l),
        ])
    print("solvers", "rho" if gaussian else "epsilon", d,n,k,loss, np.mean(errors,axis=0))


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        rng = np.random.default_rng(42)
        print("moments: relative scatter error, subspace loss, mean error")
        for d in (8,32,128):
            for offset in (0,.6):
                centered_comparison(rng,d,500,offset,1)
        rng = np.random.default_rng(200)
        print("solvers: SSCP/Bingham subspace loss, SSCP/Bingham spectrum error")
        for gaussian in (True,False):
            for d in (8,32,64):
                for k in (1,d//4,d//2):
                    solver_comparison(rng,d,500,k,1,gaussian)
