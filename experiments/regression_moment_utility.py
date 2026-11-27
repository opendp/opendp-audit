"""Public synthetic regression utility comparison at unit feature/target bounds.

Idealized noise; not production sampling or privacy validation.
Run with numpy, scipy, threadpoolctl. All candidates use the PR #3282 floor.
"""
import numpy as np
from threadpoolctl import threadpool_limits

METHODS = ["baseline", "cross-half", "cross-double", "centered",
           "centered-trace", "augmented", "full-consistency", "anchored-consistency"]


def clip(X):
    return X / np.maximum(1, np.linalg.norm(X, axis=-1, keepdims=True))


def noise(draw, d):
    i, j = np.triu_indices(d)
    z = draw(size=len(i))
    z[i != j] /= np.sqrt(2)
    A = np.empty((d, d))
    A[i, j] = A[j, i] = z
    return A


def floor(d, s, gaussian):
    t = np.log(d / .05)
    if gaussian:
        return s * min(np.sqrt(2*d) + np.sqrt(-2*np.log(.05)), np.sqrt((d+1)*t))
    u = np.sqrt(2*t / (d+2*t))
    return s * min((t - np.log1p(-u*u) - (d-1)*np.log1p(-u*u/2))/u,
                   d*np.log(d*(d+1)/2/.05))


def solve(G, b, s, gaussian):
    l, V = np.linalg.eigh(G)
    return V @ ((V.T @ b) / np.maximum(l, floor(len(G), s, gaussian)))


def scales(d, budget, gaussian, fixed, r):
    # Squared normalized joint L2 sensitivity for r >= 1/2.
    sq = 1 + 1/(2*r*r) + 1/(16*r**4) if fixed else 1 + 1/r**2
    gu = 2 * (np.sqrt(2) if fixed else 1)
    bu = np.sqrt(2) * (2 if fixed else 1)
    if gaussian:
        a = np.sqrt(sq/(2*budget))
    else:
        gu *= np.sqrt(d*(d+1)/2)
        bu *= np.sqrt(d)
        a = min(1+1/r, np.sqrt(2*sq))/budget
    return gu*a, bu*a*r


def project(A, constraints):
    """Dual Frobenius projection onto PSD with diagonal constraints."""
    from scipy.optimize import minimize

    scale = max(1., np.linalg.norm(A))
    A = A/scale
    V = np.stack([v for v, b, eq in constraints])
    b = np.array([b for v, b, eq in constraints])/scale
    norm = np.linalg.norm(V, axis=1)
    V = V/norm[:, None]
    b = b/norm
    ix = np.diag_indices(len(A))

    def evaluate(t):
        Y = A.copy()
        Y[ix] -= t @ V
        l, Q = np.linalg.eigh(Y)
        l = np.maximum(l, 0)
        diagonal = (Q*Q) @ l
        return .5*(l@l) + t@b, b-V@diagonal

    result = minimize(evaluate, np.zeros(len(b)), jac=True, method="L-BFGS-B",
                      bounds=[(None,None) if eq else (0,None) for v,b,eq in constraints],
                      options={"ftol":1e-14, "gtol":1e-10, "maxiter":250})
    Y = A.copy()
    Y[ix] -= result.x @ V
    l, Q = np.linalg.eigh(Y)
    X = (Q*np.maximum(l,0)) @ Q.T * scale
    residual = max(abs(v@X[ix]-b) if eq else max(0,v@X[ix]-b)
                   for v,b,eq in constraints)
    return X, residual


def center(G, b, n):
    n = max(2., n)
    S = G[:-1,-1]
    m = clip(S/n)
    y = np.clip(b[-1]/n, -1, 1)
    C = G[:-1,:-1] - np.outer(S,m) - np.outer(m,S) + n*np.outer(m,m)
    v = b[:-1] - S*y - m*b[-1] + n*m*y
    return C,v,m,y,n


def traced(C, bound):
    l,V = np.linalg.eigh(C)
    l = np.maximum(l,0)
    t = max(0, np.max((np.cumsum(l[::-1])-bound)/np.arange(1,len(l)+1)))
    return (V*np.maximum(l-t,0)) @ V.T


def dataset(rng, d, n, cond):
    Q,_ = np.linalg.qr(rng.normal(size=(d,d)))
    s = np.geomspace(1,1/cond,d)

    def features(n):
        return clip((rng.normal(size=(n,d))*s)@Q.T/np.sqrt(d)+.25*Q[:,0])

    X = features(n)
    Z = features(300)
    beta = Q@rng.normal(size=d)
    beta /= np.linalg.norm(beta)
    y = np.clip(X@beta+.15+rng.normal(size=n)*.08,-1,1)
    target = Z@beta+.15
    return np.c_[X,np.ones(n)], np.c_[Z,np.ones(len(Z))], y, target, beta


def compare(d,n,budget,g,fixed,cond,trials=8):
    rng = np.random.default_rng(82+d+n+int(budget*1000)+int(cond*10)+fixed)
    X,Z,y,target,beta = dataset(rng,d,n,cond)
    G,b = X.T@X,X.T@y
    w = 1/np.sqrt(2)
    H = np.c_[X,w*y]
    H = H.T@H
    draw = rng.normal if g else rng.laplace
    errors = np.zeros((len(METHODS),3))
    residual = np.zeros(2)
    for _ in range(trials):
        eg,eb = noise(draw,d+1),draw(size=d+1)
        estimates = []
        for r in (1,.5,2):
            gs,bs = scales(d+1,budget,g,fixed,r)
            A,v = G+gs*eg,b+bs*eb
            if fixed:
                A[-1,-1] = n
            estimates.append(solve(A,v,gs,g))
            if r == 1:
                C,u,m,ym,nc = center(A,v,A[-1,-1])
                centered = []
                for M in (C,traced(C,nc*max(0,1-m@m))):
                    bh = solve(M,u,gs,g)
                    centered.append(np.r_[bh,ym-m@bh])
        estimates += centered
        # Generic augmented Frobenius sensitivity, tight for d >= 2.
        delta = (np.sqrt(2) if fixed else 1)*(2+w*w)
        gs = delta/np.sqrt(2*budget) if g else delta*np.sqrt((d+2)*(d+3)/2)/budget
        E = np.zeros_like(H)
        E[:-1,:-1] = eg
        E[:-1,-1] = E[-1,:-1] = eb/np.sqrt(2)
        E[-1,-1] = draw()
        A = H+gs*E
        if fixed:
            A[-2,-2] = n
        estimates.append(solve(A[:-1,:-1],A[:-1,-1]/w,gs,g))
        constraints = [(np.r_[np.ones(d),-1.,0.],0,False),
                       (np.r_[np.zeros(d),-w*w,1.],0,False)]
        if fixed:
            constraints.append((np.r_[np.zeros(d),1.,0.],n,True))
        P,err = project(A,constraints)
        residual[0] = max(residual[0],err/max(1,np.linalg.norm(A)))
        estimates.append(solve(P[:-1,:-1],P[:-1,-1]/w,gs,g))
        nc = max(2.,A[-2,-2])
        ids = np.r_[np.arange(d),d+1]
        S = A[ids,d]
        m = S/nc
        m[:-1] = clip(m[:-1])
        m[-1] = np.clip(m[-1],-w,w)
        C = A[np.ix_(ids,ids)]-np.outer(S,m)-np.outer(m,S)+nc*np.outer(m,m)
        P,err = project(C,[(np.r_[np.ones(d),0.],nc*max(0,1-m[:-1]@m[:-1]),False),
                           (np.r_[np.zeros(d),1.],nc*max(0,w*w-m[-1]**2),False)])
        residual[1] = max(residual[1],err/max(1,np.linalg.norm(C)))
        bh = solve(P[:-1,:-1],P[:-1,-1]/w,gs,g)
        estimates.append(np.r_[bh,m[-1]/w-m[:-1]@bh])
        for i,t in enumerate(estimates):
            errors[i] += [np.mean((Z@t-target)**2),
                          np.linalg.norm(t[:-1]-beta)**2,(t[-1]-.15)**2]
    return errors/trials,residual


def configs():
    for d in (8,32,64):
        for n in (100,1000):
            for budget in (.1,1,10):
                for fixed in (True,False):
                    for cond in (1,20):
                        yield d,n,budget,fixed,cond


def weighting(d,n,budget,fixed,cond,trials=12):
    # Regenerate the dataset every trial, and separate weighting from floor tuning.
    rng = np.random.default_rng(17+d+n+int(budget*1000)+int(cond*10)+fixed)
    ratios = [1.,.5,.75,1.25,1.5]
    errors = np.zeros(len(ratios)+3)
    for _ in range(trials):
        X,Z,y,target,_ = dataset(rng,d,n,cond)
        G,b = X.T@X,X.T@y
        eg,eb = noise(rng.normal,d+1),rng.normal(size=d+1)
        for i,r in enumerate(ratios):
            gs,bs = scales(d+1,budget,True,fixed,r)
            A,v = G+gs*eg,b+bs*eb
            if fixed:
                A[-1,-1] = n
            l,V = np.linalg.eigh(A)
            q = V.T@v
            f = floor(d+1,gs,True)

            def error(f):
                return np.mean((Z@(V@(q/np.maximum(l,f)))-target)**2)

            errors[i] += error(f)
            if i == 0:
                for j,factor in enumerate((.5,1.5,2.)):
                    errors[len(ratios)+j] += error(f*factor)
    return errors/trials


if __name__ == "__main__":
    with threadpool_limits(limits=1):
        for g in (True,False):
            runs = [compare(d,n,budget,g,fixed,cond) for d,n,budget,fixed,cond in configs()]
            a = np.array([r[0] for r in runs])
            ratio = a/a[:,:1]
            print("MEASURE",g,"n configs",len(a))
            for i,m in enumerate(METHODS):
                print(m,np.round(np.median(ratio[:,i],axis=0),3),
                      "prediction wins",int((ratio[:,i,0]<1).sum()))
            print("maximum relative constraint residuals",np.max([r[1] for r in runs],axis=0))
        for fixed in (True,False):
            a = np.array([weighting(d,n,b,f,c) for d,n,b,f,c in configs() if f==fixed])
            q = a/a[:,:1]
            print("fixed",fixed,"median ratios",np.round(np.median(q,axis=0),3),
                  "wins",(q<1).sum(axis=0))
