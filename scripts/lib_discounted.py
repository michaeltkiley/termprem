"""Discounted (geometrically weighted) least-squares VAR estimation.

Same structure as lib_var.py's estim_boot/window_tp_endpoint, but each
equation is fit by weighted least squares with weights decaying by
recency (weight(age) = rho^age) instead of plain OLS. This is the adopted
alternative to the rolling-window method in Kiley (2024), "Why Have
Long-Term Treasury Yields Fallen since the 1980s? Expected Short Rates and
Term Premiums in (Quasi-) Real Time," The Journal of Fixed Income, 34(2),
5-21 -- selected via out-of-sample forecast accuracy search (see
../research/) rather than the paper's hard 30-year window cutoff.

RHO is fixed at 1 - 1/360, i.e. the geometric decay whose total weight
mass (N_eff = 1/(1-rho)) matches a 30-year (360-month) window -- chosen
for direct comparability with a conventional 30-year rolling window,
while avoiding the discontinuities a hard cutoff introduces as
observations abruptly leave the window.
"""
import numpy as np

RHO = 1 - 1 / 360  # 30-year effective window (N_eff = 1/(1-RHO) = 360 months)


def geometric_weights(n: int, rho: float = RHO) -> np.ndarray:
    """weight(age) = rho^age, age=0 for the most recent (last) row."""
    age = np.arange(n - 1, -1, -1)
    return rho ** age


def wls_fit(X: np.ndarray, y: np.ndarray, w: np.ndarray) -> np.ndarray:
    sw = np.sqrt(w)
    beta, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)
    return beta


def estim_boot_weighted(Y: np.ndarray, vlag: int, weights: np.ndarray):
    """Same structure as lib_var.estim_boot, but each equation is fit by
    weighted least squares. weights has length Tbig = Y.shape[0]-vlag, in
    the same row order as the regression sample (oldest row first)."""
    Tbig0, Nbig = Y.shape
    Tbig = Tbig0 - vlag
    assert len(weights) == Tbig

    blocks = [Y[vlag - ii : Tbig0 - ii, :] for ii in range(vlag + 1)]
    Ydep = blocks[0]
    Xmat = np.hstack(blocks[1:])

    Bcompsm = np.vstack([wls_fit(Xmat, Ydep[:, i], weights) for i in range(Nbig)])

    bottom = np.hstack([np.eye(Nbig * (vlag - 1)), np.zeros((Nbig * (vlag - 1), Nbig))])
    Bcomp = np.vstack([Bcompsm, bottom])
    return Bcomp, Xmat


def window_tp_endpoint_weighted(X: np.ndarray, vlag: int, horizons, rho: float = RHO):
    """Same decomposition as lib_var.window_tp_endpoint, but the VAR is
    fit by geometrically discounted least squares (weight(age) = rho^age)
    instead of OLS. Demeaning uses the SAME discount weights as the
    regression -- both estimated with the same rho, anchored at the same
    "now" -- rather than the full, unweighted window mean. Using an
    unweighted mean as the reversion target while the dynamics are
    recency-weighted is an inconsistency: during a long, unusually
    persistent regime (e.g. the near-zero-rate 2009-2016 period) the
    weighted dynamics see almost no mean reversion in-sample and infer a
    near-unit-root process, while an unweighted target still points at the
    distant full-history average -- the combination projects the short
    rate reverting only very slowly toward a level the discounted data
    barely informs. Weighting the demeaning the same way keeps the
    reversion target consistent with the dynamics that are supposed to
    revert to it."""
    Y = np.empty((X.shape[0], 4))
    Y[:, 0] = X[:, 0]
    Y[:, 1] = X[:, [0, 1, 2, 4]].mean(axis=1)
    Y[:, 2] = X[:, 4] - X[:, 0]
    Y[:, 3] = X[:, 2] - 0.5 * (X[:, 0] + X[:, 4])

    full_weights = geometric_weights(Y.shape[0], rho)
    Ymean = (full_weights / full_weights.sum()) @ Y
    Yd = Y - Ymean

    Tbig = Yd.shape[0] - vlag
    weights = geometric_weights(Tbig, rho)
    Bcomp, Xmat = estim_boot_weighted(Yd, vlag, weights)
    x_last = Xmat[-1, :]

    Bpow = np.eye(Bcomp.shape[0])
    acc = X[-1, 0] - Ymean[0]
    for h in range(1, max(horizons) + 1):
        Bpow = Bcomp @ Bpow
        if h in horizons:
            acc += x_last @ Bpow[0, :]

    y10proj = acc / 10 + Ymean[0]
    y10tp = X[-1, 4] - y10proj
    return y10proj, y10tp, Ymean[0]
