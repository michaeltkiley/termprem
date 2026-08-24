"""VAR estimation utilities, ported from estim_boot.m."""
import numpy as np


def estim_boot(Y: np.ndarray, vlag: int):
    """Reduced-form VAR(vlag) via equation-by-equation OLS, no constant/trend
    (iscon=0, istr=0), returned in companion form.

    Y: (Tbig0, Nbig) array.
    Returns Bcomp (Nbig*vlag, Nbig*vlag), Xmat (Tbig, Nbig*vlag).
    """
    Tbig0, Nbig = Y.shape
    Tbig = Tbig0 - vlag

    blocks = [Y[vlag - ii : Tbig0 - ii, :] for ii in range(vlag + 1)]
    Ydep = blocks[0]
    Xmat = np.hstack(blocks[1:])

    Bcompsm, *_ = np.linalg.lstsq(Xmat, Ydep, rcond=None)
    Bcompsm = Bcompsm.T  # (Nbig, Nbig*vlag)

    bottom = np.hstack([np.eye(Nbig * (vlag - 1)), np.zeros((Nbig * (vlag - 1), Nbig))])
    Bcomp = np.vstack([Bcompsm, bottom])

    return Bcomp, Xmat


def window_tp_endpoint(X: np.ndarray, vlag: int, horizons):
    """Estimate a VAR on the given window (X: window_len x 5 yields, cols
    1y/3y/5y/7y/10y) and return the term-premium decomposition (y10proj,
    y10tp) as of the *last* date in the window only (mirrors the
    tp(hhh)=...y10tp(end) pattern in var_tp_roll.m / var_tp_recursive.m)."""
    Y = np.empty((X.shape[0], 4))
    Y[:, 0] = X[:, 0]
    Y[:, 1] = X[:, [0, 1, 2, 4]].mean(axis=1)
    Y[:, 2] = X[:, 4] - X[:, 0]
    Y[:, 3] = X[:, 2] - 0.5 * (X[:, 0] + X[:, 4])
    Ymean = Y.mean(axis=0)
    Yd = Y - Ymean

    Bcomp, Xmat = estim_boot(Yd, vlag)
    x_last = Xmat[-1, :]

    Bpow = np.eye(Bcomp.shape[0])
    acc = Yd[-1, 0]
    for h in range(1, max(horizons) + 1):
        Bpow = Bcomp @ Bpow
        if h in horizons:
            acc += x_last @ Bpow[0, :]

    y10proj = acc / 10 + Ymean[0]
    y10tp = X[-1, 4] - y10proj
    return y10proj, y10tp, Ymean[0]


def horizon_forecast_row0(Bcomp: np.ndarray, Xmat: np.ndarray, horizons):
    """For each horizon h in `horizons`, compute Xmat @ (Bcomp^h)[0, :],
    i.e. the h-step-ahead forecast of the first VAR variable, iteratively
    (mirrors the MATLAB B_forw.B_h = Bcomp*B_forw.B_(h-1) loop)."""
    max_h = max(horizons)
    Bpow = np.eye(Bcomp.shape[0])
    out = {}
    for h in range(1, max_h + 1):
        Bpow = Bcomp @ Bpow
        if h in horizons:
            out[h] = Xmat @ Bpow[0, :]
    return out
