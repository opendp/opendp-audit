"""Compare Gaussian PCA consistency estimators on public synthetic data.

All methods receive the same idealized noisy augmented SSCP. This experiment
does not validate the production samplers or privacy implementation.
"""
import numpy as np
from scipy.optimize import brentq
from threadpoolctl import threadpool_limits


def project_augmented(matrix, c):
    diagonal = np.ones(len(matrix))
    diagonal[-1] = -1 / c**2
    D = np.diag(diagonal)

    def shifted_psd(t):
        values, vectors = np.linalg.eigh(matrix - t * D)
        values = np.maximum(values, 0)
        violation = values @ ((vectors**2).T @ diagonal)
        return violation, values, vectors

    violation, values, vectors = shifted_psd(0)
    if violation > 0:
        hi = max(1., np.linalg.norm(matrix) / np.linalg.norm(D))
        while shifted_psd(hi)[0] > 0:
            hi *= 2
        t = brentq(lambda t: shifted_psd(t)[0], 0, hi)
        _, values, vectors = shifted_psd(t)
    return (vectors * values) @ vectors.T


def clip(x):
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1)


def unpack(matrix, c):
    count = max(2., matrix[-1, -1] / c**2)
    sums = matrix[:-1, -1] / c
    mean = clip(sums / count)
    scatter = matrix[:-1, :-1] - np.outer(sums, mean) - np.outer(mean, sums)
    scatter += count * np.outer(mean, mean)
    return count, mean, scatter


def spectrum(scatter, count, penalty=None):
    values, vectors = np.linalg.eigh(scatter)
    values = np.maximum(values, 0)
    if penalty is not None:
        threshold = max(0., np.max(
            (np.cumsum(values[::-1]) - count)
            / (np.arange(1, len(values)+1) + penalty)
        ))
        values = np.maximum(values - threshold, 0)
        count += penalty * threshold
    return count, (vectors * values) @ vectors.T


def compare(d, n, rho, offset, count_share, trials=24):
    rng = np.random.default_rng(73+d+n+int(rho*100)+int(offset*1000))
    X = clip(rng.normal(size=(n,d))*np.r_[np.ones(3),np.full(d-3,.2)])
    X *= np.sqrt(1-offset**2)
    X[:,-1] = offset
    X = clip(X)
    s, G = X.sum(axis=0), X.T @ X
    mu = s/n
    C = G - n*np.outer(mu,mu)
    U = np.linalg.eigh(C)[1][:,-3:]
    # Effective marginal count share for add/remove adjacency:
    # c^4/(1+c^2)^2. Match 5% or use the dimension-based moment weight.
    if count_share is None:
        c = 1/(np.sqrt(2)*max(1,(d/4)**.25))
    else:
        c = (np.sqrt(count_share)/(1-np.sqrt(count_share)))**.5
    sigma = (1+c*c)/np.sqrt(2*rho)
    H = np.block([[G,(c*s)[:,None]],[(c*s)[None,:],np.array([[c*c*n]])]])
    errors = np.zeros((5,5))
    for _ in range(trials):
        Z = rng.normal(size=H.shape)*sigma/2
        Y = H + Z + Z.T
        count, mean, scatter = unpack(Y,c)
        P = project_augmented(Y,c)
        pc, pm, ps = unpack(P,c)
        assert np.linalg.eigvalsh(P).min() > -1e-8
        assert np.trace(P[:-1,:-1]) <= P[-1,-1]/c**2 + 1e-7
        assert np.linalg.norm(P-H)**2 <= np.linalg.norm(Y-H)**2 + 1e-7

        _, psd = spectrum(scatter,count)
        _, hard = spectrum(scatter,count,0)
        sc, soft = spectrum(scatter,count,1/c**4)
        _, anchored = spectrum(scatter,count*max(0.,1-np.dot(mean,mean)),0)
        for i, (nc,m,A) in enumerate([
            (count,mean,psd),
            (count,mean,hard),
            (sc,mean,soft),
            (pc,pm,ps),
            (count,mean,anchored),
        ]):
            V = np.linalg.eigh(A)[1][:,-3:]
            errors[i] += [
                abs(nc-n)/n,
                np.linalg.norm(m-mu),
                np.linalg.norm(A-C)/np.linalg.norm(C),
                np.linalg.norm(A/max(nc-1,1)-C/(n-1))/np.linalg.norm(C/(n-1)),
                1-np.linalg.norm(U.T@V,'fro')**2/3,
            ]
    return errors/trials


if __name__ == '__main__':
    with threadpool_limits(limits=1):
        print('Methods: PSD, hard trace, soft count/trace, full joint, anchored mean/count')
        print('Errors: relative count, mean, scatter, covariance, subspace')
        for share in (None,.05):
            results = []
            for d in (8,32,128):
                for n in (30,100,500):
                    for rho in (.1,1):
                        for offset in (0,.6):
                            e = compare(d,n,rho,offset,share)
                            results.append(e)
                            if (d,n,rho,offset)==(128,100,1,0):
                                print('EXAMPLE',share,np.round(e,4))
                a = np.array(results[-12:])
                print('DIM',share,d,'median ratios to PSD',
                      np.round(np.median(a[:,1:]/a[:,:1],axis=0),3))
            a = np.array(results)
            print('ALL',share,'median ratios to PSD',
                  np.round(np.median(a[:,1:]/a[:,:1],axis=0),3),
                  'wins',(a[:,1:]<a[:,:1]).sum(axis=0))
