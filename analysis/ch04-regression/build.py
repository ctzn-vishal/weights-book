"""build.py -- Chapters 4 and 5 (keys ch4, ch5): one ACS 2024 work-from-home pipeline, two artifact sets.

    python build.py            full build: unit tests, estimates, 80 SDR replicates, artifacts, R check
    python build.py --no-r     skip the R sentinel run (manifest.validation then says so)

Reads (read-only): analysis/usa/acs/part_2020_2024.parquet (SAMPLE 202401),
analysis/usa/acs_repwt/part_2020_2024.parquet (REPWTP1-80, one read), analysis/usa/metadata/*.
Writes: ch04-regression/artifacts/**, ch05-hidden-weights/artifacts/**, and
ch04-regression/_scratch/analytic_ch45.parquet (microdata for verify.R; never exported).
Sample, variables, and estimators are documented in wfhlib.py and both NOTES.md files.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import subprocess
import sys
import time

import numpy as np
import polars as pl
import scipy.sparse as sp
from scipy import stats

HERE = "C:/Users/Vishal Singh/Box/ipums/book/chapters/ch04-regression"
CH5 = "C:/Users/Vishal Singh/Box/ipums/book/chapters/ch05-hidden-weights"
sys.path.insert(0, HERE)
import test_wfhlib  # noqa: E402
import wfhlib as W  # noqa: E402

SCRATCH = f"{HERE}/_scratch"
RSCRIPT = "C:/Program Files/R/R-4.6.1/bin/x64/Rscript.exe"
SOURCE = ("IPUMS USA, ACS 2024 1-year (SAMPLE 202401), analysis/usa/acs/part_2020_2024.parquet; "
          "replicate weights REPWTP1\u201380 from analysis/usa/acs_repwt/part_2020_2024.parquet")
POP = ("wage and salary workers aged 25\u201364 in the 2024 ACS who usually worked 30+ hours a week for 40+ weeks "
       "in the past 12 months, had positive wage income, and were at work in the reference week")
LOGW = "log hourly wage, log(INCWAGE / (UHRSWORK \u00d7 weeks-worked interval midpoint))"
WFH = "working from home (TRANWORK = 80, primary means of transportation to work: 'Worked at home')"
CTRL = "age, age\u00b2, sex, and four education levels (educ4)"
N_OG = len(W.OCC_GROUPS)
NOTE_OLS_CI = "OLS intervals use household-clustered (CR1) standard errors and the normal critical value."


# ----------------------------------------------------------------------------- artifact store
class Store:
    FIELDS = ("unit", "se", "ci_low", "ci_high", "ci_display", "df", "n", "weight", "variance", "benchmark", "note",
              "source")

    def __init__(self, key: str, slug: str):
        self.key, self.slug = key, slug
        self.facts: dict = {}
        self.ledgers: dict = {}
        self.figures: dict = {}

    def add(self, k, value, display, estimand, **kw):
        f = {"value": value, "display": display, "estimand": estimand, "source": SOURCE, "unit": None, "se": None,
             "ci_low": None, "ci_high": None, "ci_display": None, "df": None, "n": None, "weight": None,
             "variance": None, "benchmark": None, "note": ""}
        for kk in kw:
            if kk not in self.FIELDS:
                raise KeyError(kk)
        f.update(kw)
        if k in self.facts:
            raise KeyError(f"duplicate fact {k}")
        self.facts[k] = f

    def coef(self, k, est, se, *, sdr, estimand, n, weight, note="", unit="log points", d=3, kind="num"):
        t = W.T_SDR if sdr else W.Z975
        lo, hi = est - t * se, est + t * se
        disp = {"num": W.fnum(est, d), "pct": W.fpct(est, d), "usd": W.fusd(est, d)}[kind]
        self.add(k, est, disp, estimand, unit=unit, se=se, ci_low=lo, ci_high=hi, ci_display=W.fci(lo, hi, kind, d),
                 df=(W.DF_SDR if sdr else None), n=n, weight=weight,
                 variance=("replicate_sdr(80)" if sdr else "cluster_robust(household)"), note=note)

    def write(self, folder: str, manifest: dict) -> None:
        os.makedirs(f"{folder}/artifacts/figures", exist_ok=True)
        W.dump({"key": self.key, "facts": self.facts}, f"{folder}/artifacts/facts.json")
        W.dump({"key": self.key, "ledgers": self.ledgers}, f"{folder}/artifacts/ledger.json")
        for name, fig in self.figures.items():
            if "alt" not in fig or "type" not in fig:
                raise ValueError(f"figure {name} needs type and alt")
            W.dump(fig, f"{folder}/artifacts/figures/{name}.json")
        man = dict(manifest)
        man["generated_at"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
        with open(f"{folder}/artifacts/manifest.json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(W.clean(man), f, sort_keys=True, indent=2, ensure_ascii=False)
            f.write("\n")


# ----------------------------------------------------------------------------- cells (Chapter 5)
EDUC_NAMES = ["less than HS", "HS", "some college", "BA+"]


def educ_label(parts: list[int]) -> str:
    p = sorted(parts)
    if len(p) == 1:
        return EDUC_NAMES[p[0]]
    if p[0] == 0:
        return f"{EDUC_NAMES[p[-1]]} or less"
    if p[-1] == 3:
        return f"{EDUC_NAMES[p[0]]} or more"
    return " or ".join(EDUC_NAMES[k] for k in p)


def build_cells(og: np.ndarray, e4: np.ndarray, D: np.ndarray):
    """Occupation major group x educ4; within an occupation group, merge an education level into its
    neighbour (toward the middle; ties to the smaller neighbour) until every cell has n >= 100 and at
    least 30 WFH workers and 30 commuters. No record is dropped."""
    base = og * 4 + e4
    nb = np.bincount(base, minlength=N_OG * 4).astype(float)
    tb = np.bincount(base, weights=D, minlength=N_OG * 4)
    cells, merges = [], []
    for g in range(N_OG):
        parts = [[k] for k in range(4)]
        while len(parts) > 1:
            st = [(sum(nb[g * 4 + k] for k in p), sum(tb[g * 4 + k] for k in p)) for p in parts]
            bad = [i for i, (nn, tt) in enumerate(st) if nn < 100 or tt < 30 or nn - tt < 30]
            if not bad:
                break
            i = bad[0]
            if i == 0:
                j = 1
            elif i == len(parts) - 1:
                j = i - 1
            else:
                j = i - 1 if st[i - 1][0] <= st[i + 1][0] else i + 1
            a, b = sorted((i, j))
            merges.append({"occupation": W.OCC_GROUPS[g][2], "merged": educ_label(parts[a] + parts[b]),
                           "reason": f"cell '{educ_label(parts[i])}' had n = {int(st[i][0])}, "
                                     f"WFH = {int(st[i][1])}, commuters = {int(st[i][0] - st[i][1])}"})
            parts = parts[:a] + [parts[a] + parts[b]] + parts[b + 1:]
        for p in parts:
            cells.append((g, sorted(p)))
    cell_of_base = np.empty(N_OG * 4, dtype=np.int64)
    for ci, (g, p) in enumerate(cells):
        for k in p:
            cell_of_base[g * 4 + k] = ci
    labels = [f"{W.OCC_GROUPS[g][2]} \u00b7 {educ_label(p)}" for g, p in cells]
    return cell_of_base[base], cells, labels, merges


# ----------------------------------------------------------------------------- helpers
def ls(X, yy, ww=None):
    Xw = X if ww is None else X * ww[:, None]
    return np.linalg.solve(Xw.T @ X, Xw.T @ yy)


def ch4_scalars(Sl: np.ndarray, Sv: np.ndarray) -> dict:
    tl, tv = Sl.sum(0, keepdims=True), Sv.sum(0, keepdims=True)
    return {"prev": tl[0, 1, 0, 0] / tl[0, :, 0, 0].sum(), "pop": tl[0, :, 0, 0].sum(),
            "raw_log": W.fe_solve(tl, use_z=False)["beta"], "adj_log": W.fe_solve(Sl)["beta"],
            "raw_lev": W.fe_solve(tv, use_z=False)["beta"], "adj_lev": W.fe_solve(Sv)["beta"],
            "hw_c": tv[0, 0, 0, 5] / tv[0, 0, 0, 0], "hw_t": tv[0, 1, 0, 5] / tv[0, 1, 0, 0],
            "p_e4": Sl[:, 1, 0, 0] / Sl[:, :, 0, 0].sum(1)}


def dd_test(Xg: np.ndarray, yy: np.ndarray, hh: np.ndarray, k_base: int, d_col: int) -> dict:
    """DuMouchel-Duncan: OLS of y on X and w*X; Wald test that the k_base weight terms are zero."""
    n, k = Xg.shape
    A = Xg.T @ Xg
    b = np.linalg.solve(A, Xg.T @ yy)
    e = yy - Xg @ b
    Ainv = np.linalg.inv(A)
    U = Xg * e[:, None]
    V = n / (n - k) * Ainv @ (U.T @ U) @ Ainv
    Hs = sp.csr_matrix((np.ones(n), (hh, np.arange(n))))
    Ug = Hs @ U
    G = Ug.shape[0]
    Vc = G / (G - 1) * (n - 1) / (n - k) * Ainv @ (Ug.T @ Ug) @ Ainv
    idx = np.arange(k_base, 2 * k_base)
    F, p, q = W.wald_test(b[idx], V[np.ix_(idx, idx)], n - k)
    Fc, pc, _ = W.wald_test(b[idx], Vc[np.ix_(idx, idx)], G - 1)
    j = k_base + d_col
    tD, tDc = b[j] / math.sqrt(V[j, j]), b[j] / math.sqrt(Vc[j, j])
    return {"F_hc1": F, "p_hc1": p, "q": q, "df2_hc1": n - k, "F_cr": Fc, "p_cr": pc, "df2_cr": G - 1,
            "b_wD": float(b[j]), "t_wD_hc1": float(tD), "t_wD_cr": float(tDc),
            "p_wD_cr": float(2 * stats.norm.sf(abs(tDc)))}


# ----------------------------------------------------------------------------- main
def main(run_r: bool = True, reuse_r: bool = False) -> None:
    t0 = time.time()

    def log(*a):
        print(f"[{time.time() - t0:7.1f}s]", *a, flush=True)

    val4: list = []
    val5: list = []

    tests = test_wfhlib.run_all()
    log("unit tests passed")
    val5.append({"check": "unit tests (test_wfhlib.py): Sloczynski published numerical example (IZA DP 11866, "
                          "Table 1), in-sample identities, simulated-population recovery, sandwich SEs vs "
                          "statsmodels, implied-weight representation, SDR formula", "result": "pass",
                 "details": tests})

    # ------------------------------------------------------------------ data
    con = W.duck()
    flow = W.sample_flow(con)
    states = W.state_labels()
    df = W.load_sample(con)
    n = len(df)
    log("sample rows", n, flow)
    R = W.load_repwts(con, df)
    con.close()
    log("replicate weights", R.shape, "negative entries:", int((R < 0).sum()))

    y = df["lnw"].to_numpy()
    hw = df["hw"].to_numpy()
    D = df["D"].to_numpy()
    w = df["PERWT"].to_numpy().astype(float)
    Z = df.select("z1", "z2", "z3").to_numpy().astype(float)
    e4 = df["e4"].to_numpy().astype(np.int64)
    og = df["og"].to_numpy().astype(np.int64)
    st_levels, st = np.unique(df["STATEFIP"].to_numpy(), return_inverse=True)
    hh = np.unique(df["SERIAL"].to_numpy(), return_inverse=True)[1]
    occ = df["OCC"].to_numpy()
    ind = df["IND"].to_numpy()
    ones = np.ones(n)
    E = np.column_stack([(e4 == k).astype(float) for k in (1, 2, 3)])
    clusters = {"hh": hh, "state": st}
    n_hh = int(hh.max() + 1)

    # ------------------------------------------------------------------ audition reproduction (EDUC general)
    age = df["AGE"].to_numpy().astype(float)
    educ = df["EDUC"].to_numpy()
    lv = np.unique(educ)
    Xa = np.column_stack([ones, D, age, age ** 2, Z[:, 2]] + [(educ == v).astype(float) for v in lv[1:]])
    X0 = np.column_stack([ones, D])
    got = {"n": n, "prev_unweighted_pct": round(100 * D.mean(), 2),
           "prev_weighted_pct": round(100 * np.average(D, weights=w), 2),
           "raw_ols": round(ls(X0, y)[1], 4), "raw_wls": round(ls(X0, y, w)[1], 4),
           "adj_ols": round(ls(Xa, y)[1], 4), "adj_wls": round(ls(Xa, y, w)[1], 4)}
    expected = {"n": 984475, "prev_unweighted_pct": 14.03, "prev_weighted_pct": 13.66, "raw_ols": 0.3493,
                "raw_wls": 0.3454, "adj_ols": 0.2153, "adj_wls": 0.2096}
    match = all(got[k] == expected[k] for k in expected)
    val4.append({"check": "v4 audition reproduction (PLAN_v4 section 2; age, age^2, female, EDUC-general dummies)",
                 "expected": expected, "got": got, "result": "match" if match else "MISMATCH"})
    if not match:
        raise AssertionError(f"audition mismatch: {got}")
    log("audition reproduced", got)

    # ------------------------------------------------------------------ Chapter 4 models
    CM_log = W.CellMoments(e4, D, Z, y, 4)
    CM_lev = W.CellMoments(e4, D, Z, hw, 4)
    S4u = (CM_log.sums(ones), CM_lev.sums(ones))
    S4w = (CM_log.sums(w), CM_lev.sums(w))
    c4u, c4w = ch4_scalars(*S4u), ch4_scalars(*S4w)

    dense = np.column_stack([ones, D, Z, E])
    SF_st = W.SparseFE(dense, [st], d_col=1)
    SF_oi = W.SparseFE(dense, [occ, ind, st], d_col=1)
    rung = {}
    for name, SF in (("state", SF_st), ("occind", SF_oi)):
        for lab, wv in (("ols", ones), ("wls", w)):
            rung[(name, lab)] = SF.ses(y, wv, clusters)
    log("sparse rungs", {f"{k[0]}_{k[1]}": round(v["beta"], 5) for k, v in rung.items()},
        "k =", SF_oi.k, "FE levels", SF_oi.n_fe)

    zero_cell = np.zeros(n, dtype=np.int64)
    se_head = {lab: W.fe_ses(e4, 4, D, Z, y, wv, clusters) for lab, wv in (("ols", ones), ("wls", w))}
    se_raw = {lab: W.fe_ses(zero_cell, 1, D, None, y, wv, clusters) for lab, wv in (("ols", ones), ("wls", w))}
    se_lev = {lab: W.fe_ses(e4, 4, D, Z, hw, wv, clusters) for lab, wv in (("ols", ones), ("wls", w))}
    se_rawlev = {lab: W.fe_ses(zero_cell, 1, D, None, hw, wv, clusters) for lab, wv in (("ols", ones), ("wls", w))}
    for lab, cc in (("ols", c4u), ("wls", c4w)):
        for nm, blk, key in (("head", se_head, "adj_log"), ("raw", se_raw, "raw_log"), ("lev", se_lev, "adj_lev"),
                             ("rawlev", se_rawlev, "raw_lev")):
            if abs(blk[lab]["beta"] - cc[key]) > 1e-9 * max(1.0, abs(cc[key])):
                raise AssertionError(f"engine mismatch {nm} {lab}: {blk[lab]['beta']} vs {cc[key]}")
    val4.append({"check": "cell-moment engine vs within-transformed WLS (headline, raw, levels; OLS and WLS)",
                 "result": "agree to 1e-9"})

    # ------------------------------------------------------------------ Chapter 5 cells and models
    cell, cells, cell_labels, merges = build_cells(og, e4, D)
    C = len(cells)
    cell_og = np.array([g for g, _ in cells])
    CM_c = W.CellMoments(cell, D, Z, y, C)
    S5u, S5w = CM_c.sums(ones), CM_c.sums(w)
    fit5u, fit5w = W.fe_solve(S5u), W.fe_solve(S5w)
    est5u, est5w = W.estimands_from_cells(fit5u), W.estimands_from_cells(fit5w)
    sl5u, sl5w = W.sloczynski_from_moments(S5u), W.sloczynski_from_moments(S5w)
    sl4u, sl4w = W.sloczynski_from_moments(S4u[0]), W.sloczynski_from_moments(S4w[0])
    se5 = {lab: W.fe_ses(cell, C, D, Z, y, wv, clusters) for lab, wv in (("ols", ones), ("wls", w))}
    SF_c = W.SparseFE(np.column_stack([ones, D, Z]), [cell], d_col=1)
    b_sparse_c = SF_c.fit(y, w)[1]
    for nm, a, b in (("M5 WLS moment vs within", fit5w["beta"], se5["wls"]["beta"]),
                     ("M5 OLS moment vs within", fit5u["beta"], se5["ols"]["beta"]),
                     ("M5 WLS moment vs sparse dummies", fit5w["beta"], b_sparse_c),
                     ("M5 WLS FWL cell representation", fit5w["beta"], fit5w["fwl"]),
                     ("M5 WLS Sloczynski identity", fit5w["beta"], sl5w["implied"]),
                     ("M5 OLS Sloczynski identity", fit5u["beta"], sl5u["implied"]),
                     ("Ch4 WLS Sloczynski identity", c4w["adj_log"], sl4w["implied"]),
                     ("PATE = rho ATT + (1-rho) ATU", est5w["pate"],
                      est5w["rho"] * est5w["att"] + (1 - est5w["rho"]) * est5w["atu"])):
        if abs(a - b) > 1e-9:
            raise AssertionError(f"{nm}: {a} vs {b}")
    val5.append({"check": "exact identities on the real data (moment engine = within WLS = sparse dummies; FWL cell "
                          "representation; Sloczynski w1*ATT + w0*ATU = coefficient; PATE split)",
                 "result": "agree to 1e-9"})
    log("cells", C, "merges", len(merges), "M5 OLS/WLS", round(fit5u["beta"], 5), round(fit5w["beta"], 5))

    # ------------------------------------------------------------------ 80 SDR replicates
    reps: dict[str, np.ndarray] = {}

    def put(k, r, v):
        if k not in reps:
            reps[k] = np.empty(W.N_REPS)
        reps[k][r] = v

    tau_r = np.empty((W.N_REPS, C))
    p_r = np.empty((W.N_REPS, C))
    prevog_r = np.empty((W.N_REPS, N_OG))
    pe4_r = np.empty((W.N_REPS, 4))
    tau4_r = np.empty((W.N_REPS, 4))
    for r in range(W.N_REPS):
        wr = R[:, r]
        Sl, Sv = CM_log.sums(wr), CM_lev.sums(wr)
        c = ch4_scalars(Sl, Sv)
        for k in ("prev", "pop", "raw_log", "adj_log", "raw_lev", "adj_lev", "hw_c", "hw_t"):
            put(k, r, c[k])
        pe4_r[r] = c["p_e4"]
        tau4_r[r] = W.fe_solve(Sl)["tau"]
        put("state", r, SF_st.fit(y, wr)[1])
        put("occind", r, SF_oi.fit(y, wr)[1])
        f = wr / w
        put("adj_log_olsf", r, W.fe_solve(CM_log.sums(f))["beta"])
        Sc = CM_c.sums(wr)
        fr = W.fe_solve(Sc)
        er = W.estimands_from_cells(fr)
        sr = W.sloczynski_from_moments(Sc)
        s4 = W.sloczynski_from_moments(Sl)
        put("m5", r, fr["beta"])
        for k in ("pate", "att", "atu", "rho"):
            put(k, r, er[k])
        put("att_minus_atu", r, er["att"] - er["atu"])
        put("proj_minus_pate", r, er["proj"] - er["pate"])
        for k in ("w1", "att", "atu", "ape", "delta"):
            put(f"sl5_{k}", r, sr[k])
            put(f"sl4_{k}", r, s4[k])
        Scu = CM_c.sums(f)
        put("m5_olsf", r, W.fe_solve(Scu)["beta"])
        tau_r[r] = fr["tau"]
        p_r[r] = fr["p"]
        prevog_r[r] = (np.bincount(cell_og, weights=Sc[:, 1, 0, 0], minlength=N_OG)
                       / np.bincount(cell_og, weights=Sc[:, :, 0, 0].sum(1), minlength=N_OG))
        if r % 10 == 9:
            log(f"replicate {r + 1}/80")
    SE = {}

    def se_of(k, theta):
        SE[k] = W.sdr_se(theta, reps[k])
        return SE[k]

    full = {"prev": c4w["prev"], "pop": c4w["pop"], "raw_log": c4w["raw_log"], "adj_log": c4w["adj_log"],
            "raw_lev": c4w["raw_lev"], "adj_lev": c4w["adj_lev"], "hw_c": c4w["hw_c"], "hw_t": c4w["hw_t"],
            "state": rung[("state", "wls")]["beta"], "occind": rung[("occind", "wls")]["beta"],
            "adj_log_olsf": c4u["adj_log"], "m5": fit5w["beta"], "pate": est5w["pate"], "att": est5w["att"],
            "atu": est5w["atu"], "rho": est5w["rho"], "att_minus_atu": est5w["att"] - est5w["atu"],
            "proj_minus_pate": est5w["proj"] - est5w["pate"], "m5_olsf": fit5u["beta"]}
    for k in ("w1", "att", "atu", "ape", "delta"):
        full[f"sl5_{k}"] = sl5w[k]
        full[f"sl4_{k}"] = sl4w[k]
    for k, v in full.items():
        se_of(k, v)
    tau_se = W.sdr_se_vec(fit5w["tau"], tau_r)
    p_se = W.sdr_se_vec(fit5w["p"], p_r)
    prevog = (np.bincount(cell_og, weights=S5w[:, 1, 0, 0], minlength=N_OG)
              / np.bincount(cell_og, weights=S5w[:, :, 0, 0].sum(1), minlength=N_OG))
    prevog_se = W.sdr_se_vec(prevog, prevog_r)
    pe4_se = W.sdr_se_vec(c4w["p_e4"], pe4_r)
    fit4w = W.fe_solve(S4w[0])
    tau4_se = W.sdr_se_vec(fit4w["tau"], tau4_r)
    log("replicates done", {k: round(v, 5) for k, v in SE.items() if k in ("adj_log", "m5", "pate", "occind")})

    # ------------------------------------------------------------------ influence (leave one group out)
    gap_full = c4w["adj_log"] - c4u["adj_log"]
    infl = []
    NS = len(st_levels)
    CM_st = W.CellMoments(e4 * NS + st, D, Z, y, 4 * NS)
    Sst = {lab: CM_st.sums(wv).reshape(4, NS, 2, 6, 6) for lab, wv in (("ols", ones), ("wls", w))}
    del CM_st
    for j in range(NS):
        b = {lab: W.fe_solve(Sst[lab].sum(1) - Sst[lab][:, j])["beta"] for lab in ("ols", "wls")}
        infl.append({"dim": "State", "label": states[int(st_levels[j])], "gap": b["wls"] - b["ols"],
                     "share_w": Sst["wls"][:, j, :, 0, 0].sum() / c4w["pop"], "share_u": Sst["ols"][:, j, :, 0, 0].sum() / n})
    CM_og = W.CellMoments(e4 * N_OG + og, D, Z, y, 4 * N_OG)
    Sog = {lab: CM_og.sums(wv).reshape(4, N_OG, 2, 6, 6) for lab, wv in (("ols", ones), ("wls", w))}
    del CM_og
    for j in range(N_OG):
        b = {lab: W.fe_solve(Sog[lab].sum(1) - Sog[lab][:, j])["beta"] for lab in ("ols", "wls")}
        infl.append({"dim": "Occupation group", "label": W.OCC_GROUPS[j][2], "gap": b["wls"] - b["ols"],
                     "share_w": Sog["wls"][:, j, :, 0, 0].sum() / c4w["pop"], "share_u": Sog["ols"][:, j, :, 0, 0].sum() / n})
    for j in range(4):
        b = {lab: W.fe_solve(np.delete(S4u[0] if lab == "ols" else S4w[0], j, axis=0))["beta"] for lab in ("ols", "wls")}
        infl.append({"dim": "Education", "label": W.EDUC4_LEVELS[j], "gap": b["wls"] - b["ols"],
                     "share_w": S4w[0][j, :, 0, 0].sum() / c4w["pop"], "share_u": S4u[0][j, :, 0, 0].sum() / n})
    for d_ in infl:
        d_["change"] = d_["gap"] - gap_full
        d_["ratio"] = d_["share_w"] / d_["share_u"]

    # ------------------------------------------------------------------ DuMouchel-Duncan
    X8 = np.column_stack([ones, D, Z, E])
    wt = w / w.mean()
    Xg = np.column_stack([X8, X8 * wt[:, None]])
    dd_log = dd_test(Xg, y, hh, 8, 1)
    dd_lev = dd_test(Xg, hw, hh, 8, 1)
    del Xg
    log("DuMouchel-Duncan", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in dd_log.items()})

    # ------------------------------------------------------------------ Moulton bridge
    Xt = W.within(e4, np.column_stack([D, Z]), ones, 4)
    Dt = Xt[:, 0] - Xt[:, 1:] @ np.linalg.lstsq(Xt[:, 1:], Xt[:, 0], rcond=None)[0]  # D partialled out
    e_ols = se_head["ols"]["resid"]
    moul = {}
    for nm, codes in (("hh", hh), ("state", st)):
        rx, _ = W.icc_anova(Dt, codes)
        ru, _ = W.icc_anova(e_ols, codes)
        mf, kk = W.moulton_factor(rx, ru, codes)
        emp = (se_head["ols"]["se"][f"cr_{nm}"] / se_head["ols"]["se"]["iid"]) ** 2
        moul[nm] = {"rho_x": rx, "rho_u": ru, "size_term": kk, "factor": mf, "empirical": emp}
    log("Moulton", moul)

    # ------------------------------------------------------------------ topcoding, low wages
    inc = df["INCWAGE"].to_numpy()
    mx = np.zeros(NS)
    np.maximum.at(mx, st, inc)
    at_max = inc == mx[st]
    min_at_max = int(np.bincount(st, weights=at_max.astype(float)).min())
    top = {"share": float(at_max.mean()), "share_w": float(np.average(at_max, weights=w)),
           "share_wfh": float(at_max[D == 1].mean()), "share_comm": float(at_max[D == 0].mean()),
           "min_records_at_state_max": min_at_max, "state_max_lo": float(mx.min()), "state_max_hi": float(mx.max()),
           "n_hw_below_2": int((hw < 2).sum())}

    # ------------------------------------------------------------------ implied (signed) weights under linear specs
    Xl = np.column_stack([ones, Z, E])
    lin_head = {}
    for lab, wv in (("ols", ones), ("wls", w)):
        l = Xl @ ls(Xl, D, wv)
        lin_head[lab] = {"min": float(l.min()), "max": float(l.max()), "neg_controls": int(((D == 0) & (l < 0)).sum()),
                         "treated_above_1": int(((D == 1) & (l > 1)).sum())}
    SF_lpm = W.SparseFE(np.column_stack([ones, Z, E]), [occ, ind, st], d_col=0)
    signed = {}
    for lab, wv in (("ols", ones), ("wls", w)):
        l = SF_lpm.X @ SF_lpm.fit(D, wv)
        neg_c = (D == 0) & (l < 0)
        neg_t = (D == 1) & (l > 1)
        v = wv * (D - l)
        comm_w = np.bincount(og, weights=wv * (D == 0), minlength=N_OG)
        signed[lab] = {
            "min": float(l.min()), "max": float(l.max()),
            "n_neg_controls": int(neg_c.sum()), "n_treated_above_1": int(neg_t.sum()),
            "share_commuters_neg": float(wv[neg_c].sum() / wv[D == 0].sum()),
            "neg_mass_share": float(np.abs(v[neg_c | neg_t]).sum() / np.abs(v).sum()),
            "ctrl_neg_mass_share": float(np.abs(v[neg_c]).sum() / np.abs(v[D == 0]).sum()),
            "by_og_share_commuters_neg": np.bincount(og, weights=wv * neg_c, minlength=N_OG) / comm_w,
            "by_og_neg_mass": np.bincount(og, weights=np.abs(v) * (neg_c | neg_t), minlength=N_OG) / np.abs(v[neg_c | neg_t]).sum()}
    # cell-FE + linear z: fitted probabilities (observation-level representation) for NOTES
    S5 = S5w.sum(1)
    Szz = (S5[:, 2:5][:, :, 2:5] - np.einsum("ci,cj->cij", S5[:, 2:5, 0], S5[:, 0, 2:5]) / S5[:, 0, 0][:, None, None]).sum(0)
    SzD = (S5[:, 2:5, 1] - S5[:, 2:5, 0] * S5[:, 0, 1][:, None] / S5[:, 0, 0][:, None]).sum(0)
    bl = np.linalg.solve(Szz, SzD)
    a_c = (S5[:, 0, 1] - S5[:, 0, 2:5] @ bl) / S5[:, 0, 0]
    l5 = a_c[cell] + Z @ bl
    lin_m5 = {"min": float(l5.min()), "max": float(l5.max()), "neg_controls": int(((D == 0) & (l5 < 0)).sum()),
              "neg_controls_wshare": float(w[(D == 0) & (l5 < 0)].sum() / w[D == 0].sum())}
    log("signed weights", {k: {kk: vv for kk, vv in v.items() if not isinstance(vv, np.ndarray)} for k, v in signed.items()},
        "headline LPM", lin_head, "M5 LPM", lin_m5)

    # ------------------------------------------------------------------ pyfixest cross-check (independent package)
    pyfixest_check = None
    try:
        import pyfixest as pf
        pdf = df.select("lnw", "D", "z1", "z2", "z3", "educ4", "OCC", "IND", "STATEFIP", "SERIAL", "PERWT").to_pandas()
        m1 = pf.feols("lnw ~ D + z1 + z2 + z3 + C(educ4)", data=pdf, weights="PERWT", vcov={"CRV1": "SERIAL"})
        m2 = pf.feols("lnw ~ D + z1 + z2 + z3 + C(educ4) | OCC + IND + STATEFIP", data=pdf, weights="PERWT",
                      vcov="hetero")
        pyfixest_check = {"headline_wls_beta": float(m1.coef()["D"]), "headline_wls_crhh": float(m1.se()["D"]),
                          "occind_wls_beta": float(m2.coef()["D"]), "occind_wls_hc": float(m2.se()["D"]),
                          "ours_headline_wls_beta": c4w["adj_log"], "ours_headline_wls_crhh": se_head["wls"]["se"]["cr_hh"],
                          "ours_occind_wls_beta": rung[("occind", "wls")]["beta"],
                          "ours_occind_wls_hc1": rung[("occind", "wls")]["se"]["hc1"]}
        del pdf
        ok = (abs(pyfixest_check["headline_wls_beta"] - c4w["adj_log"]) < 1e-8
              and abs(pyfixest_check["occind_wls_beta"] - rung[("occind", "wls")]["beta"]) < 1e-6)
        val4.append({"check": "pyfixest 0.60 cross-check (headline WLS, CR1 by household; occupation+industry+state "
                              "WLS, heteroskedasticity-robust)", "result": "agree" if ok else "DISAGREE",
                     "details": pyfixest_check})
        log("pyfixest", pyfixest_check)
    except Exception as exc:  # pragma: no cover - recorded, not fatal
        val4.append({"check": "pyfixest cross-check", "result": f"not run: {type(exc).__name__}: {exc}"})

    # ------------------------------------------------------------------ analytic file for verify.R
    out = df.select("SERIAL", "PERWT", "STATEFIP", "OCC", "IND", "lnw", "hw", "D", "z1", "z2", "z3", "educ4").with_columns(
        cell=pl.Series(cell))
    rep_df = pl.DataFrame(R, schema=[f"REPWTP{i}" for i in range(1, W.N_REPS + 1)], orient="row")
    out.hstack(rep_df.get_columns()).write_parquet(f"{SCRATCH}/analytic_ch45.parquet", compression="zstd")
    del rep_df, out
    log("wrote analytic_ch45.parquet for verify.R")

    r_result = {"result": "not run (--no-r)"}
    rj = f"{SCRATCH}/r_check.json"
    if reuse_r and os.path.exists(rj):
        run_r = False
        rc_ok = True
        log("reusing existing r_check.json (verify.R already run on this analytic file)")
    else:
        rc_ok = False
    if run_r and os.path.exists(RSCRIPT):
        if os.path.exists(rj):
            os.remove(rj)
        pr = subprocess.run([RSCRIPT, f"{HERE}/verify.R"], capture_output=True, text=True, timeout=7200)
        log("verify.R exit", pr.returncode)
        rc_ok = pr.returncode == 0 and os.path.exists(rj)
        if not rc_ok:
            r_result = {"result": f"verify.R failed (exit {pr.returncode})", "stderr_tail": pr.stderr[-1500:]}
    if rc_ok:
        with open(rj, encoding="utf-8") as fh:
            rc = json.load(fh)
            ours = {"svymean_D": (c4w["prev"], SE["prev"]), "svyglm_raw_log": (c4w["raw_log"], SE["raw_log"]),
                    "svyglm_headline_log": (c4w["adj_log"], SE["adj_log"]),
                    "svyglm_headline_levels": (c4w["adj_lev"], SE["adj_lev"]),
                    "svyglm_cellfe_log": (fit5w["beta"], SE["m5"]),
                    "wr_headline_log": (c4w["adj_log"], SE["adj_log"]),
                    "wr_cellfe_log": (fit5w["beta"], SE["m5"]),
                    "fixest_headline_wls_crhh": (c4w["adj_log"], se_head["wls"]["se"]["cr_hh"]),
                    "fixest_headline_ols_crhh": (c4u["adj_log"], se_head["ols"]["se"]["cr_hh"]),
                    "fixest_occind_wls_hetero": (rung[("occind", "wls")]["beta"], rung[("occind", "wls")]["se"]["hc1"]),
                    "fixest_occind_ols_hetero": (rung[("occind", "ols")]["beta"], rung[("occind", "ols")]["se"]["hc1"])}
            rows = []
            for chk in rc["checks"]:
                o = ours.get(chk["check"])
                if o is None:
                    continue
                rows.append({"check": chk["check"], "r_estimate": chk["estimate"], "py_estimate": o[0],
                             "abs_diff_estimate": abs(chk["estimate"] - o[0]), "r_se": chk["se"], "py_se": o[1],
                             "rel_diff_se": abs(chk["se"] - o[1]) / o[1], "method": chk.get("method", "")})
            r_result = {"result": "run", "r_version": rc["r_version"], "survey": rc["survey"], "fixest": rc["fixest"],
                        "rows": rows}
    val4.append({"check": "R sentinel (verify.R): survey 4.5 svrepdesign(type='successive-difference', mse=TRUE) "
                          "and fixest", **r_result})
    val5.append({"check": "R sentinel for the cell-fixed-effect projection (survey::withReplicates, within-cell WLS on all "
                          "80 SDR replicates) and the weighted WFH share (svymean); full R table in the ch4 manifest",
                 "result": r_result.get("result"),
                 "rows": [r_ for r_ in r_result.get("rows", []) if r_["check"] in ("wr_cellfe_log", "svymean_D")]})

    # ================================================================== Chapter 4 artifacts
    s4 = Store("ch4", "ch04-regression")
    P = f"Population: {POP}."
    wls_w, ols_w = "PERWT", "none (equal case weights)"
    s4.add("n_sample", n, W.fint(n), f"Unweighted count of analytic-sample records. {P}", unit="records", n=n,
           weight=ols_w, variance="none")
    s4.add("n_households", n_hh, W.fint(n_hh), "Unweighted count of distinct households (SERIAL) in the analytic sample",
           unit="households", n=n, weight=ols_w, variance="none")
    s4.add("n_wfh", int(D.sum()), W.fint(D.sum()), "Unweighted count of analytic-sample records coded as working from home",
           unit="records", n=n, weight=ols_w, variance="none")
    s4.add("pop_millions", c4w["pop"] / 1e6, W.fnum(c4w["pop"] / 1e6, 1), f"PERWT-weighted size of the target population, millions. {P}",
           unit="million people", se=SE["pop"] / 1e6, n=n, weight=wls_w, variance="replicate_sdr(80)", df=W.DF_SDR)
    s4.add("prev_unw", D.mean(), W.fpct(D.mean(), 1), f"Unweighted share of records {WFH}. {P}", n=n, weight=ols_w,
           variance="none")
    lo, hi = c4w["prev"] - W.T_SDR * SE["prev"], c4w["prev"] + W.T_SDR * SE["prev"]
    s4.add("prev_w", c4w["prev"], W.fpct(c4w["prev"], 1), f"PERWT-weighted share {WFH}. {P}", se=SE["prev"], ci_low=lo,
           ci_high=hi, ci_display=W.fci(lo, hi, "pct", 1), df=W.DF_SDR, n=n, weight=wls_w, variance="replicate_sdr(80)")
    s4.add("prev_ba", c4w["p_e4"][3], W.fpct(c4w["p_e4"][3], 1), f"PERWT-weighted WFH share among BA+ workers. {P}",
           se=pe4_se[3], n=int((e4 == 3).sum()), weight=wls_w, variance="replicate_sdr(80)", df=W.DF_SDR)
    s4.add("prev_lths", c4w["p_e4"][0], W.fpct(c4w["p_e4"][0], 1), f"PERWT-weighted WFH share among workers with less than a high school diploma. {P}",
           se=pe4_se[0], n=int((e4 == 0).sum()), weight=wls_w, variance="replicate_sdr(80)", df=W.DF_SDR)

    est_raw = f"Difference in mean {LOGW} between WFH workers and commuters. {P}"
    est_adj = f"Coefficient on WFH in a linear regression of {LOGW} on WFH, {CTRL}; a descriptive adjusted contrast. {P}"
    s4.coef("raw_ols", c4u["raw_log"], se_raw["ols"]["se"]["cr_hh"], sdr=False, estimand=est_raw + " Unweighted.", n=n,
            weight=ols_w, note=NOTE_OLS_CI)
    s4.coef("raw_wls", c4w["raw_log"], SE["raw_log"], sdr=True, estimand=est_raw + " PERWT-weighted.", n=n, weight=wls_w)
    s4.coef("adj_ols", c4u["adj_log"], se_head["ols"]["se"]["cr_hh"], sdr=False, estimand=est_adj + " Unweighted (OLS).",
            n=n, weight=ols_w, note=NOTE_OLS_CI)
    s4.coef("adj_wls", c4w["adj_log"], SE["adj_log"], sdr=True, estimand=est_adj + " PERWT-weighted (WLS): the population linear projection.",
            n=n, weight=wls_w)
    for k, b in (("raw_wls_pct", c4w["raw_log"]), ("adj_wls_pct", c4w["adj_log"])):
        s4.add(k, math.exp(b) - 1, W.fpct(math.exp(b) - 1, 0), "exp(coefficient) - 1: the proportional hourly-wage "
               f"difference implied by the log-point coefficient ({k.split('_')[0]}, {k.split('_')[1]})", n=n, variance="none")
    s4.add("adj_gap_abs", abs(gap_full), W.fnum(abs(gap_full), 3), "Absolute WLS-OLS difference in the adjusted coefficient",
           unit="log points", n=n, variance="none")
    s4.add("gap_rel_se", abs(gap_full) / SE["adj_log"], W.fnum(abs(gap_full) / SE["adj_log"], 1),
           "|WLS - OLS| divided by the SDR standard error of the WLS coefficient", unit="standard errors", variance="none")
    s4.coef("state_ols", rung[("state", "ols")]["beta"], rung[("state", "ols")]["se"]["cr_hh"], sdr=False,
            estimand=f"As adj_ols, adding state fixed effects. {P}", n=n, weight=ols_w, note=NOTE_OLS_CI)
    s4.coef("state_wls", rung[("state", "wls")]["beta"], SE["state"], sdr=True,
            estimand=f"As adj_wls, adding state fixed effects. {P}", n=n, weight=wls_w)
    s4.coef("occind_ols", rung[("occind", "ols")]["beta"], rung[("occind", "ols")]["se"]["cr_hh"], sdr=False,
            estimand=f"As adj_ols, adding fixed effects for {SF_oi.n_fe[0]} detailed occupations, {SF_oi.n_fe[1]} industries, "
                     f"and {SF_oi.n_fe[2]} states. {P}", n=n, weight=ols_w, note=NOTE_OLS_CI)
    s4.coef("occind_wls", rung[("occind", "wls")]["beta"], SE["occind"], sdr=True,
            estimand=f"As adj_wls, adding fixed effects for {SF_oi.n_fe[0]} detailed occupations, {SF_oi.n_fe[1]} industries, "
                     f"and {SF_oi.n_fe[2]} states (population linear projection). {P}", n=n, weight=wls_w)
    s4.add("occind_wls_pct", math.exp(full["occind"]) - 1, W.fpct(math.exp(full["occind"]) - 1, 0),
           "exp(occupation-industry-state adjusted WLS coefficient) - 1", n=n, variance="none")
    shrink = 1 - full["occind"] / c4w["adj_log"]
    s4.add("occind_shrink", shrink, W.fpct(shrink, 0), "Share of the demographically adjusted WLS coefficient that "
           "disappears when occupation, industry, and state fixed effects are added", n=n, variance="none")
    s4.add("n_occ_codes", SF_oi.n_fe[0], W.fint(SF_oi.n_fe[0]), "Distinct 2018 Census occupation codes (OCC) in the sample",
           unit="codes", variance="none")
    s4.add("n_ind_codes", SF_oi.n_fe[1], W.fint(SF_oi.n_fe[1]), "Distinct Census industry codes (IND) in the sample",
           unit="codes", variance="none")
    # levels
    est_lev = f"Coefficient on WFH in a linear regression of hourly wage in dollars (levels) on WFH, {CTRL}. {P}"
    s4.coef("adj_lev_ols", c4u["adj_lev"], se_lev["ols"]["se"]["cr_hh"], sdr=False, estimand=est_lev + " Unweighted.", n=n,
            weight=ols_w, unit="dollars per hour", d=2, kind="usd", note=NOTE_OLS_CI)
    s4.coef("adj_lev_wls", c4w["adj_lev"], SE["adj_lev"], sdr=True, estimand=est_lev + " PERWT-weighted.", n=n, weight=wls_w,
            unit="dollars per hour", d=2, kind="usd")
    s4.coef("hw_comm", c4w["hw_c"], SE["hw_c"], sdr=True, estimand=f"PERWT-weighted mean hourly wage of commuters (dollars). {P}",
            n=int((D == 0).sum()), weight=wls_w, unit="dollars per hour", d=2, kind="usd")
    rel_w, rel_u = c4w["adj_lev"] / c4w["hw_c"], c4u["adj_lev"] / c4u["hw_c"]
    s4.add("adj_lev_wls_rel", rel_w, W.fpct(rel_w, 0), "WLS levels coefficient divided by commuters' weighted mean hourly wage",
           n=n, variance="none")
    lev_gap_rel = (c4w["adj_lev"] - c4u["adj_lev"]) / c4u["adj_lev"]
    log_gap_rel = gap_full / c4u["adj_log"]
    s4.add("lev_gap_rel", lev_gap_rel, W.fpct(abs(lev_gap_rel), 1), "|WLS - OLS| as a share of the OLS coefficient, levels",
           variance="none")
    s4.add("log_gap_rel", log_gap_rel, W.fpct(abs(log_gap_rel), 1), "|WLS - OLS| as a share of the OLS coefficient, logs",
           variance="none")
    # DuMouchel-Duncan
    s4.add("dd_q", dd_log["q"], str(dd_log["q"]), "Number of weight terms tested (the weight and its interactions with the "
           "intercept-adjusted regressors: WFH, age, age^2, female, three education dummies)", variance="none")
    s4.add("dd_f", dd_log["F_cr"], W.fnum(dd_log["F_cr"], 1), "DuMouchel-Duncan joint F statistic for the weight terms "
           "(log-wage headline model), household-clustered Wald test", n=n, variance="cluster_robust(household)",
           note=f"F({dd_log['q']}, {dd_log['df2_cr']:,}); heteroskedasticity-robust version F = {dd_log['F_hc1']:.1f}")
    s4.add("dd_p", dd_log["p_cr"], W.fp(dd_log["p_cr"]), "p-value of the DuMouchel-Duncan joint test (household-clustered)",
           n=n, variance="cluster_robust(household)")
    s4.add("dd_t_wd", dd_log["t_wD_cr"], W.fnum(dd_log["t_wD_cr"], 1), "t statistic on weight x WFH in the DuMouchel-Duncan "
           "regression (household-clustered)", n=n, variance="cluster_robust(household)")
    s4.add("dd_lev_f", dd_lev["F_cr"], W.fnum(dd_lev["F_cr"], 1), "DuMouchel-Duncan joint F statistic, levels model "
           "(household-clustered)", n=n, variance="cluster_robust(household)")
    # standard errors
    for lab in ("wls",):
        sse = se_head[lab]["se"]
        for m in ("iid", "hc1", "cr_hh", "cr_state"):
            s4.add(f"se_{lab}_{m.replace('cr_', 'cr')}", sse[m], W.fnum(sse[m], 4),
                   f"Standard error of the {lab.upper()} headline coefficient, {m}", unit="log points", n=n,
                   variance={"iid": "none", "hc1": "none", "cr_hh": "cluster_robust(household)",
                             "cr_state": "cluster_robust(state)"}[m])
    s4.add("se_wls_sdr", SE["adj_log"], W.fnum(SE["adj_log"], 4), "SDR replicate standard error of the WLS headline coefficient",
           unit="log points", n=n, df=W.DF_SDR, variance="replicate_sdr(80)")
    s4.add("se_ratio_state_sdr", se_head["wls"]["se"]["cr_state"] / SE["adj_log"],
           W.fnum(se_head["wls"]["se"]["cr_state"] / SE["adj_log"], 1), "State-clustered SE divided by the SDR SE (WLS)",
           unit="ratio", variance="none")
    s4.add("se_ratio_sdr_hh", SE["adj_log"] / se_head["wls"]["se"]["cr_hh"], W.fnum(SE["adj_log"] / se_head["wls"]["se"]["cr_hh"], 2),
           "SDR SE divided by the household-clustered SE (WLS)", unit="ratio", variance="none")
    s4.add("weighting_var_ratio", (se_head["wls"]["se"]["hc1"] / se_head["ols"]["se"]["hc1"]) ** 2,
           W.fnum((se_head["wls"]["se"]["hc1"] / se_head["ols"]["se"]["hc1"]) ** 2, 2),
           "Variance of WLS divided by variance of OLS, both heteroskedasticity-robust (HC1): the precision cost of weighting",
           unit="ratio", variance="none")
    cvw = float(np.std(w) / np.mean(w))
    s4.add("cv_w", cvw, W.fnum(cvw, 2), "Coefficient of variation of PERWT in the analytic sample", variance="none", n=n)
    s4.add("kish_ratio", 1 / (1 + cvw ** 2), W.fpct(1 / (1 + cvw ** 2), 0), "Kish effective sample size as a share of n, "
           "1/(1 + CV(w)^2)", variance="none", n=n)
    dvr = (SE["adj_log"] / SE["adj_log_olsf"]) ** 2
    s4.add("design_var_ratio", dvr, W.fnum(dvr, 2), "SDR variance of the WLS headline coefficient divided by the SDR-factor "
           "variance of the OLS coefficient", unit="ratio", variance="none")
    s4.add("n_states", NS, str(NS), "States plus DC in the sample (state clusters)", unit="clusters", variance="none")
    for nm in ("hh", "state"):
        mo = moul[nm]
        s4.add(f"moulton_{nm}", mo["factor"], W.fnum(mo["factor"], 2), f"Moulton factor 1 + [V(m)/m + m - 1] rho_x rho_u for "
               f"{'household' if nm == 'hh' else 'state'} clusters (headline OLS)", unit="variance ratio", variance="none",
               note=f"rho_x = {mo['rho_x']:.4f} (WFH partialled on controls), rho_u = {mo['rho_u']:.4f}, size term = {mo['size_term']:.2f}")
        s4.add(f"moulton_{nm}_emp", mo["empirical"], W.fnum(mo["empirical"], 2), f"Cluster-robust ({nm}) variance divided "
               "by iid variance, headline OLS", unit="variance ratio", variance="none")
    s4.add("topcode_share", top["share"], W.fpct(top["share"], 1), "Share of analytic-sample records whose INCWAGE equals "
           "their state's maximum (the IPUMS/Census state top-code replacement value)", n=n, variance="none",
           note=f"Every state has at least {top['min_records_at_state_max']} records at its maximum; WFH {top['share_wfh']:.3%}, commuters {top['share_comm']:.3%}")
    # influence facts
    sel = {}
    for dim in ("State", "Occupation group", "Education"):
        rows_ = sorted([d_ for d_ in infl if d_["dim"] == dim], key=lambda d_: -abs(d_["change"]))
        sel[dim] = rows_
    top_state, top_occ = sel["State"][0], sel["Occupation group"][0]
    s4.add("infl_state", top_state["label"], top_state["label"], "State whose removal moves the WLS-OLS gap the most",
           variance="none")
    s4.add("infl_state_gap", top_state["gap"], W.fnum(top_state["gap"], 3), f"WLS - OLS headline gap without {top_state['label']}",
           unit="log points", variance="none")
    s4.add("infl_occ", top_occ["label"], top_occ["label"], "Occupation group whose removal moves the WLS-OLS gap the most",
           variance="none")
    s4.add("infl_occ_gap", top_occ["gap"], W.fnum(top_occ["gap"], 3), f"WLS - OLS headline gap without {top_occ['label']}",
           unit="log points", variance="none")
    edu_top = sel["Education"][0]
    s4.add("infl_educ", edu_top["label"], edu_top["label"], "Education level whose removal moves the WLS-OLS gap the most",
           variance="none")
    s4.add("infl_educ_gap", edu_top["gap"], W.fnum(edu_top["gap"], 3), f"WLS - OLS headline gap without {edu_top['label']}",
           unit="log points", variance="none")
    max_abs_change = max(abs(d_["change"]) for d_ in infl)
    s4.add("infl_max_change", max_abs_change, W.fnum(max_abs_change, 3), "Largest absolute change in the WLS-OLS gap from "
           "dropping any single state, occupation group, or education level", unit="log points", variance="none")

    # ---- Chapter 4 figures
    def ci_rows(label, group, b, se, sdr, role):
        t = W.T_SDR if sdr else W.Z975
        return {"label": label, "group": group, "estimate": b, "ci_low": b - t * se, "ci_high": b + t * se, "role": role,
                "n": n}

    ladder = []
    for grp, bo, so, bw, sw in (
            ("Raw difference", c4u["raw_log"], se_raw["ols"]["se"]["cr_hh"], c4w["raw_log"], SE["raw_log"]),
            ("+ age, sex, education", c4u["adj_log"], se_head["ols"]["se"]["cr_hh"], c4w["adj_log"], SE["adj_log"]),
            ("+ state", rung[("state", "ols")]["beta"], rung[("state", "ols")]["se"]["cr_hh"], full["state"], SE["state"]),
            ("+ occupation and industry", rung[("occind", "ols")]["beta"], rung[("occind", "ols")]["se"]["cr_hh"],
             full["occind"], SE["occind"])):
        ladder.append(ci_rows("Unweighted (OLS)", grp, bo, so, False, "unweighted"))
        ladder.append(ci_rows("Weighted (WLS, PERWT)", grp, bw, sw, True, "weighted"))
    s4.figures["ladder"] = {
        "type": "dot", "format": "num3",
        "title": "The WFH wage gap shrinks with each control; weighting barely moves it",
        "subtitle": "Coefficient on working from home, log hourly wage, 2024 ACS full-time wage and salary workers aged 25\u201364",
        "alt": "Dot plot of the work-from-home coefficient in four specifications. Weighted and unweighted estimates nearly "
               "coincide in every row, while adding controls moves the estimate from about 0.35 to about 0.08 log points.",
        "x_label": "Adjusted WFH \u2212 commuter difference in log hourly wage (log points)",
        "reference": {"value": 0, "label": "no difference"}, "rows": ladder, "source": SOURCE,
        "note": ("Weighted intervals: 80-replicate SDR, t with 79 df. " + NOTE_OLS_CI +
                 " '+ occupation and industry' adds fixed effects for detailed occupation, industry, and state.")}
    ll_rows = []
    for spec, lab, bl_, blev, hwc in (("Raw difference", "Unweighted (OLS)", c4u["raw_log"], c4u["raw_lev"], c4u["hw_c"]),
                                      ("Raw difference", "Weighted (WLS)", c4w["raw_log"], c4w["raw_lev"], c4w["hw_c"]),
                                      ("+ age, sex, education", "Unweighted (OLS)", c4u["adj_log"], c4u["adj_lev"], c4u["hw_c"]),
                                      ("+ age, sex, education", "Weighted (WLS)", c4w["adj_log"], c4w["adj_lev"], c4w["hw_c"])):
        ll_rows.append({"spec": spec, "est": lab, "log": bl_, "log_pct": math.exp(bl_) - 1, "lev": W.fusd(blev, 2),
                        "lev_pct": blev / hwc})
    s4.figures["logs_levels"] = {
        "type": "table", "title": "Logs and levels tell the same story here",
        "alt": "Table comparing the work-from-home coefficient in logs and in dollars per hour, unweighted and weighted, "
               "raw and adjusted; the implied percentage differences agree within a few points.",
        "columns": [{"key": "spec", "label": "Specification", "align": "left"},
                    {"key": "est", "label": "Estimator", "align": "left"},
                    {"key": "log", "label": "Log points", "format": "num3", "align": "right"},
                    {"key": "log_pct", "label": "exp(b) \u2212 1", "format": "pct1", "align": "right"},
                    {"key": "lev", "label": "Dollars per hour", "align": "right"},
                    {"key": "lev_pct", "label": "Dollars \u00f7 commuter mean", "format": "pct1", "align": "right"}],
        "rows": ll_rows, "source": SOURCE,
        "note": "Commuter means are weighted for WLS rows and unweighted for OLS rows. Levels use hourly wage in dollars."}
    f4 = lambda v: W.fnum(v, 4)  # noqa: E731
    sh, sw_ = se_head["ols"]["se"], se_head["wls"]["se"]
    s4.figures["se_table"] = {
        "type": "table", "title": "Same coefficient, five standard errors",
        "alt": "Table of standard errors for the adjusted work-from-home coefficient under five variance estimators. Most "
               "agree closely; clustering by state is several times larger because it answers a different question.",
        "columns": [{"key": "method", "label": "Variance estimator", "align": "left"},
                    {"key": "ols", "label": "OLS", "align": "right"}, {"key": "wls", "label": "WLS", "align": "right"},
                    {"key": "repeats", "label": "What it imagines repeating", "align": "left"}],
        "rows": [
            {"method": "Classical (iid)", "ols": f4(sh["iid"]), "wls": f4(sw_["iid"]),
             "repeats": "independent draws of workers with a common error variance"},
            {"method": "Heteroskedasticity-robust (HC1)", "ols": f4(sh["hc1"]), "wls": f4(sw_["hc1"]),
             "repeats": "independent draws of workers"},
            {"method": "Clustered by household (CR1)", "ols": f4(sh["cr_hh"]), "wls": f4(sw_["cr_hh"]),
             "repeats": "independent draws of households"},
            {"method": "ACS replicate weights (SDR, 80)", "ols": f4(SE["adj_log_olsf"]), "wls": f4(SE["adj_log"]),
             "repeats": "the ACS address sample and its weighting, as the Census Bureau encodes them"},
            {"method": f"Clustered by state (CR1, {NS} clusters)", "ols": f4(sh["cr_state"]), "wls": f4(sw_["cr_state"]),
             "repeats": "independent draws of states, which the ACS does not do"}],
        "source": SOURCE,
        "note": ("Headline specification (WFH, age, age\u00b2, sex, education). The OLS entry in the replicate row applies each "
                 "replicate's perturbation (REPWTP_r \u00f7 PERWT) to equal case weights, an approximation because the "
                 "replicates also re-run the weighting adjustments.")}
    irows = []
    for dim, k in (("State", 5), ("Occupation group", 5), ("Education", 4)):
        for d_ in sel[dim][:k]:
            irows.append({"label": f"Drop {d_['label']}", "group": dim, "estimate": d_["gap"], "role": "highlight"
                          if abs(d_["change"]) >= 0.5 * max_abs_change else "muted"})
    s4.figures["influence"] = {
        "type": "dot", "format": "num3",
        "title": "No single state, occupation, or education group explains the small WLS\u2013OLS gap",
        "subtitle": "WLS minus OLS adjusted coefficient after dropping one group at a time (largest movers shown)",
        "alt": "Dot plot of the weighted-minus-unweighted coefficient gap after dropping single states, occupation groups, "
               "and education levels; every value stays within about a hundredth of a log point of the full-sample gap.",
        "x_label": "WLS \u2212 OLS coefficient (log points)",
        "reference": {"value": gap_full, "label": "full sample"}, "rows": irows, "source": SOURCE,
        "note": "Headline specification. Rows are the five states and five occupation groups whose removal changes the gap most, plus all four education levels."}
    s4.ledgers["adjusted_gap"] = {
        "title": "Do people who work from home earn more? The adjusted contrast (ACS 2024)",
        "target_population": POP[0].upper() + POP[1:] + "; about " + W.fnum(c4w["pop"] / 1e6, 0) + " million people.",
        "estimand": ("The population linear-projection coefficient on working from home (TRANWORK = 80) in a regression of "
                     "log hourly wage on WFH, age, age\u00b2, sex, and four education levels. A descriptive adjusted "
                     "contrast between WFH workers and commuters, not the causal effect of working from home."),
        "estimator": f"WLS with PERWT on {W.fint(n)} person records; OLS with equal case weights reported alongside.",
        "explicit_weights": ("PERWT, the ACS person weight: base weight adjusted for noninterview and calibrated to Census "
                             "population estimates. Equal case weights in the OLS comparison."),
        "implicit_weights": ("Within education groups, the coefficient averages WFH\u2013commuter contrasts with weights "
                             "proportional to population share \u00d7 p(1 \u2212 p), where p is the WFH share; high-overlap "
                             "groups count most (Chapter 5)."),
        "randomness": "The ACS sample of addresses and the response process. WFH is not assigned by any design.",
        "variance_estimator": "Successive difference replication with 80 replicate weights: Var = (4/80)\u03a3(\u03b2_r \u2212 \u03b2)\u00b2, df = 79.",
        "assumptions": ("TRANWORK codes the primary means of transportation last week, so hybrid workers who mostly commute "
                        "count as commuters; hourly wages use weeks-worked interval midpoints and state top-coded wage "
                        "income as released; no causal interpretation."),
        "facts": ["ch4.adj_wls", "ch4.adj_ols", "ch4.n_sample", "ch4.prev_w", "ch4.se_wls_sdr"]}
    s4.ledgers["occupation_adjusted"] = {
        "title": "The same contrast within occupation, industry, and state",
        "target_population": POP[0].upper() + POP[1:] + ".",
        "estimand": ("The population linear-projection coefficient on WFH after adding fixed effects for detailed occupation, "
                     "industry, and state: a WFH\u2013commuter contrast among workers with the same recorded job and "
                     "location, still descriptive."),
        "estimator": f"WLS with PERWT and {SF_oi.k - 8} fixed-effect dummies, solved as sparse normal equations.",
        "explicit_weights": "PERWT (ACS person weight). Equal case weights for OLS.",
        "implicit_weights": ("A linear probability model for WFH with additive fixed effects; about "
                             f"{W.fpct(signed['wls']['share_commuters_neg'], 0)} of weighted commuters get negative implied "
                             "weight because their predicted WFH probability is below zero (Chapter 5)."),
        "randomness": "The ACS sample and response process.",
        "variance_estimator": "SDR, 80 replicates, each a full re-solve of the fixed-effect normal equations; df = 79.",
        "assumptions": ("Occupation and industry are measured for the main job; controlling for them conditions on outcomes "
                        "of the same choices that shape WFH, so the contrast is not a structural wage premium."),
        "facts": ["ch4.occind_wls", "ch4.occind_ols", "ch4.occind_shrink"]}

    man4 = {"key": "ch4", "slug": "ch04-regression", "status": "draft", "code": "build.py (with wfhlib.py, test_wfhlib.py, verify.R)",
            "inputs": [
                {"path": "analysis/usa/acs/part_2020_2024.parquet", "rows": n,
                 "note": "SAMPLE 202401; " + W.SAMPLE_WHERE.format(s=202401) + f"; sample flow {flow}"},
                {"path": "analysis/usa/acs_repwt/part_2020_2024.parquet", "rows": n,
                 "note": "REPWTP1-80 joined on SAMPLE+SERIAL+PERNUM, one read; 1:1 alignment asserted"},
                {"path": "analysis/usa/metadata/acs.design.json", "note": "SDR, 80 replicates, c = 4/80, df = 79"},
                {"path": "analysis/usa/metadata/acs.dictionary.json", "note": "labels asserted: TRANWORK 80 'Worked at home'; "
                 "CLASSWKR 2 'Works for wages'; WKSWORK2 4 '40-47 weeks', 6 '50-52 weeks'"}],
            "validation": val4,
            "diagnostics": {"topcoding": top, "moulton": moul, "dumouchel_duncan_log": dd_log, "dumouchel_duncan_levels": dd_lev,
                            "influence": infl, "signed_weights_occind": {k: {kk: (vv.tolist() if isinstance(vv, np.ndarray) else vv)
                                                                              for kk, vv in v.items()} for k, v in signed.items()},
                            "headline_lpm_range": lin_head}}
    s4.write(HERE, man4)
    log("ch4 artifacts written:", len(s4.facts), "facts,", len(s4.figures), "figures,", len(s4.ledgers), "ledgers")

    # ================================================================== Chapter 5 artifacts
    s5 = Store("ch5", "ch05-hidden-weights")
    pop_share, reg_share = est5w["pop_share"], est5w["reg_share"]
    reg_share_u = est5u["reg_share"]
    n_c = np.bincount(cell, minlength=C)
    s5.add("n_cells", C, str(C), "Occupation-by-education cells after pooling (23 SOC major groups x 4 education levels, "
           "small cells merged within occupation)", unit="cells", variance="none")
    s5.add("n_base_cells", N_OG * 4, str(N_OG * 4), "Occupation-by-education cells before pooling", unit="cells", variance="none")
    s5.add("n_merges", len(merges), str(len(merges)), "Number of within-occupation education merges needed to give every "
           "cell n >= 100 and at least 30 WFH workers and 30 commuters", unit="merges", variance="none")
    s5.add("n_og", N_OG, str(N_OG), "SOC 2018 major occupation groups represented", unit="groups", variance="none")
    order = np.argsort(prevog)
    lo_g, hi_g = int(order[0]), int(order[-1])
    s5.add("prev_occ_lo_label", W.OCC_GROUPS[lo_g][2], W.OCC_GROUPS[lo_g][2], "Occupation group with the lowest WFH share",
           variance="none")
    s5.add("prev_occ_lo", prevog[lo_g], W.fpct(prevog[lo_g], 1), "Lowest occupation-group WFH share (PERWT-weighted)",
           se=prevog_se[lo_g], variance="replicate_sdr(80)", df=W.DF_SDR, weight=wls_w, n=int((og == lo_g).sum()))
    s5.add("prev_occ_hi_label", W.OCC_GROUPS[hi_g][2], W.OCC_GROUPS[hi_g][2], "Occupation group with the highest WFH share",
           variance="none")
    s5.add("prev_occ_hi", prevog[hi_g], W.fpct(prevog[hi_g], 1), "Highest occupation-group WFH share (PERWT-weighted)",
           se=prevog_se[hi_g], variance="replicate_sdr(80)", df=W.DF_SDR, weight=wls_w, n=int((og == hi_g).sum()))
    pc = fit5w["p"]
    s5.add("p_cell_min", pc.min(), W.fpct(pc.min(), 1), "Lowest cell WFH share (PERWT-weighted)", variance="none")
    s5.add("p_cell_max", pc.max(), W.fpct(pc.max(), 1), "Highest cell WFH share (PERWT-weighted)", variance="none")
    tc = fit5w["tau"]
    s5.add("tau_min", tc.min(), W.fnum(tc.min(), 3), "Smallest cell contrast (log points)", unit="log points", variance="none")
    s5.add("tau_max", tc.max(), W.fnum(tc.max(), 3), "Largest cell contrast (log points)", unit="log points", variance="none")
    est_c = (f"cell contrasts: within each occupation-by-education cell, the PERWT-weighted difference in mean {LOGW} between "
             "WFH workers and commuters, net of a common age-sex profile estimated in the cell-fixed-effect regression. "
             f"Population: {POP}.")
    s5.coef("cellfe_ols", fit5u["beta"], se5["ols"]["se"]["cr_hh"], sdr=False, n=n, weight=ols_w, note=NOTE_OLS_CI,
            estimand=f"Coefficient on WFH in an unweighted regression of {LOGW} on WFH, age, age\u00b2, sex, and "
                     f"{C} occupation-by-education cell fixed effects. {P}")
    s5.coef("cellfe_wls", fit5w["beta"], SE["m5"], sdr=True, n=n, weight=wls_w,
            estimand=f"Population linear-projection coefficient on WFH (PERWT-weighted) in the same cell-fixed-effect "
                     f"regression; equals the average of {est_c.split(':')[0]} with weights N_c p_c (1 - p_c).")
    s5.coef("pate", est5w["pate"], SE["pate"], sdr=True, n=n, weight=wls_w,
            estimand="PATE-analogue: population-share-weighted average of the " + est_c)
    s5.coef("att", est5w["att"], SE["att"], sdr=True, n=n, weight=wls_w,
            estimand="ATT-analogue: average of the " + est_c.split(". Population")[0] + ", weighted by each cell's number of "
                     "WFH workers (N_c p_c).")
    s5.coef("atu", est5w["atu"], SE["atu"], sdr=True, n=n, weight=wls_w,
            estimand="ATU-analogue: average of the " + est_c.split(". Population")[0] + ", weighted by each cell's number of "
                     "commuters (N_c (1 - p_c)).")
    s5.coef("att_minus_atu", full["att_minus_atu"], SE["att_minus_atu"], sdr=True, n=n, weight=wls_w,
            estimand="ATT-analogue minus ATU-analogue (log points)")
    s5.coef("proj_minus_pate", full["proj_minus_pate"], SE["proj_minus_pate"], sdr=True, n=n, weight=wls_w,
            estimand="Survey-weighted projection coefficient minus PATE-analogue (log points)")
    pate_ratio = fit5w["beta"] / est5w["pate"]
    s5.add("proj_pate_ratio", pate_ratio, W.fnum(pate_ratio, 2), "Survey-weighted projection coefficient divided by the "
           "PATE-analogue", unit="ratio", variance="none")
    # effective sample
    top10 = np.argsort(-reg_share)[:10]
    s5.add("top10_reg", reg_share[top10].sum(), W.fpct(reg_share[top10].sum(), 0), "Share of the projection's implicit "
           "weight held by the 10 cells with the most weight", variance="none")
    s5.add("top10_pop", pop_share[top10].sum(), W.fpct(pop_share[top10].sum(), 0), "Population share of those 10 cells",
           variance="none")
    low = pc < 0.05
    s5.add("lowp_n_cells", int(low.sum()), str(int(low.sum())), "Cells where fewer than 5% work from home", unit="cells",
           variance="none")
    s5.add("lowp_pop", pop_share[low].sum(), W.fpct(pop_share[low].sum(), 0), "Population share of cells where fewer than "
           "5% work from home", variance="none")
    s5.add("lowp_reg", reg_share[low].sum(), W.fpct(reg_share[low].sum(), 0), "Implicit-weight share of cells where fewer "
           "than 5% work from home", variance="none")
    hi_ = pc >= 0.25
    s5.add("hip_pop", pop_share[hi_].sum(), W.fpct(pop_share[hi_].sum(), 0), "Population share of cells where 25% or more "
           "work from home", variance="none")
    s5.add("hip_reg", reg_share[hi_].sum(), W.fpct(reg_share[hi_].sum(), 0), "Implicit-weight share of cells where 25% or "
           "more work from home", variance="none")
    eff_pop, eff_reg = 1 / np.sum(pop_share ** 2), 1 / np.sum(reg_share ** 2)
    s5.add("eff_cells_pop", eff_pop, W.fnum(eff_pop, 0), "Effective number of cells under population shares, 1/sum(s_c^2)",
           unit="cells", variance="none")
    s5.add("eff_cells_reg", eff_reg, W.fnum(eff_reg, 0), "Effective number of cells under the projection's implicit weights",
           unit="cells", variance="none")
    ppp = pc * (1 - pc)
    s5.add("per_worker_ratio", ppp.max() / ppp.min(), W.fnum(ppp.max() / ppp.min(), 0), "Ratio of the largest to smallest "
           "per-worker implicit weight p_c (1 - p_c) across cells", unit="ratio", variance="none")
    big = int(np.argmax(reg_share))
    s5.add("top_cell", cell_labels[big], cell_labels[big], "Cell with the largest implicit weight", variance="none")
    s5.add("top_cell_reg", reg_share[big], W.fpct(reg_share[big], 1), "Implicit-weight share of that cell", variance="none")
    s5.add("top_cell_pop", pop_share[big], W.fpct(pop_share[big], 1), "Population share of that cell", variance="none")
    s5.add("top_cell_p", pc[big], W.fpct(pc[big], 0), "WFH share in that cell", variance="none")
    lb = int([c for c in np.argsort(-pop_share) if pc[c] < 0.05][0])
    s5.add("lowp_big_cell", cell_labels[lb], cell_labels[lb], "Largest cell (by population share) among cells where fewer "
           "than 5% work from home", variance="none")
    s5.add("lowp_big_pop", pop_share[lb], W.fpct(pop_share[lb], 1), "Population share of that cell", variance="none")
    s5.add("lowp_big_reg", reg_share[lb], W.fpct(reg_share[lb], 1), "Implicit-weight share of that cell", variance="none")
    s5.add("lowp_big_p", pc[lb], W.fpct(pc[lb], 1), "WFH share in that cell", variance="none")

    def named(prefix, label):
        c = cell_labels.index(label)
        s5.add(f"{prefix}_pop", pop_share[c], W.fpct(pop_share[c], 1), f"Population share of {label}", variance="none")
        s5.add(f"{prefix}_reg", reg_share[c], W.fpct(reg_share[c], 1), f"Implicit-weight share of {label}", variance="none")
        s5.add(f"{prefix}_p", pc[c], W.fpct(pc[c], 0), f"WFH share (PERWT-weighted) in {label}", variance="none")
        s5.add(f"{prefix}_tau", tc[c], W.fnum(tc[c], 3), f"WFH-commuter contrast in {label}, net of the common age-sex "
               "profile (log points)", unit="log points", se=float(tau_se[c]), variance="replicate_sdr(80)", df=W.DF_SDR,
               n=int(n_c[c]), weight=wls_w)

    named("hp_ba", "Healthcare practitioners · BA+")
    named("sales_ba", "Sales · BA+")
    corr = float(np.corrcoef(reg_share, reg_share_u)[0, 1])
    s5.add("reg_share_corr", corr, W.fnum(corr, 2), "Correlation across cells between the weighted and unweighted "
           "regressions' implicit-weight shares", variance="none")
    # Sloczynski
    for lab, sl, sek in (("wls", sl5w, True), ("ols", sl5u, False)):
        wt_ = wls_w if lab == "wls" else ols_w
        var_ = "replicate_sdr(80)" if sek else "none"
        s5.add(f"sl_w1_{lab}", sl["w1"], W.fpct(sl["w1"], 0), f"Sloczynski weight on the ATT (APLE on WFH workers) in the "
               f"{lab.upper()} cell-fixed-effect coefficient: (1-rho)V0/(rho V1 + (1-rho)V0), V_d = variance of the linear "
               "propensity score among group d", se=SE["sl5_w1"] if sek else None, df=W.DF_SDR if sek else None,
               variance=var_, weight=wt_, n=n)
        s5.add(f"sl_rho_{lab}", sl["rho"], W.fpct(sl["rho"], 1), f"Share working from home ({lab.upper()} weighting)",
               variance="none", weight=wt_, n=n)
    s5.coef("sl_att", sl5w["att"], SE["sl5_att"], sdr=True, n=n, weight=wls_w,
            estimand="Sloczynski's APLE on WFH workers (ATT under his Corollary 1): mean log wage of WFH workers minus the "
                     "commuter projection of log wage on the linear propensity score, evaluated at the WFH workers' mean score")
    s5.coef("sl_atu", sl5w["atu"], SE["sl5_atu"], sdr=True, n=n, weight=wls_w,
            estimand="Sloczynski's APLE on commuters (ATU under his Corollary 1)")
    s5.coef("sl_ape", sl5w["ape"], SE["sl5_ape"], sdr=True, n=n, weight=wls_w,
            estimand="Sloczynski's APE = rho x ATT_S + (1 - rho) x ATU_S")
    s5.add("sl4_w1", sl4w["w1"], W.fpct(sl4w["w1"], 0), "Sloczynski weight on the ATT for Chapter 4's headline WLS model "
           "(education dummies only)", se=SE["sl4_w1"], variance="replicate_sdr(80)", df=W.DF_SDR, weight=wls_w, n=n)
    hybrid = sl5w["w1"] * est5w["att"] + (1 - sl5w["w1"]) * est5w["atu"]
    s5.add("sl_hybrid", hybrid, W.fnum(hybrid, 3), "Sloczynski's WLS weights applied to the cell-based ATT- and "
           "ATU-analogues, w1 x ATT_cell + (1 - w1) x ATU_cell: a consistency check, not an identity", unit="log points",
           variance="none")
    s5.add("m5_lpm_min", lin_m5["min"], W.fnum(lin_m5["min"], 3), "Lowest fitted WFH probability in the linear probability "
           "model of the cell-fixed-effect regression (cells + age, age^2, sex; WLS)", variance="none")
    s5.add("m5_neg_share", lin_m5["neg_controls_wshare"], W.fpct(lin_m5["neg_controls_wshare"], 1), "PERWT-weighted share "
           "of commuters with a negative fitted probability in that model", variance="none")
    # signed weights
    sw = signed["wls"]
    s5.add("neg_commuters", sw["share_commuters_neg"], W.fpct(sw["share_commuters_neg"], 1), "PERWT-weighted share of "
           "commuters whose implied regression weight is negative (linear-probability prediction below zero) in the "
           "occupation + industry + state fixed-effect specification", variance="none", weight=wls_w, n=int((D == 0).sum()))
    s5.add("neg_mass", sw["neg_mass_share"], W.fpct(sw["neg_mass_share"], 1), "Share of total absolute implied weight that "
           "enters with the wrong sign, same specification", variance="none", weight=wls_w, n=n)
    s5.add("lpm_min_occind", sw["min"], W.fnum(sw["min"], 2), "Lowest fitted WFH probability, occupation + industry + state "
           "linear probability model (WLS)", variance="none")
    s5.add("lpm_max_occind", sw["max"], W.fnum(sw["max"], 2), "Highest fitted WFH probability, same model", variance="none")
    s5.add("lpm_min_head", lin_head["wls"]["min"], W.fpct(lin_head["wls"]["min"], 1), "Lowest fitted WFH probability in "
           "Chapter 4's headline specification (WLS)", variance="none")
    s5.add("lpm_max_head", lin_head["wls"]["max"], W.fpct(lin_head["wls"]["max"], 1), "Highest fitted WFH probability in "
           "Chapter 4's headline specification (WLS)", variance="none")
    neg_by = sw["by_og_share_commuters_neg"]
    top_neg = int(np.argmax(neg_by))
    s5.add("neg_top_occ", W.OCC_GROUPS[top_neg][2], W.OCC_GROUPS[top_neg][2], "Occupation group with the highest share of "
           "commuters carrying negative implied weight", variance="none")
    s5.add("neg_top_occ_share", neg_by[top_neg], W.fpct(neg_by[top_neg], 0), "That group's weighted share of commuters with "
           "negative implied weight", variance="none")
    s5.add("educ_tau_ba", fit4w["tau"][3], W.fnum(fit4w["tau"][3], 3), "Within-education WFH-commuter contrast for BA+ "
           "workers, net of the common age-sex profile (Chapter 4 headline WLS)", unit="log points", se=tau4_se[3],
           variance="replicate_sdr(80)", df=W.DF_SDR, weight=wls_w, n=int((e4 == 3).sum()))
    s5.add("educ_tau_lths", fit4w["tau"][0], W.fnum(fit4w["tau"][0], 3), "Within-education contrast for workers without a "
           "high school diploma (same model)", unit="log points", se=tau4_se[0], variance="replicate_sdr(80)", df=W.DF_SDR,
           weight=wls_w, n=int((e4 == 0).sum()))

    # ---- Chapter 5 figures
    cell_rows = [{"label": cell_labels[c], "pop_share": float(pop_share[c]), "treat_share": float(pc[c]),
                  "effect": float(tc[c]), "effect_se": float(tau_se[c]), "n": int(n_c[c])} for c in range(C)]
    s5.figures["cells"] = {
        "type": "cells", "title": "Occupation-by-education cells: who works from home, and the wage contrast in each",
        "alt": f"Interactive view of {C} occupation-by-education cells showing each cell's population share, work-from-home "
               "share, and WFH\u2013commuter wage contrast, with the regression's implicit weights compared to population shares.",
        "subtitle": "Log hourly wage, people who work from home versus commuters, cell by cell.",
        "outcome_label": "log hourly wage", "treatment_label": "works from home", "effect_format": "num3",
        "cells": cell_rows, "ols_coef": fit5u["beta"], "wls_coef": fit5w["beta"], "source": SOURCE,
        "note": ("pop_share and treat_share are PERWT-weighted; effect is the within-cell WFH \u2212 commuter difference in mean "
                 "log hourly wage net of a common age\u2013sex profile, so the implicit-weight average "
                 "\u03a3 pop_share\u00b7p(1\u2212p)\u00b7effect / \u03a3 pop_share\u00b7p(1\u2212p) reproduces wls_coef exactly. "
                 "effect_se from 80 SDR replicates. ols_coef is the unweighted regression with the same cells.")}
    chk = sum(r_["pop_share"] * r_["treat_share"] * (1 - r_["treat_share"]) * r_["effect"] for r_ in cell_rows) / sum(
        r_["pop_share"] * r_["treat_share"] * (1 - r_["treat_share"]) for r_ in cell_rows)
    if abs(chk - fit5w["beta"]) > 1e-6:
        raise AssertionError(f"cells.json does not reproduce wls_coef: {chk} vs {fit5w['beta']}")
    val5.append({"check": "cells.json implicit-weight average reproduces wls_coef", "result": f"|diff| = {abs(chk - fit5w['beta']):.2e}"})
    prow = [{"label": W.OCC_GROUPS[g][2], "value": float(prevog[g]), "ci_low": float(prevog[g] - W.T_SDR * prevog_se[g]),
             "ci_high": float(prevog[g] + W.T_SDR * prevog_se[g]), "role": "weighted"} for g in np.argsort(-prevog)]
    s5.figures["prevalence_by_occ"] = {
        "type": "bar", "format": "pct1", "title": "Working from home is concentrated in a few occupation groups",
        "subtitle": "Share of full-time wage and salary workers aged 25\u201364 whose main way to work is working at home, 2024",
        "alt": f"Horizontal bar chart of work-from-home shares across {N_OG} occupation groups, from about "
               f"{round(100 * prevog.min())} percent in {W.OCC_GROUPS[lo_g][2].lower()} to about {round(100 * prevog.max())} "
               f"percent in {W.OCC_GROUPS[hi_g][2].lower()}.",
        "x_label": "Share working from home (PERWT-weighted)", "domain": [0, 0.5], "rows": prow, "source": SOURCE,
        "note": "Intervals: 80-replicate SDR, t with 79 df. Occupation groups are 2018 SOC major groups built from OCC code ranges."}
    six = [
        ci_rows("Unweighted regression, cell fixed effects", "Regression coefficients", fit5u["beta"], se5["ols"]["se"]["cr_hh"],
                False, "unweighted"),
        ci_rows("Survey-weighted projection, cell fixed effects", "Regression coefficients", fit5w["beta"], SE["m5"], True,
                "weighted"),
        ci_rows("Chapter 4 headline (education only, weighted)", "Regression coefficients", c4w["adj_log"], SE["adj_log"], True,
                "muted"),
        ci_rows("Population-weighted (PATE-analogue)", "Averages of the same cell contrasts", est5w["pate"], SE["pate"], True,
                "highlight"),
        ci_rows("WFH-weighted (ATT-analogue)", "Averages of the same cell contrasts", est5w["att"], SE["att"], True, "treated"),
        ci_rows("Commuter-weighted (ATU-analogue)", "Averages of the same cell contrasts", est5w["atu"], SE["atu"], True,
                "control")]
    s5.figures["six_way"] = {
        "type": "dot", "format": "num3",
        "title": "One set of cell contrasts, several defensible averages",
        "subtitle": f"WFH \u2212 commuter difference in log hourly wage, {C} occupation-by-education cells, 2024 ACS",
        "alt": "Dot plot comparing regression coefficients with population-, WFH-, and commuter-weighted averages of the same "
               "cell contrasts; the survey-weighted regression sits near the WFH-weighted average, above the population average.",
        "x_label": "Log points", "reference": {"value": 0, "label": "no difference"}, "rows": six, "source": SOURCE,
        "note": "Weighted rows: 80-replicate SDR, t with 79 df. " + NOTE_OLS_CI +
                " The projection equals the average of the cell contrasts with weights N_c p_c(1 \u2212 p_c)."}
    pop_og = np.bincount(cell_og, weights=pop_share, minlength=N_OG)
    reg_og = np.bincount(cell_og, weights=reg_share, minlength=N_OG)
    srows = [{"label": W.OCC_GROUPS[g][2], "left": float(pop_og[g]), "right": float(reg_og[g]),
              "role": "highlight" if reg_og[g] > 1.5 * pop_og[g] else ("muted" if reg_og[g] < pop_og[g] / 1.5 else "weighted")}
             for g in np.argsort(-reg_og)]
    s5.figures["effective_sample"] = {
        "type": "slope", "format": "pct1",
        "title": "The regression's effective sample is not the population",
        "subtitle": "Share of workers vs share of the survey-weighted regression's implicit weight, by occupation group",
        "alt": "Slope chart from each occupation group's share of workers to its share of the regression's implicit weight; "
               "computer, business, and management groups gain weight while production, transportation, and food service lose it.",
        "left_label": "Share of workers", "right_label": "Share of regression weight", "rows": srows, "source": SOURCE,
        "note": "Implicit weight of a cell = N_c p_c (1 \u2212 p_c) (Angrist 1998), summed within occupation group."}
    lowp_by_pop = [int(c) for c in np.argsort(-pop_share) if pc[c] < 0.05]
    pick = list(dict.fromkeys([int(c) for c in np.argsort(-reg_share)[:8]] + [int(c) for c in np.argsort(-pop_share)[:6]]
                              + lowp_by_pop[:3]))
    pick = sorted(pick, key=lambda c: -reg_share[c])
    s5.figures["cell_table"] = {
        "type": "table", "title": "Cells that dominate the regression, and large cells that barely count",
        "alt": "Table of the cells with the largest implicit weight and the largest population shares, with their WFH shares "
               "and contrasts; large low-WFH cells such as production and transportation carry little regression weight.",
        "columns": [{"key": "cell", "label": "Cell", "align": "left"}, {"key": "n", "label": "Records", "format": "int", "align": "right"},
                    {"key": "pop", "label": "Share of workers", "format": "pct1", "align": "right"},
                    {"key": "p", "label": "WFH share", "format": "pct1", "align": "right"},
                    {"key": "reg", "label": "Regression weight", "format": "pct1", "align": "right"},
                    {"key": "tau", "label": "Contrast (log points)", "format": "num3", "align": "right"},
                    {"key": "se", "label": "SE", "align": "right"}],
        "rows": [{"cell": cell_labels[c], "n": int(n_c[c]), "pop": float(pop_share[c]), "p": float(pc[c]),
                  "reg": float(reg_share[c]), "tau": float(tc[c]), "se": W.fnum(float(tau_se[c]), 3)} for c in pick],
        "highlight_key": "reg", "source": SOURCE,
        "note": ("The eight cells with the most implicit weight, the six largest cells, and the three largest cells where "
                 "fewer than 5% work from home. SE: 80-replicate SDR.")}
    s5.figures["sloczynski"] = {
        "type": "table", "title": "Smaller groups get larger weights",
        "alt": (f"Table of Sloczynski's decomposition for the unweighted and survey-weighted cell regressions: "
                f"{W.fpct(sl5w['rho'], 0)} of workers work from home, yet the contrast for home workers receives "
                f"{W.fpct(sl5w['w1'], 0)} of the regression's weight."),
        "columns": [{"key": "est", "label": "Regression", "align": "left"},
                    {"key": "coef", "label": "Coefficient", "format": "num3", "align": "right"},
                    {"key": "rho", "label": "Share WFH (\u03c1)", "format": "pct1", "align": "right"},
                    {"key": "w1", "label": "Weight on ATT (\u03c9\u2081)", "format": "pct1", "align": "right"},
                    {"key": "att", "label": "ATT (APLE)", "format": "num3", "align": "right"},
                    {"key": "atu", "label": "ATU (APLE)", "format": "num3", "align": "right"},
                    {"key": "ape", "label": "APE", "format": "num3", "align": "right"}],
        "rows": [{"est": "Unweighted (OLS)", "coef": fit5u["beta"], "rho": sl5u["rho"], "w1": sl5u["w1"], "att": sl5u["att"],
                  "atu": sl5u["atu"], "ape": sl5u["ape"]},
                 {"est": "Survey-weighted (WLS)", "coef": fit5w["beta"], "rho": sl5w["rho"], "w1": sl5w["w1"],
                  "att": sl5w["att"], "atu": sl5w["atu"], "ape": sl5w["ape"]}],
        "source": SOURCE,
        "note": ("Cell-fixed-effect model. p(X) is the linear projection of WFH on the cells and the age\u2013sex terms; "
                 "ATT and ATU are Sloczynski's average partial linear effects, equal to the causal ATT and ATU only under "
                 "unconfoundedness and linearity in p(X). Coefficient = \u03c9\u2081\u00b7ATT + (1 \u2212 \u03c9\u2081)\u00b7ATU exactly.")}
    nrow = [{"label": W.OCC_GROUPS[g][2], "value": float(neg_by[g]), "role": "highlight"}
            for g in np.argsort(-neg_by) if neg_by[g] > 0.005]
    s5.figures["signed_weights"] = {
        "type": "bar", "format": "pct1",
        "title": "Where the linear specification assigns negative weight",
        "subtitle": "Share of each occupation group's commuters whose implied weight is negative, occupation + industry + state model",
        "alt": ("Horizontal bar chart of the share of commuters with negative implied regression weight by occupation group, "
                "highest in low-WFH groups: " + ", ".join(W.OCC_GROUPS[g][2].lower() for g in np.argsort(-neg_by)[:3]) + "."),
        "x_label": "Share of commuters (PERWT-weighted) with negative implied weight", "rows": nrow, "source": SOURCE,
        "note": ("Implied weight of observation i is PERWT_i(D_i \u2212 \u2113_i), where \u2113 is the fitted value of a linear "
                 "probability model for WFH with the regression's controls; a commuter with \u2113 < 0 enters the comparison "
                 "with the wrong sign. Groups under 0.5% not shown. In Chapter 4's headline model every fitted value lies "
                 "between 0 and 1, so no weight is negative.")}
    s5.ledgers["six_way"] = {
        "title": "Whose wage gap? Averaging the same cell contrasts in different ways",
        "target_population": POP[0].upper() + POP[1:] + ".",
        "estimand": ("Descriptive averages of occupation-by-education cell contrasts in log hourly wage (WFH minus commuters, "
                     "net of a common age\u2013sex profile): population-weighted (PATE-analogue), WFH-weighted "
                     "(ATT-analogue), commuter-weighted (ATU-analogue), and the survey-weighted projection coefficient."),
        "estimator": ("Weighted cell moments from PERWT; contrasts are within-cell differences in mean log wage minus the "
                      "fitted age\u2013sex profile; the projection is WLS with cell fixed effects."),
        "explicit_weights": "PERWT for every weighted quantity; equal case weights for the OLS comparison.",
        "implicit_weights": ("Projection: N_c p_c(1 \u2212 p_c). PATE-analogue: N_c. ATT-analogue: N_c p_c. "
                             "ATU-analogue: N_c(1 \u2212 p_c)."),
        "randomness": "The ACS sample and response process; no treatment assignment.",
        "variance_estimator": "SDR, 80 replicates; every contrast, cell weight, and average is recomputed per replicate; df = 79.",
        "assumptions": (f"{len(merges)} small cells merged within occupation (n \u2265 100, 30+ in each arm); common "
                        "age\u2013sex profile across cells; descriptive, not causal; TRANWORK construct caveat applies."),
        "facts": ["ch5.cellfe_wls", "ch5.pate", "ch5.att", "ch5.atu", "ch5.cellfe_ols"]}
    s5.ledgers["sloczynski"] = {
        "title": "Smaller groups get larger weights (S\u0142oczy\u0144ski decomposition)",
        "target_population": POP[0].upper() + POP[1:] + ".",
        "estimand": ("The cell-fixed-effect projection coefficient, re-expressed as \u03c9\u2081\u00b7ATT + (1 \u2212 "
                     "\u03c9\u2081)\u00b7ATU, where ATT and ATU are average partial linear effects on WFH workers and commuters."),
        "estimator": ("Linear propensity score p(X) from WLS of WFH on cells and age\u2013sex terms; within-group projections "
                      "of log wage on p(X); weights from group shares and within-group variances of p(X)."),
        "explicit_weights": "PERWT.",
        "implicit_weights": "\u03c9\u2081 = (1 \u2212 \u03c1)V\u2080 / [\u03c1V\u2081 + (1 \u2212 \u03c1)V\u2080] on the ATT; the smaller group gets the larger weight.",
        "randomness": "The ACS sample and response process.",
        "variance_estimator": "SDR, 80 replicates, full recomputation; df = 79.",
        "assumptions": ("The decomposition is an in-sample identity; reading its components as ATT and ATU requires "
                        "unconfoundedness and linearity in p(X), which this descriptive analysis does not claim."),
        "facts": ["ch5.sl_w1_wls", "ch5.sl_att", "ch5.sl_atu", "ch5.sl_ape"]}
    man5 = {"key": "ch5", "slug": "ch05-hidden-weights", "status": "draft",
            "code": "../ch04-regression/build.py (shared pipeline with wfhlib.py; this folder's build.py calls it)",
            "inputs": man4["inputs"], "validation": val5,
            "diagnostics": {"cell_merges": merges, "cells": [{"label": cell_labels[c], "n": int(n_c[c]), "pop_share": float(pop_share[c]),
                                                              "p": float(pc[c]), "p_se": float(p_se[c]), "tau": float(tc[c]),
                                                              "tau_se": float(tau_se[c]), "reg_share": float(reg_share[c]),
                                                              "reg_share_ols": float(reg_share_u[c]),
                                                              "tau_ols": float(fit5u["tau"][c])} for c in range(C)],
                            "sloczynski_ch4_headline": {"ols": sl4u, "wls": sl4w},
                            "cellfe_lpm_range": lin_m5, "replicate_factor_se_m5_ols": SE["m5_olsf"],
                            "occupation_groups": [{"label": W.OCC_GROUPS[g][2], "soc": W.OCC_GROUPS[g][3],
                                                   "occ_range": [W.OCC_GROUPS[g][0], W.OCC_GROUPS[g][1]],
                                                   "prev": float(prevog[g]), "prev_se": float(prevog_se[g]),
                                                   "pop_share": float(pop_og[g]), "reg_share": float(reg_og[g]),
                                                   "neg_share_commuters": float(neg_by[g])} for g in range(N_OG)]}}
    s5.write(CH5, man5)
    log("ch5 artifacts written:", len(s5.facts), "facts,", len(s5.figures), "figures,", len(s5.ledgers), "ledgers")

    # ------------------------------------------------------------------ console summary
    summ = {k: s4.facts[k]["display"] for k in s4.facts}
    summ5 = {k: s5.facts[k]["display"] for k in s5.facts}
    print(json.dumps({"ch4": summ, "ch5": summ5}, indent=1, ensure_ascii=False))
    print("R check:", json.dumps(r_result, indent=1, default=str)[:3000])
    log("done")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(run_r="--no-r" not in sys.argv, reuse_r="--reuse-r" in sys.argv)
