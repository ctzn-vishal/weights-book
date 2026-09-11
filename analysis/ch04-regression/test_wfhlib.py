"""Unit tests for wfhlib (run: python test_wfhlib.py). build.py also calls run_all().

1. Sloczynski's published numerical example (IZA DP 11866, Table 1): OLS 0.92, ATE -0.2,
   ATT 1, ATC -0.25, OLS weight on ATT 93.6%, Angrist weight on tau_1 48%.
2. In-sample identities on random weighted data: moment engine = direct WLS; FWL cell
   representation; Sloczynski OLS = w1 ATT + w0 ATU; PATE = rho ATT + (1 - rho) ATU.
3. A large simulated population satisfying Sloczynski's Corollary 1 (saturated E[d|X],
   potential outcomes linear in p(X)): estimates recover the known ATT, ATU, w1.
4. Sandwich SEs (iid, HC1, CR1) against statsmodels; SparseFE against the within engine.
5. Chattopadhyay-Zubizarreta implied weights reproduce the OLS coefficient.
"""
from __future__ import annotations

import sys

import numpy as np
import statsmodels.api as sm

sys.path.insert(0, "C:/Users/Vishal Singh/Box/ipums/book/chapters/ch04-regression")
import wfhlib as W  # noqa: E402


def _close(a, b, tol, what):
    if not abs(a - b) <= tol:
        raise AssertionError(f"{what}: {a!r} vs {b!r} (tol {tol})")


def _moments(cell, D, Z, y, w, C):
    return W.CellMoments(cell, D, Z, y, C).sums(w)


def test_published_example() -> dict:
    # 1600 units reproduce the population proportions exactly.
    rows = []  # (d, x, count, y)
    rows += [(1, 1, 32, 3.0), (1, 0, 32, 4.0), (0, 1, 288, 0.0), (0, 0, 1248, 5.0)]
    d = np.concatenate([np.full(c, dd, float) for dd, _, c, _ in rows])
    x = np.concatenate([np.full(c, xx, np.int64) for _, xx, c, _ in rows])
    y = np.concatenate([np.full(c, yy, float) for _, _, c, yy in rows])
    Z = np.zeros((len(y), 3))
    w = np.ones(len(y))
    S = _moments(x, d, Z, y, w, 2)
    fit = W.fe_solve(S, use_z=False)
    sl = W.sloczynski_from_moments(S, use_z=False)
    est = W.estimands_from_cells(fit)
    _close(fit["beta"], 0.92, 1e-12, "OLS")
    _close(sl["implied"], 0.92, 1e-12, "w1*ATT + w0*ATU")
    _close(sl["att"], 1.0, 1e-12, "ATT")
    _close(sl["atu"], -0.25, 1e-12, "ATC")
    _close(sl["ape"], -0.2, 1e-12, "ATE")
    _close(round(100 * sl["w1"], 1), 93.6, 1e-9, "w_ATT (percent, 1 dp)")
    _close(round(100 * est["reg_share"][1], 1), 48.0, 1e-9, "Angrist weight on tau_1")
    _close(est["pate"], -0.2, 1e-12, "cell PATE")
    _close(est["att"], 1.0, 1e-12, "cell ATT")
    _close(est["atu"], -0.25, 1e-12, "cell ATU")
    return {"ols": fit["beta"], "w1": sl["w1"], "att": sl["att"], "atu": sl["atu"], "ate": sl["ape"],
            "angrist_w_tau1": float(est["reg_share"][1])}


def _random_data(n=4000, C=7, seed=11):
    rng = np.random.default_rng(seed)
    cell = rng.integers(0, C, n)
    Z = np.column_stack([rng.normal(size=n), rng.normal(size=n) ** 2, rng.integers(0, 2, n)])
    lin = -1.2 + 0.25 * cell + 0.4 * Z[:, 0] - 0.2 * Z[:, 2]
    D = (rng.uniform(size=n) < 1 / (1 + np.exp(-lin))).astype(float)
    y = 1.0 + 0.1 * cell + 0.3 * Z[:, 0] - 0.1 * Z[:, 1] + D * (0.2 + 0.05 * cell + 0.1 * Z[:, 0]) + rng.normal(size=n)
    w = rng.uniform(0.2, 5.0, n)
    return cell, Z, D, y, w, C


def test_identities() -> dict:
    cell, Z, D, y, w, C = _random_data()
    n = len(y)
    dummies = np.column_stack([(cell == c).astype(float) for c in range(C)])
    out = {}
    for label, wv in (("ols", np.ones(n)), ("wls", w)):
        S = _moments(cell, D, Z, y, wv, C)
        fit = W.fe_solve(S)
        X = np.column_stack([D, Z, dummies])
        b = np.linalg.lstsq(X * np.sqrt(wv)[:, None], y * np.sqrt(wv), rcond=None)[0]
        _close(fit["beta"], b[0], 1e-10, f"{label}: moment engine vs direct WLS")
        _close(fit["fwl"], fit["beta"], 1e-10, f"{label}: FWL cell representation")
        sl = W.sloczynski_from_moments(S)
        _close(sl["implied"], fit["beta"], 1e-10, f"{label}: Sloczynski identity")
        # direct Sloczynski: p(X) by WLS of D on (dummies, Z); group-wise WLS of y on (1, p)
        Xl = np.column_stack([dummies, Z])
        bl = np.linalg.lstsq(Xl * np.sqrt(wv)[:, None], D * np.sqrt(wv), rcond=None)[0]
        q = Xl @ bl
        coef = {}
        for dd in (0, 1):
            m = D == dd
            A = np.column_stack([np.ones(m.sum()), q[m]])
            coef[dd] = np.linalg.lstsq(A * np.sqrt(wv[m])[:, None], y[m] * np.sqrt(wv[m]), rcond=None)[0]
        q1 = np.average(q[D == 1], weights=wv[D == 1])
        q0 = np.average(q[D == 0], weights=wv[D == 0])
        att = np.average(y[D == 1], weights=wv[D == 1]) - (coef[0][0] + coef[0][1] * q1)
        atu = (coef[1][0] + coef[1][1] * q0) - np.average(y[D == 0], weights=wv[D == 0])
        _close(sl["att"], att, 1e-10, f"{label}: ATT_S direct")
        _close(sl["atu"], atu, 1e-10, f"{label}: ATU_S direct")
        rho = np.average(D, weights=wv)
        V1 = np.average((q[D == 1] - q1) ** 2, weights=wv[D == 1])
        V0 = np.average((q[D == 0] - q0) ** 2, weights=wv[D == 0])
        _close(sl["w1"], (1 - rho) * V0 / (rho * V1 + (1 - rho) * V0), 1e-10, f"{label}: w1 formula")
        est = W.estimands_from_cells(fit)
        _close(est["pate"], est["rho"] * est["att"] + (1 - est["rho"]) * est["atu"], 1e-12, f"{label}: PATE split")
        _close(est["proj"], fit["beta"], 1e-10, f"{label}: projection = implicit-weighted average")
        out[label] = {"beta": fit["beta"], "w1": sl["w1"]}
    return out


def test_population_recovery(n=2_000_000, seed=7) -> dict:
    """Corollary 1 holds by construction, so APLE = ATT/ATU and the weights are Sloczynski's."""
    rng = np.random.default_rng(seed)
    K = 12
    px = np.linspace(0.03, 0.45, K)  # E[d | x] for 12 cells: saturated, hence linear in the dummies
    share = rng.dirichlet(np.full(K, 3.0))
    x = rng.choice(K, size=n, p=share)
    p = px[x]
    d = (rng.uniform(size=n) < p).astype(float)
    a0, b0, a1, b1 = 1.0, 0.5, 1.1, 1.5  # y(j) linear in p(X)
    y0 = a0 + b0 * p + rng.normal(scale=0.5, size=n)
    y1 = a1 + b1 * p + rng.normal(scale=0.5, size=n)
    y = np.where(d == 1, y1, y0)
    # population truth
    Ep1 = float((share * px * px).sum() / (share * px).sum())
    Ep0 = float((share * (1 - px) * px).sum() / (share * (1 - px)).sum())
    att_true = (a1 - a0) + (b1 - b0) * Ep1
    atu_true = (a1 - a0) + (b1 - b0) * Ep0
    rho = float((share * px).sum())
    V1 = float((share * px * (px - Ep1) ** 2).sum() / (share * px).sum())
    V0 = float((share * (1 - px) * (px - Ep0) ** 2).sum() / (share * (1 - px)).sum())
    w1_true = (1 - rho) * V0 / (rho * V1 + (1 - rho) * V0)
    S = _moments(x, d, np.zeros((n, 3)), y, np.ones(n), K)
    sl = W.sloczynski_from_moments(S, use_z=False)
    _close(sl["att"], att_true, 0.02, "population ATT")
    _close(sl["atu"], atu_true, 0.01, "population ATU")
    _close(sl["w1"], w1_true, 0.01, "population w1")
    ols_true = w1_true * att_true + (1 - w1_true) * atu_true
    _close(W.fe_solve(S, use_z=False)["beta"], ols_true, 0.02, "population OLS plim")
    return {"att_true": att_true, "att_hat": sl["att"], "atu_true": atu_true, "atu_hat": sl["atu"],
            "w1_true": w1_true, "w1_hat": sl["w1"], "rho": rho}


def test_sandwich() -> dict:
    cell, Z, D, y, w, C = _random_data(n=3000, seed=5)
    rng = np.random.default_rng(3)
    clus = rng.integers(0, 150, len(y))
    dummies = np.column_stack([(cell == c).astype(float) for c in range(C)])
    X = np.column_stack([D, Z, dummies])
    res = {}
    for label, wv in (("ols", np.ones(len(y))), ("wls", w)):
        r = W.fe_ses(cell, C, D, Z, y, wv, {"g": clus})
        mod = sm.WLS(y, X, weights=wv)
        f_nr = mod.fit()
        f_hc = mod.fit(cov_type="HC1")
        f_cl = mod.fit(cov_type="cluster", cov_kwds={"groups": clus})
        _close(r["beta"], f_nr.params[0], 1e-10, f"{label} beta")
        _close(r["se"]["iid"], f_nr.bse[0], 1e-9, f"{label} iid SE")
        _close(r["se"]["hc1"], f_hc.bse[0], 1e-9, f"{label} HC1 SE")
        _close(r["se"]["cr_g"], f_cl.bse[0], 1e-9, f"{label} CR1 SE")
        sf = W.SparseFE(np.column_stack([np.ones(len(y)), D, Z]), [cell], d_col=1)
        s = sf.ses(y, wv, {"g": clus})
        _close(s["beta"], r["beta"], 1e-10, f"{label} SparseFE beta")
        _close(s["se"]["hc1"], r["se"]["hc1"], 1e-9, f"{label} SparseFE HC1")
        _close(s["se"]["cr_g"], r["se"]["cr_g"], 1e-9, f"{label} SparseFE CR1")
        res[label] = {"hc1": r["se"]["hc1"], "cr": r["se"]["cr_g"]}
    return res


def test_implied_weights() -> dict:
    cell, Z, D, y, w, C = _random_data(n=2500, seed=9)
    X = np.column_stack([np.ones(len(y)), Z[:, 0]])  # a deliberately coarse linear specification
    b = np.linalg.lstsq(X, D, rcond=None)[0]
    Dt = D - X @ b
    beta_direct = np.linalg.lstsq(np.column_stack([D, X]), y, rcond=None)[0][0]
    wT = np.where(D == 1, Dt, 0.0)
    wC = np.where(D == 0, -Dt, 0.0)
    _close(wT.sum(), wC.sum(), 1e-9, "treated and control implied weights have equal totals")
    beta_cz = (wT @ y - wC @ y) / wT.sum()
    _close(beta_cz, beta_direct, 1e-10, "implied-weight representation")
    return {"neg_control_weights": int((wC < 0).sum()), "neg_treated_weights": int((wT < 0).sum())}


def test_sdr() -> dict:
    rng = np.random.default_rng(1)
    reps = 0.5 + rng.normal(scale=0.01, size=80)
    _close(W.sdr_se(0.5, reps), float(np.sqrt(4 / 80 * np.sum((reps - 0.5) ** 2))), 1e-15, "SDR formula")
    _close(W.T_SDR, 1.99045021, 1e-8, "t(0.975, 79)")
    return {"ok": True}


def run_all() -> dict:
    return {
        "published_example": test_published_example(),
        "identities": test_identities(),
        "population_recovery": test_population_recovery(),
        "sandwich_vs_statsmodels": test_sandwich(),
        "implied_weights": test_implied_weights(),
        "sdr": test_sdr(),
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    r = run_all()
    for k, v in r.items():
        print(k, v)
    print("ALL TESTS PASSED")
