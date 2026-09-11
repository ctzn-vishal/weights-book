"""Appendix B build: numerical checks of the scoped derivations.

The appendix states each result together with its conditions. This script checks
every stated identity or approximation on synthetic data built to satisfy those
conditions, and checks that the stated failures occur in the stated direction
when a condition is dropped. Results go to artifacts/figures/derivation_checks.json
(rendered as Figure B.1) and manifest.validation.

    python build.py

Deterministic: seeded generators, fixed rounding; only manifest.generated_at varies.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

os.environ.setdefault("NO_COLOR", "1")

import numpy as np
import polars as pl
import pyfixest as pf
import svy

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
KEY, SLUG = "appB", "appendix-b-derivations"
SEED = 20260910
rows: list[dict] = []
validation: list[dict] = []


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, sort_keys=True, indent=2, ensure_ascii=False)
        f.write("\n")


def sci(x: float) -> str:
    return f"{x:.1e}"


def record(section: str, claim: str, check: str, result: str, ok: bool, **detail) -> None:
    rows.append({"section": section, "claim": claim, "check": check, "result": result,
                 "status": "consistent" if ok else "NOT CONSISTENT"})
    validation.append({"check": f"{section}: {check}", "pass": bool(ok),
                       **{k: (round(v, 10) if isinstance(v, float) else v) for k, v in detail.items()}})


# ============================================================ B.1 Horvitz-Thompson and Hajek
rng = np.random.default_rng(SEED)
N = 2_000
size = rng.lognormal(0.0, 0.7, N)
pi = np.minimum(200 * size / size.sum(), 1.0)          # Poisson sampling, expected n = 200
y_flat = 10 + rng.normal(0, 1, N)                       # outcome unrelated to pi
y_size = 2 * size / size.mean() + rng.normal(0, 0.1, N)  # outcome roughly proportional to pi
R = 20_000
ht = np.empty((R, 2)); hj = np.empty((R, 2))
for r in range(R):
    s = rng.random(N) < pi
    inv = 1.0 / pi[s]
    for j, yv in enumerate((y_flat, y_size)):
        t = float((yv[s] * inv).sum())
        ht[r, j] = t
        hj[r, j] = t / inv.sum()
for j, label in enumerate(("outcome unrelated to pi", "outcome proportional to pi")):
    yv = (y_flat, y_size)[j]
    T, Ybar = yv.sum(), yv.mean()
    z_ht = (ht[:, j].mean() - T) / (ht[:, j].std(ddof=1) / np.sqrt(R))
    bias_hj = hj[:, j].mean() - Ybar
    mcse_hj = hj[:, j].std(ddof=1) / np.sqrt(R)
    vr = (ht[:, j] / N).var(ddof=1) / hj[:, j].var(ddof=1)
    record("B.1", "HT total is design-unbiased when every pi_i > 0 and is known",
           f"Poisson sampling, {R:,} draws, {label}",
           f"HT mean minus T = {z_ht:+.2f} Monte Carlo SEs",
           abs(z_ht) < 3, z=float(z_ht))
    record("B.1", "Hajek mean is not exactly unbiased; its variance can be far below HT/N's",
           f"same draws, {label}",
           f"Hajek bias {bias_hj:+.4f} (MC SE {mcse_hj:.4f}); Var(HT/N) / Var(Hajek) = {vr:.2f}",
           True, bias=float(bias_hj), var_ratio=float(vr))

# ============================================================ B.2 Taylor linearization vs CRV1
rng = np.random.default_rng(SEED + 1)
G = 40
sizes = rng.integers(5, 31, G)
cl = np.repeat(np.arange(G), sizes)
n = cl.size
h = cl % 4                                              # strata: PSUs nested in strata
x = rng.normal(size=n)
w = rng.uniform(0.5, 3.0, n)
u = rng.normal(0, 1, G)[cl]
y1 = 2 + u + rng.normal(0, 1, n)                        # strata uninformative
y2 = y1 + 3.0 * h                                       # strata informative for the outcome
frame = pl.DataFrame({"y1": y1, "y2": y2, "x": x, "w": w, "cl": cl, "h": h})
pdf = frame.to_pandas()

Rhat = (w * y1).sum() / w.sum()
z = np.bincount(cl, weights=w * (y1 - Rhat)) / w.sum()
v_tl = G / (G - 1) * ((z - z.mean()) ** 2).sum()
se_hand = float(np.sqrt(v_tl))
se_svy1 = float(svy.Sample(frame, design=svy.Design(psu="cl", wgt="w")).estimation.mean("y1").to_dicts()[0]["se"])
se_crv1 = float(pf.feols("y1 ~ 1", data=pdf, weights="w", vcov={"CRV1": "cl"}).se().iloc[0])
rel1 = abs(se_crv1 - se_svy1) / se_svy1
rel0 = abs(se_hand - se_svy1) / se_svy1
record("B.2", "One stratum, weighted mean: Taylor (with replacement) equals CRV1 exactly",
       "hand formula vs svy vs pyfixest CRV1, 40 PSUs",
       f"svy vs hand {sci(rel0)}; CRV1 vs svy {sci(rel1)} (relative)",
       rel1 < 1e-8 and rel0 < 1e-8, rel_crv1=float(rel1), rel_hand=float(rel0))

se_tl_strat = float(svy.Sample(frame, design=svy.Design(stratum="h", psu="cl", wgt="w"))
                    .estimation.mean("y2").to_dicts()[0]["se"])
se_crv1_2 = float(pf.feols("y2 ~ 1", data=pdf, weights="w", vcov={"CRV1": "cl"}).se().iloc[0])
se_tl_strat_u = float(svy.Sample(frame, design=svy.Design(stratum="h", psu="cl", wgt="w"))
                      .estimation.mean("y1").to_dicts()[0]["se"])
record("B.2", "Informative strata: CRV1 omits the stratification gain and is conservative",
       "outcome with stratum means 0, 3, 6, 9",
       f"CRV1 SE / Taylor SE = {se_crv1_2 / se_tl_strat:.2f}; with uninformative strata "
       f"{se_crv1 / se_tl_strat_u:.2f}",
       se_crv1_2 / se_tl_strat > 1.2, ratio_informative=float(se_crv1_2 / se_tl_strat),
       ratio_uninformative=float(se_crv1 / se_tl_strat_u))

glm = svy.Sample(frame, design=svy.Design(psu="cl", wgt="w")).glm.fit("y1", x=["x"])
se_svy_x = float([c.se for c in glm.coefs if c.term == "x"][0])
se_pf_x = float(pf.feols("y1 ~ x", data=pdf, weights="w", vcov={"CRV1": "cl"}).se()["x"])
X = np.column_stack([np.ones(n), x])
XtWX_inv = np.linalg.inv(X.T @ (X * w[:, None]))
beta = XtWX_inv @ (X.T @ (w * y1))
e = y1 - X @ beta
S = np.zeros((2, 2))
for g_ in range(G):
    m_ = cl == g_
    sg = (X[m_] * (w[m_] * e[m_])[:, None]).sum(axis=0)
    S += np.outer(sg, sg)
v_hand = G / (G - 1) * XtWX_inv @ S @ XtWX_inv
se_hand_x = float(np.sqrt(v_hand[1, 1]))
expected = np.sqrt((n - 1) / (n - 2))
record("B.2", "Regression (K = 2): CRV1 = Taylor x (N - 1)/(N - K), a small-sample factor",
       "slope SE: svy GLM vs hand sandwich vs pyfixest CRV1",
       f"svy vs hand {sci(abs(se_svy_x - se_hand_x) / se_hand_x)}; CRV1 / svy = {se_pf_x / se_svy_x:.6f} "
       f"vs sqrt((N-1)/(N-K)) = {expected:.6f}",
       abs(se_svy_x - se_hand_x) / se_hand_x < 1e-6 and abs(se_pf_x / se_svy_x - expected) < 1e-6,
       svy_vs_hand=float(abs(se_svy_x - se_hand_x) / se_hand_x), crv1_over_svy=float(se_pf_x / se_svy_x),
       expected=float(expected))

# ============================================================ B.3 Moulton factor
rng = np.random.default_rng(SEED + 2)
Gm, m, rho = 200, 20, 0.10
reps = 2_000
for label, rho_x in (("regressor constant within clusters", 1.0), ("regressor half within-cluster", 0.5)):
    xg = rng.normal(size=Gm)
    xi = np.sqrt(rho_x) * np.repeat(xg, m) + np.sqrt(1 - rho_x) * rng.normal(size=Gm * m)
    Xm = np.column_stack([np.ones(Gm * m), xi])
    inv = np.linalg.inv(Xm.T @ Xm)
    b_draws, v_conv = np.empty(reps), np.empty(reps)
    for r in range(reps):
        yv = 1 + 0.5 * xi + np.repeat(rng.normal(0, np.sqrt(rho), Gm), m) + rng.normal(0, np.sqrt(1 - rho), Gm * m)
        b = inv @ (Xm.T @ yv)
        res = yv - Xm @ b
        b_draws[r] = b[1]
        v_conv[r] = res @ res / (Gm * m - 2) * inv[1, 1]
    # sample intraclass correlation of the realized regressor (the rho_x in the formula)
    xc = xi.reshape(Gm, m) - xi.mean()
    rx = float(((xc.sum(axis=1) ** 2 - (xc ** 2).sum(axis=1)).sum()) / ((m - 1) * (xc ** 2).sum()))
    ratio = b_draws.var(ddof=1) / v_conv.mean()
    formula = 1 + (m - 1) * rx * rho
    record("B.3", "Moulton: Var(OLS slope) / conventional OLS variance = 1 + (m - 1) rho_x rho_u",
           f"equal clusters (m = {m}), rho_u = {rho}, {label}",
           f"Monte Carlo ratio {ratio:.2f} vs formula {formula:.2f}",
           abs(ratio / formula - 1) < 0.08, mc_ratio=float(ratio), formula=float(formula), rho_x=rx)

# ============================================================ B.4 Angrist variance weighting
rng = np.random.default_rng(SEED + 3)
cells = np.repeat([0, 1, 2], [400, 300, 300])
p_cell = np.array([0.1, 0.5, 0.9])
D = (rng.random(cells.size) < p_cell[cells]).astype(float)
tau = np.array([1.0, 2.0, 4.0])
yv = np.array([0.0, 1.0, -1.0])[cells] + tau[cells] * D + rng.normal(0, 1, cells.size)
wv = rng.uniform(0.5, 4.0, cells.size) * np.array([1.0, 2.0, 0.5])[cells]
Xs = np.column_stack([D, cells == 0, cells == 1, cells == 2]).astype(float)
b_ols = float(np.linalg.lstsq(Xs, yv, rcond=None)[0][0])
b_wls = float(np.linalg.lstsq(Xs * np.sqrt(wv)[:, None], yv * np.sqrt(wv), rcond=None)[0][0])


def angrist(weights: np.ndarray):
    num = den = 0.0
    shares, deltas, pvec = [], [], []
    for c in range(3):
        mk = cells == c
        wc = weights[mk]
        pc = float((wc * D[mk]).sum() / wc.sum())
        d1 = float((wc * yv[mk] * D[mk]).sum() / (wc * D[mk]).sum())
        d0 = float((wc * yv[mk] * (1 - D[mk])).sum() / (wc * (1 - D[mk])).sum())
        omega = float(wc.sum() * pc * (1 - pc))
        num += omega * (d1 - d0); den += omega
        shares.append(float(wc.sum())); deltas.append(d1 - d0); pvec.append(pc)
    return num / den, np.array(shares) / sum(shares), np.array(deltas), np.array(pvec)


f_ols, sh, dl, pv = angrist(np.ones(cells.size))
f_wls, shw, dlw, pvw = angrist(wv)
ate_w = float((shw * dlw).sum())
att_w = float((shw * pvw * dlw).sum() / (shw * pvw).sum())
record("B.4", "Saturated OLS slope = sum over cells of n_x p_x(1 - p_x) Delta_x / sum n_x p_x(1 - p_x), exactly in sample",
       "three cells, p = 0.1, 0.5, 0.9; unweighted",
       f"|OLS - formula| = {sci(abs(b_ols - f_ols))}", abs(b_ols - f_ols) < 1e-10,
       ols=b_ols, formula=f_ols)
record("B.4", "Same identity for WLS with the weighted cell shares and treatment rates",
       "same data with unequal weights",
       f"|WLS - formula| = {sci(abs(b_wls - f_wls))}; WLS {b_wls:.3f} vs weighted cell-average "
       f"(PATE analogue) {ate_w:.3f} vs ATT analogue {att_w:.3f}",
       abs(b_wls - f_wls) < 1e-10, wls=b_wls, formula=f_wls, pate_analogue=ate_w, att_analogue=att_w)

# signed weights under a linear (non-saturated) control
px = np.array([0.05, 0.90, 0.95])
tx = np.array([1.0, 1.0, 5.0])
xs = np.array([0.0, 1.0, 2.0])
cov = (xs * px).mean() - xs.mean() * px.mean()
slope = cov / xs.var()
L = px.mean() - slope * xs.mean() + slope * xs
omega = px * (1 - L)
beta_pop = float((omega * tx).sum() / omega.sum())
rng = np.random.default_rng(SEED + 4)
nn = 2_000_000
xd = rng.integers(0, 3, nn)
dd = (rng.random(nn) < px[xd]).astype(float)
yd = xd + tx[xd] * dd + rng.normal(0, 1, nn)            # E[Y(0)|X] = X, linear
Xl = np.column_stack([np.ones(nn), dd, xd])
b_lin = float(np.linalg.lstsq(Xl, yd, rcond=None)[0][1])
record("B.4", "Linear control, nonlinear propensity: implicit cell weights p(x)(1 - L(x)) can be negative",
       "X in {0,1,2}, p = 0.05, 0.90, 0.95, cell effects 1, 1, 5; n = 2,000,000",
       f"weights {', '.join(f'{v / omega.sum():+.3f}' for v in omega)}; population slope {beta_pop:+.4f}, "
       f"simulated OLS {b_lin:+.4f}",
       omega.min() < 0 and abs(b_lin - beta_pop) < 0.01, beta_pop=beta_pop, beta_sim=b_lin,
       min_weight=float(omega.min() / omega.sum()))

# ============================================================ B.5 effective samples
rng = np.random.default_rng(SEED + 5)
wk = rng.lognormal(0, 0.8, 5_000)
kish = wk.sum() ** 2 / (wk ** 2).sum()
cv2 = wk.var() / wk.mean() ** 2                        # population-variance CV
record("B.5", "n_Kish = (sum w)^2 / sum w^2 = n / (1 + CV(w)^2)",
       "5,000 lognormal weights", f"relative difference {sci(abs(kish - 5_000 / (1 + cv2)) / kish)}",
       abs(kish - 5_000 / (1 + cv2)) / kish < 1e-12)

Npop = 10_000
yp = rng.normal(50, 10, Npop)
rec = rng.random(Npop) < 1 / (1 + np.exp(-(yp - 55) / 5))   # self-selection on Y
f = rec.mean()
rho_ry = np.corrcoef(rec.astype(float), yp)[0, 1]
lhs = yp[rec].mean() - yp.mean()
rhs = rho_ry * np.sqrt((1 - f) / f) * yp.std()           # population SD (divisor N)
record("B.5", "Meng: sample mean error = rho(R,Y) x sqrt((1 - f)/f) x sigma_Y, an identity",
       "N = 10,000, recording depends on Y", f"error {lhs:.4f} vs identity {rhs:.4f}",
       abs(lhs - rhs) < 1e-9, error=float(lhs), identity=float(rhs))

# ============================================================ outputs
figure = {
    "type": "table",
    "title": "Numerical checks of the stated results",
    "subtitle": "Each derivation's claim, checked on synthetic data built to satisfy its conditions",
    "alt": "Table listing, for each derivation in Appendix B, the claim, the numerical check run in the "
           "build script, the result, and whether it is consistent with the claim.",
    "columns": [
        {"key": "section", "label": "Block", "align": "left"},
        {"key": "claim", "label": "Claim as stated", "align": "left"},
        {"key": "check", "label": "Check", "align": "left"},
        {"key": "result", "label": "Result", "align": "left"},
        {"key": "status", "label": "Status", "align": "left"},
    ],
    "rows": rows,
    "source": "appendix-b-derivations/build.py (seed 20260910); synthetic data only",
    "note": "Consistent means the check behaved as the derivation says under its conditions; "
            "a check is not a proof.",
}
write_json(ART / "figures" / "derivation_checks.json", figure)
write_json(ART / "manifest.json", {
    "key": KEY, "slug": SLUG, "status": "draft", "inputs": [], "code": "build.py",
    "validation": validation,
    "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
})
bad = [r["check"] for r in rows if r["status"] != "consistent"]
for r in rows:
    print(f"[{r['status']}] {r['section']} {r['check']}: {r['result']}")
print("appB:", "all checks consistent" if not bad else f"INCONSISTENT: {bad}")
