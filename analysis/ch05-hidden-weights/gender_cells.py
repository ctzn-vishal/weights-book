"""gender_cells.py -- Chapter 5's second example: the within-cell gender wage gap.

Called by this folder's build.py after the shared Chapter 4-5 pipeline has written artifacts/.
Reuses that pipeline's analytic cache (../ch04-regression/_scratch/analytic_ch45.parquet: the frozen
ACS 2024 sample with PERWT and REPWTP1-80; microdata, stays in Box) and the same 85
occupation-by-education cells, and adds facts, two figures, one ledger, and validation records to
this chapter's artifacts.

Model:  log w = beta * female + alpha_c + g1 (age-45) + g2 (age-45)^2 + g3 WFH + e,  cells c as in cells.json.
The cell contrast tau_c is the PERWT-weighted female-male difference in mean (log w - z'gamma) in cell c;
beta = sum_c N_c p_c (1-p_c) tau_c / sum_c N_c p_c (1-p_c) exactly (Angrist 1998), p_c = female share.
Averages: population-share (N_c), women-share (N_c p_c), men-share (N_c (1-p_c)).
Variance: SDR, 80 replicates, scale 4/80, df 79; every quantity is recomputed per replicate.
Deterministic: no randomness, fixed rounding through wfhlib.dump.

    python gender_cells.py          add the gender facts to artifacts/ (artifacts must already exist)
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import polars as pl

CH4 = "C:/Users/Vishal Singh/Box/ipums/book/chapters/ch04-regression"
CH5 = "C:/Users/Vishal Singh/Box/ipums/book/chapters/ch05-hidden-weights"
sys.path.insert(0, CH4)
import wfhlib as W  # noqa: E402

CACHE = f"{CH4}/_scratch/analytic_ch45.parquet"
ART = f"{CH5}/artifacts"
R_CHECK = f"{CH5}/_scratch/r_gender_check.json"
SOURCE = ("IPUMS USA, ACS 2024 1-year (SAMPLE 202401), analysis/usa/acs/part_2020_2024.parquet; "
          "replicate weights REPWTP1\u201380 from analysis/usa/acs_repwt/part_2020_2024.parquet")
POP = ("wage and salary workers aged 25\u201364 in the 2024 ACS who usually worked 30+ hours a week for 40+ weeks "
       "in the past 12 months, had positive wage income, and were at work in the reference week")
LOGW = "log hourly wage, log(INCWAGE / (UHRSWORK \u00d7 weeks-worked interval midpoint))"
NOTE_OLS_CI = "OLS intervals use household-clustered (CR1) standard errors and the normal critical value."
SEG_LO, SEG_HI = 0.20, 0.80   # a cell is "segregated" when women are under 20% or over 80% of it


def load():
    df = pl.read_parquet(CACHE, columns=["SERIAL", "PERWT", "lnw", "D", "z1", "z2", "z3", "cell"]
                         + [f"REPWTP{i}" for i in range(1, W.N_REPS + 1)])
    cells = json.load(open(f"{ART}/figures/cells.json", encoding="utf-8"))["cells"]
    cell = df["cell"].to_numpy().astype(np.int64)
    C = len(cells)
    n_c = np.bincount(cell, minlength=C)
    if not all(int(n_c[i]) == cells[i]["n"] for i in range(C)):
        raise AssertionError("cells.json is not in cell-index order or does not match the cache")
    return df, cell, C, [c["label"] for c in cells]


def wcorr(x, y, w):
    mx, my = np.average(x, weights=w), np.average(y, weights=w)
    return float(np.sum(w * (x - mx) * (y - my)) / np.sqrt(np.sum(w * (x - mx) ** 2) * np.sum(w * (y - my) ** 2)))


def compute():
    df, cell, C, labels = load()
    n = df.height
    y = df["lnw"].to_numpy()
    fem = df["z3"].to_numpy()
    Z = np.column_stack([df["z1"].to_numpy(), df["z2"].to_numpy(), df["D"].to_numpy()])
    w = df["PERWT"].to_numpy().astype(float)
    hh = np.unique(df["SERIAL"].to_numpy(), return_inverse=True)[1]
    R = df.select([f"REPWTP{i}" for i in range(1, W.N_REPS + 1)]).to_numpy().astype(np.float64)
    ones = np.ones(n)
    nf = np.bincount(cell, weights=fem, minlength=C)
    nm = np.bincount(cell, minlength=C) - nf
    if nf.min() < 30 or nm.min() < 30:
        raise AssertionError("a cell has fewer than 30 women or 30 men; the WFH partition cannot be reused")

    CM = W.CellMoments(cell, fem, Z, y, C)
    Sw, Su = CM.sums(w), CM.sums(ones)
    fw, fu = W.fe_solve(Sw), W.fe_solve(Su)
    ew, eu = W.estimands_from_cells(fw), W.estimands_from_cells(fu)
    slw = W.sloczynski_from_moments(Sw)
    se_ols = W.fe_ses(cell, C, fem, Z, y, ones, {"hh": hh})
    se_wls_cr = W.fe_ses(cell, C, fem, Z, y, w, {"hh": hh})
    for nm_, a, b in (("moment engine vs within WLS", fw["beta"], se_wls_cr["beta"]),
                      ("moment engine vs within OLS", fu["beta"], se_ols["beta"]),
                      ("FWL cell representation", fw["beta"], fw["fwl"]),
                      ("Sloczynski identity", fw["beta"], slw["implied"]),
                      ("PATE split", ew["pate"], ew["rho"] * ew["att"] + (1 - ew["rho"]) * ew["atu"])):
        if abs(a - b) > 1e-9:
            raise AssertionError(f"{nm_}: {a} vs {b}")

    overlap = fw["p"] * (1 - fw["p"])
    seg = (fw["p"] < SEG_LO) | (fw["p"] > SEG_HI)
    ps, rs = ew["pop_share"], ew["reg_share"]

    def stats_for(f, e):
        ov = f["p"] * (1 - f["p"])
        return {"wls": f["beta"], "pate": e["pate"], "att": e["att"], "atu": e["atu"], "rho": e["rho"],
                "proj_minus_pate": f["beta"] - e["pate"], "att_minus_atu": e["att"] - e["atu"],
                "seg_pop": float(e["pop_share"][seg].sum()), "seg_reg": float(e["reg_share"][seg].sum()),
                "seg_tau": float(np.sum(e["pop_share"][seg] * f["tau"][seg]) / e["pop_share"][seg].sum()),
                "int_tau": float(np.sum(e["pop_share"][~seg] * f["tau"][~seg]) / e["pop_share"][~seg].sum()),
                "corr": wcorr(f["tau"], ov, e["pop_share"])}

    full = stats_for(fw, ew)
    full["sl_w1"] = slw["w1"]
    reps = {k: np.empty(W.N_REPS) for k in full}
    tau_r = np.empty((W.N_REPS, C))
    for r in range(W.N_REPS):
        Sr = CM.sums(R[:, r])
        fr = W.fe_solve(Sr)
        er = W.estimands_from_cells(fr)
        sr = stats_for(fr, er)
        sr["sl_w1"] = W.sloczynski_from_moments(Sr)["w1"]
        for k in full:
            reps[k][r] = sr[k]
        tau_r[r] = fr["tau"]
    SE = {k: W.sdr_se(full[k], reps[k]) for k in full}
    tau_se = W.sdr_se_vec(fw["tau"], tau_r)

    o = np.argsort(-rs)
    out = {
        "n": n, "C": C, "labels": labels, "fw": fw, "fu": fu, "ew": ew, "eu": eu, "slw": slw, "full": full, "SE": SE,
        "tau_se": tau_se, "seg": seg, "overlap": overlap, "n_seg": int(seg.sum()),
        "top10_pop": float(ps[o[:10]].sum()), "top10_reg": float(rs[o[:10]].sum()),
        "eff_pop": float(1 / np.sum(ps ** 2)), "eff_reg": float(1 / np.sum(rs ** 2)),
        "ols_se_hh": se_ols["se"]["cr_hh"], "wls_se_hh": se_wls_cr["se"]["cr_hh"],
        "min_p_cell": int(np.argmin(fw["p"])), "max_p_cell": int(np.argmax(fw["p"])),
        "min_women": int(nf.min()), "min_men": int(nm.min()),
    }
    return out


def write(res: dict) -> None:
    facts = json.load(open(f"{ART}/facts.json", encoding="utf-8"))
    ledgers = json.load(open(f"{ART}/ledger.json", encoding="utf-8"))
    manifest = json.load(open(f"{ART}/manifest.json", encoding="utf-8"))
    F = facts["facts"]
    for k in list(F):
        if k.startswith("gg_"):
            del F[k]

    def add(k, value, display, estimand, **kw):
        f = {"value": value, "display": display, "estimand": estimand, "source": SOURCE, "unit": None, "se": None,
             "ci_low": None, "ci_high": None, "ci_display": None, "df": None, "n": None, "weight": None,
             "variance": None, "benchmark": None, "note": ""}
        f.update(kw)
        F["gg_" + k] = f

    def coef(k, est, se, estimand, *, sdr=True, unit="log points", d=3, note="", kind="num"):
        t = W.T_SDR if sdr else W.Z975
        lo, hi = est - t * se, est + t * se
        disp = {"num": W.fnum(est, d), "pct": W.fpct(est, d)}[kind]
        add(k, est, disp, estimand, unit=unit, se=se, ci_low=lo, ci_high=hi, ci_display=W.fci(lo, hi, kind, d),
            df=(W.DF_SDR if sdr else None), n=res["n"], weight=("PERWT" if sdr else "none (equal case weights)"),
            variance=("replicate_sdr(80)" if sdr else "cluster_robust(household)"), note=note)

    full, SE, fw, ew, C = res["full"], res["SE"], res["fw"], res["ew"], res["C"]
    P = f"Population: {POP}."
    est_c = (f"cell contrasts: within each of the {C} occupation-by-education cells of this chapter, the PERWT-weighted "
             f"difference in mean {LOGW} between women and men, net of a common age and work-from-home profile "
             f"estimated in the cell-fixed-effect regression. {P}")
    coef("wls", full["wls"], SE["wls"], "Coefficient on female (PERWT-weighted) in a regression of " + LOGW +
         f" on female, age, age\u00b2, working from home, and {C} occupation-by-education cell fixed effects; equals the "
         "average of the gender " + est_c[5:] + " with weights N_c p_c (1 \u2212 p_c), p_c the cell's female share.")
    coef("ols", res["fu"]["beta"], res["ols_se_hh"], "The same regression unweighted (OLS). " + P, sdr=False, note=NOTE_OLS_CI)
    coef("pate", full["pate"], SE["pate"], "Population-share-weighted average of the gender " + est_c)
    coef("att", full["att"], SE["att"], "Women-share-weighted average (weights N_c p_c) of the gender " + est_c)
    coef("atu", full["atu"], SE["atu"], "Men-share-weighted average (weights N_c (1 \u2212 p_c)) of the gender " + est_c)
    coef("proj_minus_pate", full["proj_minus_pate"], SE["proj_minus_pate"],
         "Survey-weighted regression coefficient minus the population-share average of the gender cell contrasts")
    coef("att_minus_atu", full["att_minus_atu"], SE["att_minus_atu"],
         "Women-share average minus men-share average of the gender cell contrasts")
    coef("rho", full["rho"], SE["rho"], f"PERWT-weighted share of workers who are women. {P}", unit=None, d=1, kind="pct")
    coef("seg_tau", full["seg_tau"], SE["seg_tau"],
         f"Population-share average of the gender cell contrasts in cells where women are under {int(SEG_LO * 100)}% or over "
         f"{int(SEG_HI * 100)}% of workers")
    coef("int_tau", full["int_tau"], SE["int_tau"],
         f"Population-share average of the gender cell contrasts in cells where women are between {int(SEG_LO * 100)}% and "
         f"{int(SEG_HI * 100)}% of workers")
    add("corr", full["corr"], W.fnum(full["corr"], 2),
        "Population-share-weighted correlation across cells between the gender contrast and the overlap term p_c (1 \u2212 p_c)",
        se=SE["corr"], df=W.DF_SDR, n=res["n"], weight="PERWT", variance="replicate_sdr(80)")
    add("sl_w1", full["sl_w1"], W.fpct(full["sl_w1"], 0),
        "Sloczynski weight on the women's term in the survey-weighted cell regression: (1 \u2212 \u03c1)V0 / (\u03c1V1 + (1 \u2212 \u03c1)V0)",
        se=SE["sl_w1"], df=W.DF_SDR, n=res["n"], weight="PERWT", variance="replicate_sdr(80)")
    add("n_seg", res["n_seg"], str(res["n_seg"]),
        f"Cells in which women are under {int(SEG_LO * 100)}% or over {int(SEG_HI * 100)}% of workers", unit="cells", variance="none")
    add("seg_pop", full["seg_pop"], W.fpct(full["seg_pop"], 1), "Share of workers (PERWT) in those segregated cells",
        weight="PERWT", variance="none")
    add("seg_reg", full["seg_reg"], W.fpct(full["seg_reg"], 1),
        "Share of the survey-weighted regression's implicit weight N_c p_c (1 \u2212 p_c) in those segregated cells", variance="none")
    add("top10_pop", res["top10_pop"], W.fpct(res["top10_pop"], 1),
        "Share of workers in the ten cells with the most implicit weight in the gender regression", weight="PERWT", variance="none")
    add("top10_reg", res["top10_reg"], W.fpct(res["top10_reg"], 1), "Share of implicit weight held by those ten cells", variance="none")
    add("eff_cells_pop", res["eff_pop"], W.fnum(res["eff_pop"], 1),
        "Effective number of equally weighted cells under population shares (inverse sum of squared shares)", unit="cells", variance="none")
    add("eff_cells_reg", res["eff_reg"], W.fnum(res["eff_reg"], 1),
        "Effective number of equally weighted cells under the gender regression's implicit weights", unit="cells", variance="none")
    add("tau_min", fw["tau"].min(), W.fnum(fw["tau"].min(), 3), "Smallest (most negative) gender cell contrast", unit="log points", variance="none")
    add("tau_max", fw["tau"].max(), W.fnum(fw["tau"].max(), 3), "Largest gender cell contrast", unit="log points", variance="none")
    add("p_min", fw["p"].min(), W.fpct(fw["p"].min(), 1), "Lowest cell female share (PERWT-weighted)", weight="PERWT", variance="none")
    add("p_max", fw["p"].max(), W.fpct(fw["p"].max(), 1), "Highest cell female share (PERWT-weighted)", weight="PERWT", variance="none")
    add("p_min_label", res["labels"][res["min_p_cell"]], res["labels"][res["min_p_cell"]], "Cell with the lowest female share", variance="none")
    add("p_max_label", res["labels"][res["max_p_cell"]], res["labels"][res["max_p_cell"]], "Cell with the highest female share", variance="none")

    # figures
    t, z = W.T_SDR, W.Z975
    rows = [{"label": "Unweighted regression, cell fixed effects", "group": "Regression coefficients",
             "estimate": res["fu"]["beta"], "ci_low": res["fu"]["beta"] - z * res["ols_se_hh"],
             "ci_high": res["fu"]["beta"] + z * res["ols_se_hh"], "role": "unweighted", "n": res["n"]},
            {"label": "Survey-weighted projection, cell fixed effects", "group": "Regression coefficients",
             "estimate": full["wls"], "ci_low": full["wls"] - t * SE["wls"], "ci_high": full["wls"] + t * SE["wls"],
             "role": "weighted", "n": res["n"]}]
    for k, lab in (("pate", "Population-share average (PATE-analogue)"), ("att", "Women-share average (ATT-analogue)"),
                   ("atu", "Men-share average (ATU-analogue)")):
        rows.append({"label": lab, "group": "Averages of the same cell contrasts", "estimate": full[k],
                     "ci_low": full[k] - t * SE[k], "ci_high": full[k] + t * SE[k], "role": "design", "n": res["n"]})
    figs = {}
    figs["gender_six_way"] = {
        "type": "dot", "format": "num3",
        "title": "The gender gap: unequal implicit weights, and the same answer",
        "subtitle": f"Female \u2212 male difference in log hourly wage, the same {C} occupation-by-education cells, 2024 ACS",
        "alt": "Dot plot of the female-male log wage coefficient from two regressions beside population-, women-, and "
               "men-share averages of the same cell contrasts; the survey-weighted regression and the population-share "
               "average coincide, and all five sit near minus 0.2.",
        "x_label": "Log points", "reference": {"value": 0, "label": "no difference"}, "rows": rows, "source": SOURCE,
        "note": "Weighted rows: 80-replicate SDR, t with 79 df. " + NOTE_OLS_CI +
                " Contrasts are net of a common age and work-from-home profile."}
    bands = [(0.0, SEG_LO, f"Under {int(SEG_LO * 100)}% women"), (SEG_LO, SEG_HI, f"{int(SEG_LO * 100)}\u2013{int(SEG_HI * 100)}% women"),
             (SEG_HI, 1.01, f"Over {int(SEG_HI * 100)}% women")]
    trows = []
    ps, rs, tau = ew["pop_share"], ew["reg_share"], fw["tau"]
    for lo, hi, lab in bands:
        m = (fw["p"] >= lo) & (fw["p"] < hi)
        trows.append({"band": lab, "cells": int(m.sum()), "pop": float(ps[m].sum()), "reg": float(rs[m].sum()),
                      "tau": float(np.sum(ps[m] * tau[m]) / ps[m].sum())})
    figs["gender_overlap_table"] = {
        "type": "table", "title": "Where the gender regression's weight goes",
        "subtitle": "Cells grouped by their female share; contrasts are population-share averages within the band",
        "alt": "Table of three bands of cells by female share, showing the number of cells, their share of workers, their share "
               "of the regression's implicit weight, and their average gender contrast; mixed cells gain weight and segregated "
               "cells lose it, while the average contrast differs little between the first two bands.",
        "columns": [{"key": "band", "label": "Female share of the cell", "align": "left"},
                    {"key": "cells", "label": "Cells", "format": "int", "align": "right"},
                    {"key": "pop", "label": "Share of workers", "format": "pct1", "align": "right"},
                    {"key": "reg", "label": "Regression weight", "format": "pct1", "align": "right"},
                    {"key": "tau", "label": "Average contrast (log points)", "format": "num3", "align": "right"}],
        "rows": trows, "highlight_key": "reg", "source": SOURCE,
        "note": "Implicit weight of a cell = N_c p_c (1 \u2212 p_c) with p_c the cell's PERWT-weighted female share."}
    for name, fig in figs.items():
        W.dump(fig, f"{ART}/figures/{name}.json")

    ledgers["ledgers"]["gender_gap"] = {
        "title": "The within-cell gender wage gap: the same averages, a second outcome",
        "target_population": POP[0].upper() + POP[1:] + ".",
        "estimand": "Descriptive averages of occupation-by-education cell contrasts in log hourly wage (women minus men, net of a "
                    "common age and work-from-home profile): population-weighted (PATE-analogue), women-weighted (ATT-analogue), "
                    "men-weighted (ATU-analogue), and the survey-weighted projection coefficient.",
        "estimator": "Weighted cell moments from PERWT; contrasts are within-cell differences in mean log wage minus the fitted "
                     "age and work-from-home profile; the projection is WLS with cell fixed effects.",
        "explicit_weights": "PERWT for every weighted quantity; equal case weights for the OLS comparison.",
        "implicit_weights": "Projection: N_c p_c(1 \u2212 p_c) with p_c the female share. PATE-analogue: N_c. ATT-analogue: N_c p_c. "
                            "ATU-analogue: N_c(1 \u2212 p_c).",
        "randomness": "The ACS sample and response process; sex is not assigned.",
        "variance_estimator": "SDR, 80 replicates; every contrast, cell weight, and average is recomputed per replicate; df = 79.",
        "assumptions": f"The chapter's {C} cells reused unchanged (every cell has at least 30 women and 30 men); common age and "
                       "work-from-home profile across cells; descriptive, not causal.",
        "facts": ["ch5.gg_wls", "ch5.gg_pate", "ch5.gg_att", "ch5.gg_atu", "ch5.gg_ols"]}

    val = [v for v in manifest.get("validation", []) if not str(v.get("check", "")).startswith("gender example")]
    val.append({"check": "gender example: exact identities on the real data (moment engine = within WLS; FWL cell representation; "
                         "Sloczynski identity; PATE split)", "result": "agree to 1e-9"})
    val.append({"check": "gender example: the WFH cell partition satisfies the 30-per-side rule for sex as well",
                "result": "pass (minimum women and men per cell recorded in diagnostics)"})
    if os.path.exists(R_CHECK):
        rc = json.load(open(R_CHECK, encoding="utf-8"))
        rows_ = []
        ours = {"svymean_female": (full["rho"], SE["rho"]), "wr_cellfe_female": (full["wls"], SE["wls"])}
        for chk in rc.get("checks", []):
            o = ours.get(chk["check"])
            if o is None:
                continue
            rows_.append({"check": chk["check"], "r_estimate": chk["estimate"], "py_estimate": o[0],
                          "abs_diff_estimate": abs(chk["estimate"] - o[0]), "r_se": chk["se"], "py_se": o[1],
                          "rel_diff_se": abs(chk["se"] - o[1]) / o[1], "method": chk.get("method", ""),
                          "pass": abs(chk["estimate"] - o[0]) < 1e-8 and abs(chk["se"] - o[1]) / o[1] < 1e-6})
        val.append({"check": "gender example: R sentinel (verify_gender.R): survey 4.5 svrepdesign(type='successive-difference', "
                             "mse=TRUE), svymean of female and withReplicates within-cell WLS coefficient on female",
                    "result": "run" if rows_ else "r_gender_check.json had no matching rows", "r_version": rc.get("r_version"),
                    "survey": rc.get("survey"), "rows": rows_})
    else:
        val.append({"check": "gender example: R sentinel (verify_gender.R)", "result": "not run: _scratch/r_gender_check.json missing"})
    manifest["validation"] = val
    inputs = [i for i in manifest.get("inputs", []) if "analytic_ch45" not in i.get("path", "")]
    inputs.append({"path": "book/chapters/ch04-regression/_scratch/analytic_ch45.parquet", "rows": res["n"],
                   "note": "gender example: the pipeline's frozen analytic sample with REPWTP1-80 (a cache of the two inputs above; "
                           "written by ../ch04-regression/build.py; microdata, never exported)"})
    manifest["inputs"] = inputs
    diag = manifest.setdefault("diagnostics", {})
    diag["gender_example"] = {"code": "gender_cells.py", "segregated_bands": f"female share under {SEG_LO} or over {SEG_HI}",
                              "cells_reused": C, "min_women_per_cell": res["min_women"], "min_men_per_cell": res["min_men"]}
    manifest["code"] = "build.py (runs ../ch04-regression/build.py, then gender_cells.py)"

    W.dump({"key": "ch5", "facts": F}, f"{ART}/facts.json")
    W.dump(ledgers, f"{ART}/ledger.json")
    import datetime as dt
    manifest["generated_at"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    with open(f"{ART}/manifest.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(W.clean(manifest), f, sort_keys=True, indent=2, ensure_ascii=False)
        f.write("\n")


def main() -> None:
    res = compute()
    write(res)
    full, SE = res["full"], res["SE"]
    print("gender example:", {k: (round(full[k], 4), round(SE[k], 4)) for k in ("wls", "pate", "att", "atu", "rho", "proj_minus_pate", "corr")},
          "seg pop/reg", round(full["seg_pop"], 3), round(full["seg_reg"], 3), "sl_w1", round(full["sl_w1"], 3))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
