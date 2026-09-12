"""Chapter 3 build: Point Estimates and Design-Based Uncertainty (key ch3).

    python build.py          -> regenerates artifacts/ deterministically
    Rscript verify.R         -> writes _scratch/verify_R_results.csv (R survey oracle)
    python build.py          -> re-run folds the R comparison into manifest.validation

Reads (select columns only):
  NHANES  nhanes_analysis.parquet (+ BPQ040A/BPQ050A and auscultatory BPX* from the
          superset nhanes_full_1999_2023.parquet, joined on SEQN + CYCLE_YEAR)
  NHIS    analysis/nhis/nhis_core/part_2015_2024.parquet, 2023 sample adults
  BRFSS   BRFSS_2026/cleaned/brfss_multi_rec.parquet, 2023 and 2024

Variance: a small stratified with-replacement Taylor engine (below), checked
against svy 0.28 in this script (dual path) and against R survey 4.5 in verify.R.
Microdata never leave Box; only aggregates are written.
"""
from __future__ import annotations

import csv
import datetime as _dt
import json
import os
from pathlib import Path

os.environ.setdefault("NO_COLOR", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import duckdb
import numpy as np
import polars as pl
from scipy import stats

CH = Path(__file__).resolve().parent
ART = CH / "artifacts"
FIG = ART / "figures"
SCR = CH / "_scratch"
KEY = "ch3"
SLUG = "ch03-design"

NHANES_A = "C:/Users/Vishal Singh/Box/NHANES/data/processed/nhanes_analysis.parquet"
NHANES_F = "C:/Users/Vishal Singh/Box/NHANES/data/processed/nhanes_full_1999_2023.parquet"
NHIS = "C:/Users/Vishal Singh/Box/ipums/analysis/nhis/nhis_core/part_2015_2024.parquet"
BRFSS = "C:/Users/Vishal Singh/Box/BRFSS/BRFSS_2026/cleaned/brfss_multi_rec.parquet"

SEED = 20260910
THIN_DRAWS = 200
THIN_FRACS = [1.0, 0.10, 0.02, 0.01, 0.005, 0.002]

# 2000 U.S. standard population (Census P25-1130), single-age counts from SEER
# (seer.cancer.gov/stdpopulations/stdpop.singleages.html), summed to the NCHS
# Data Brief 511 age groups 18-39, 40-59, 60+.
STD_POP_COUNTS = {"18-39": 85671821, "40-59": 72816615, "60+": 45363752}
STD_POP_TOTAL = sum(STD_POP_COUNTS.values())
S_A = np.array([STD_POP_COUNTS[k] / STD_POP_TOTAL for k in ("18-39", "40-59", "60+")])

# NCHS Data Brief 511 (Fryar, Kit, Carroll, Afful, Oct 2024), published values.
DB511 = {
    "prev_crude": (47.7, 1.1, "45.4-49.9", 6084),
    "prev_adj": (44.5, 1.1, "42.1-46.9", 6084),
    "prev_men_crude": (50.8, 1.1, "48.4-53.2", 2776),
    "prev_women_crude": (44.6, 1.5, "41.4-47.8", 3308),
    "prev_men_adj": (48.8, 1.2, "46.2-51.4", 2776),
    "prev_women_adj": (40.1, 1.3, "37.2-43.1", 3308),
    "prev_18_39": (23.4, 1.6, "20.2-26.9", 1712),
    "prev_40_59": (52.5, 1.4, "49.5-55.4", 1681),
    "prev_60p": (71.6, 1.3, "68.7-74.3", 2691),
    "aware": (59.2, 1.3, "56.4-61.9", 3240),
    "treat": (51.2, 1.2, "48.6-53.7", 3238),
    "control": (20.7, 0.9, "18.8-22.8", 3242),
    "pre_aware": (60.2, 1.3, "57.4-63.0", 4297),
    "pre_treat": (50.3, 1.4, "47.5-53.1", 4295),
    "pre_control": (22.2, 0.8, "20.6-23.9", 4305),
}

SRC_NHANES_L = "NHANES August 2021-August 2023 (_L files), MEC-examined adults; NHANES/data/processed/nhanes_analysis.parquet"
SRC_NHANES_P = "NHANES 2017-March 2020 pre-pandemic (P_ files); nhanes_analysis.parquet + nhanes_full_1999_2023.parquet (BPQ040A/BPQ050A)"
SRC_NHANES_J = "NHANES 2017-2018 (_J files), BPXO_J and BPX_J on the same participants; nhanes_full_1999_2023.parquet"
SRC_NHIS = "IPUMS NHIS 2023 sample adults (analysis/nhis/nhis_core/part_2015_2024.parquet)"
SRC_BRFSS24 = "CDC BRFSS 2024 public file (BRFSS_2026/cleaned/brfss_multi_rec.parquet); 49 states (no Tennessee), DC, Guam, Puerto Rico, U.S. Virgin Islands"
SRC_BRFSS23 = "CDC BRFSS 2023 public file (BRFSS_2026/cleaned/brfss_multi_rec.parquet); 48 states (no Kentucky, no Pennsylvania) and DC"


# ---------------------------------------------------------------- formatting
MINUS = "\u2212"


def sig(x, digits=10):
    """Fixed rounding for determinism (10 significant digits)."""
    if x is None:
        return None
    x = float(x)
    if not np.isfinite(x):
        return None
    return float(f"{x:.{digits}g}")


def _neg(s: str) -> str:
    return s.replace("-", MINUS) if s.startswith("-") else s


def pct(p, d=1):
    return _neg(f"{p * 100:.{d}f}%")


def pp(x, d=1):
    """A proportion difference shown as a signed number of percentage points."""
    return _neg(f"{x * 100:+.{d}f}".replace("+", ""))


def num(x, d=2):
    return _neg(f"{x:.{d}f}")


def integer(n):
    return f"{int(round(n)):,}"


def ci_pct(lo, hi, d=1):
    return f"{pct(lo, d)}\u2013{pct(hi, d)}"


def ci_pp(lo, hi, d=1):
    return f"{pp(lo, d)} to {pp(hi, d)}"


def tcrit(df):
    return float(stats.t.ppf(0.975, df)) if df and df > 0 else float("nan")


def satterthwaite(v1, df1, v2, df2):
    return (v1 + v2) ** 2 / (v1 ** 2 / df1 + v2 ** 2 / df2)


# ---------------------------------------------------------------- Taylor engine
class LonelyPSUError(RuntimeError):
    pass


class Design:
    """Stratified, clustered design: rows -> PSU index -> stratum index.

    PSUs are keyed by (stratum, psu) so PSU ids that repeat across strata are
    never pooled (the composite-key rule)."""

    def __init__(self, strata, psu, w):
        strata = np.asarray(strata, dtype=np.int64)
        psu = np.asarray(psu, dtype=np.int64)
        key = np.column_stack([strata, psu])
        ukey, pidx = np.unique(key, axis=0, return_inverse=True)
        us, sidx = np.unique(ukey[:, 0], return_inverse=True)
        self.pidx = pidx.ravel()
        self.psu_str = sidx.ravel()
        self.n_psu = len(ukey)
        self.n_str = len(us)
        self.w = np.asarray(w, dtype=np.float64)
        self.n = len(self.w)

    def var(self, z, rows=None, lonely="fail"):
        """Variance of sum(z) under stratified with-replacement PSU sampling.

        rows=None: z covers every row of the declared design (zero outside a
        domain), so every PSU of the design is kept -- correct domain estimation.
        rows=mask: only those rows exist (the data were subset first), so PSUs
        and strata are re-counted from the surviving rows."""
        pidx = self.pidx if rows is None else self.pidx[rows]
        zz = z if rows is None else z[rows]
        return strat_var(zz, pidx, self.psu_str, self.n_psu, self.n_str, lonely)

    def domain_counts(self, mask):
        """PSUs and strata that contain domain members (NCHS domain df)."""
        present = np.bincount(self.pidx[mask], minlength=self.n_psu) > 0
        strata = np.unique(self.psu_str[present])
        k_psu, k_str = int(present.sum()), int(len(strata))
        nh = np.bincount(self.psu_str[present], minlength=self.n_str)
        return {"psus": k_psu, "strata": k_str, "single": int((nh == 1).sum()), "df": k_psu - k_str}


def strat_var(z, pidx, psu_str, n_psu, n_str, lonely="fail"):
    t_all = np.bincount(pidx, weights=z, minlength=n_psu)
    present = np.bincount(pidx, minlength=n_psu) > 0
    t = t_all[present]
    ps = psu_str[present]
    nh = np.bincount(ps, minlength=n_str)
    sums = np.bincount(ps, weights=t, minlength=n_str)
    mh = np.zeros(n_str)
    np.divide(sums, nh, out=mh, where=nh > 0)
    dev = t - mh[ps]
    ss = np.bincount(ps, weights=dev * dev, minlength=n_str)
    ok = nh > 1
    v = float(np.sum(nh[ok] / (nh[ok] - 1.0) * ss[ok]))
    single = nh == 1
    k_single = int(single.sum())
    k_str = int((nh > 0).sum())
    k_psu = int(present.sum())
    info = {"psus": k_psu, "strata": k_str, "single": k_single, "df": k_psu - k_str}
    if k_single:
        if lonely == "fail":
            raise LonelyPSUError(f"{k_single} strata have a single PSU")
        if lonely in ("certainty", "remove"):
            pass  # a lone PSU contributes nothing
        elif lonely == "adjust":
            grand = float(t.mean())  # centre lone PSUs at the grand mean of PSU totals
            v += float(np.sum((t[single[ps]] - grand) ** 2))
        elif lonely == "average":
            v = v * k_str / int(ok.sum())  # average contribution of the other strata
        else:
            raise ValueError(lonely)
    return v, info


def lin_mean(y, w, d):
    """Hajek ratio mean over domain d and its linearized (influence) values."""
    N = float(np.sum(w * d))
    R = float(np.sum(w * d * y) / N)
    return R, w * d * (y - R) / N


def wonly_var(z, mask):
    """Weights-only (HC1-type) variance: every respondent its own PSU, no strata."""
    zd = z[mask]
    n = len(zd)
    return float(n / (n - 1.0) * np.sum((zd - zd.mean()) ** 2))


def kish(w):
    cv = float(np.std(w) / np.mean(w))
    return 1.0 + cv * cv, cv


def three_ses(des, y, d, lonely="fail"):
    """Point estimate with three standard errors for a proportion in domain d."""
    y = np.asarray(y, dtype=np.float64)
    d = np.asarray(d, dtype=np.float64)
    mask = d > 0
    R, z = lin_mean(y, des.w, d)
    n = int(mask.sum())
    v_naive = R * (1.0 - R) / (n - 1.0)
    v_w = wonly_var(z, mask)
    v_d, _ = des.var(z, lonely=lonely)
    dom = des.domain_counts(mask)
    k, cv = kish(des.w[mask])
    return {
        "est": R, "n": n, "z": z,
        "v_naive": v_naive, "v_w": v_w, "v_d": v_d,
        "se_naive": v_naive ** 0.5, "se_w": v_w ** 0.5, "se_d": v_d ** 0.5,
        "deff": v_d / v_naive, "wfac": v_w / v_naive, "cfac": v_d / v_w,
        "kish": k, "cv_w": cv, "df": dom["df"], "psus": dom["psus"], "strata": dom["strata"],
        "single": dom["single"], "wsum": float(np.sum(des.w[mask])),
    }


def standardized(des, y, d, groups, s):
    """Directly age-standardized proportion: sum_a s_a p_a, linearized."""
    y = np.asarray(y, dtype=np.float64)
    est, z = 0.0, np.zeros(des.n)
    v_naive = 0.0
    parts = []
    for a, s_a in enumerate(s):
        da = d * (groups == a)
        pa, za = lin_mean(y, des.w, da)
        na = int((da > 0).sum())
        est += s_a * pa
        z += s_a * za
        v_naive += s_a * s_a * pa * (1 - pa) / (na - 1.0)
        parts.append((pa, na))
    mask = d > 0
    v_w = wonly_var(z, mask)
    v_d, _ = des.var(z)
    dom = des.domain_counts(mask)
    return {
        "est": est, "n": int(mask.sum()), "z": z, "parts": parts,
        "v_naive": v_naive, "v_w": v_w, "v_d": v_d,
        "se_naive": v_naive ** 0.5, "se_w": v_w ** 0.5, "se_d": v_d ** 0.5,
        "deff": v_d / v_naive, "wfac": v_w / v_naive, "cfac": v_d / v_w,
        "df": dom["df"], "psus": dom["psus"], "strata": dom["strata"], "single": dom["single"],
    }


def ci_t(r, level_df=None):
    df = r["df"] if level_df is None else level_df
    t = tcrit(df)
    return r["est"] - t * r["se_d"], r["est"] + t * r["se_d"], t


# ---------------------------------------------------------------- NHANES data
OSC_S = ["BPXOSY1", "BPXOSY2", "BPXOSY3"]
OSC_D = ["BPXODI1", "BPXODI2", "BPXODI3"]
AUS_S = ["BPXSY1", "BPXSY2", "BPXSY3", "BPXSY4"]
AUS_D = ["BPXDI1", "BPXDI2", "BPXDI3", "BPXDI4"]
INPUTS = []


def load_nhanes():
    con = duckdb.connect()
    a = con.sql(
        "select SEQN, CYCLE_YEAR, SDMVSTRA, SDMVPSU, WTMEC2YR, WTMECPRP, RIDAGEYR, RIAGENDR, "
        "RIDEXPRG, BPQ020, BPQ150, " + ", ".join(OSC_S + OSC_D) +
        f" from read_parquet('{NHANES_A}') where CYCLE_YEAR in (2017, 2019, 2021)"
    ).pl()
    f = con.sql(
        "select SEQN, CYCLE_YEAR, BPQ040A, BPQ050A, " + ", ".join(AUS_S + AUS_D) +
        f" from read_parquet('{NHANES_F}') where CYCLE_YEAR in (2017, 2019, 2021)"
    ).pl()
    d = a.join(f, on=["SEQN", "CYCLE_YEAR"], how="left").sort(["CYCLE_YEAR", "SEQN"])
    INPUTS.append({"path": NHANES_A, "rows": int(a.height),
                   "note": "CYCLE_YEAR in 2017, 2019, 2021; design, weights, BPQ020, BPQ150, BPXOSY1-3, BPXODI1-3"})
    INPUTS.append({"path": NHANES_F, "rows": int(f.height),
                   "note": "same rows; BPQ040A/BPQ050A (pre-pandemic medication items) and auscultatory BPXSY1-4/BPXDI1-4 (2017-2018), absent from the analysis file"})
    return d


def _bp_cols(x, s_cols, d_cols, tag):
    x = x.with_columns([pl.when(pl.col(c) > 0).then(pl.col(c)).otherwise(None).alias(c) for c in s_cols + d_cols])
    return x.with_columns(
        pl.mean_horizontal(s_cols).alias(f"sbp{tag}"),
        pl.mean_horizontal(d_cols).alias(f"dbp{tag}"),
        (pl.sum_horizontal([pl.col(c).is_not_null().cast(pl.Int32) for c in s_cols]) >= 1).alias(f"has_s{tag}"),
        (pl.sum_horizontal([pl.col(c).is_not_null().cast(pl.Int32) for c in d_cols]) >= 1).alias(f"has_d{tag}"),
    )


def derive_nhanes(d, cycle):
    """One cycle's design frame (MEC-examined, weight > 0) with NCHS Data Brief 511 flags."""
    wcol = "WTMECPRP" if cycle == 2019 else "WTMEC2YR"
    x = d.filter(pl.col("CYCLE_YEAR") == cycle).with_columns(pl.col(wcol).fill_null(0.0).alias("wt"))
    x = x.filter(pl.col("wt") > 0)
    x = _bp_cols(x, OSC_S, OSC_D, "")
    if cycle == 2017:
        x = _bp_cols(x, AUS_S, AUS_D, "_a")
    if cycle == 2021:
        med = pl.col("BPQ150") == "Yes"
        med_known = pl.col("BPQ150").is_in(["Yes", "No"]) | (pl.col("BPQ020") == "No")
    else:
        med = (pl.col("BPQ040A") == "Yes") & (pl.col("BPQ050A") == "Yes")
        med_known = (pl.col("BPQ050A").is_in(["Yes", "No"]) | (pl.col("BPQ040A") == "No")
                     | (pl.col("BPQ020") == "No"))
    x = x.with_columns(
        med.fill_null(False).alias("med"),
        med_known.fill_null(False).alias("med_known"),
        (pl.col("BPQ020") == "Yes").fill_null(False).alias("aware"),
        pl.col("BPQ020").is_in(["Yes", "No"]).fill_null(False).alias("aware_known"),
        pl.col("RIDEXPRG").fill_null("").str.starts_with("Yes").alias("preg"),
        (pl.col("RIAGENDR") == "Male").fill_null(False).alias("male"),
        pl.when(pl.col("RIDAGEYR") < 40).then(0).when(pl.col("RIDAGEYR") < 60).then(1)
        .otherwise(2).alias("agegrp"),
    )
    x = x.with_columns(
        ((pl.col("RIDAGEYR") >= 18) & ~pl.col("preg") & pl.col("has_s") & pl.col("has_d")).alias("analytic"),
        ((pl.col("sbp") >= 130) | (pl.col("dbp") >= 80)).fill_null(False).alias("htn_bp"),
        ((pl.col("sbp") >= 140) | (pl.col("dbp") >= 90)).fill_null(False).alias("htn_bp140"),
        ((pl.col("sbp") < 130) & (pl.col("dbp") < 80)).fill_null(False).alias("controlled"),
    )
    x = x.with_columns(
        (pl.col("htn_bp") | pl.col("med")).alias("htn"),
        (pl.col("htn_bp140") | pl.col("med")).alias("htn140"),
    )
    if cycle == 2017:
        x = x.with_columns(
            ((pl.col("sbp_a") >= 130) | (pl.col("dbp_a") >= 80)).fill_null(False).alias("htn_bp_a"),
        ).with_columns((pl.col("htn_bp_a") | pl.col("med")).alias("htn_a"))
    return x


def arr(x, c, dtype=np.float64):
    return x[c].to_numpy().astype(dtype)


def nhanes_design(x):
    return Design(arr(x, "SDMVSTRA", np.int64), arr(x, "SDMVPSU", np.int64), arr(x, "wt"))


# ---------------------------------------------------------------- NHANES analysis
STAGES = ["prev", "aware", "treat", "control"]
STAGE_LABEL = {"prev": "Prevalence", "aware": "Awareness", "treat": "Treatment", "control": "Control"}
STAGE_DENOM = {"prev": "all adults", "aware": "adults with hypertension",
               "treat": "adults with hypertension", "control": "adults with hypertension"}
GROUPS = [("all", "All adults"), ("men", "Men"), ("women", "Women"),
          ("a0", "Ages 18–39"), ("a1", "Ages 40–59"), ("a2", "Ages 60+")]


def cascade(x):
    des = nhanes_design(x)
    A = arr(x, "analytic", bool)
    htn, med, aware = arr(x, "htn", bool), arr(x, "med", bool), arr(x, "aware", bool)
    med_known, aware_known = arr(x, "med_known", bool), arr(x, "aware_known", bool)
    controlled, male, ag = arr(x, "controlled", bool), arr(x, "male", bool), arr(x, "agegrp", np.int64)
    gm = {"all": np.ones(des.n, bool), "men": male, "women": ~male, "a0": ag == 0, "a1": ag == 1, "a2": ag == 2}
    out = {}
    for g, m in gm.items():
        base = A & m
        out[("prev", g)] = three_ses(des, htn, base)
        out[("aware", g)] = three_ses(des, aware, base & htn & aware_known)
        out[("treat", g)] = three_ses(des, med, base & htn & med_known)
        out[("control", g)] = three_ses(des, controlled, base & htn)
    out["adj_all"] = standardized(des, htn, A.astype(float), ag, S_A)
    out["adj_men"] = standardized(des, htn, (A & male).astype(float), ag, S_A)
    out["adj_women"] = standardized(des, htn, (A & ~male).astype(float), ag, S_A)
    out["selfreport"] = three_ses(des, aware, A & aware_known)
    out["htn140"] = three_ses(des, arr(x, "htn140", bool), A)
    out["design"] = {"psus": des.n_psu, "strata": des.n_str, "df": des.n_psu - des.n_str,
                     "n_frame": des.n}
    return des, out


def period_changes(post, pre):
    rows = []
    for st in STAGES:
        for g, glab in GROUPS:
            a, b = post[(st, g)], pre[(st, g)]
            diff = a["est"] - b["est"]
            se_n = (a["v_naive"] + b["v_naive"]) ** 0.5
            se_w = (a["v_w"] + b["v_w"]) ** 0.5
            se_d = (a["v_d"] + b["v_d"]) ** 0.5
            df = satterthwaite(a["v_d"], a["df"], b["v_d"], b["df"])
            p_n = 2 * stats.norm.sf(abs(diff / se_n))
            p_w = 2 * stats.norm.sf(abs(diff / se_w))
            p_d = 2 * stats.t.sf(abs(diff / se_d), df)
            rows.append({"stage": st, "group": g, "group_label": glab, "diff": diff,
                         "se_n": se_n, "se_w": se_w, "se_d": se_d, "df": df, "t_crit": tcrit(df),
                         "p_n": p_n, "p_w": p_w, "p_d": p_d, "n_post": a["n"], "n_pre": b["n"]})
    return rows


def instrument(xj):
    """Same 2017-2018 participants, same weight: auscultatory vs oscillometric."""
    des = nhanes_design(xj)
    both = arr(xj, "analytic", bool) & arr(xj, "has_s_a", bool) & arr(xj, "has_d_a", bool)
    ro = three_ses(des, arr(xj, "htn", bool), both)
    ra = three_ses(des, arr(xj, "htn_a", bool), both)
    v, _ = des.var(ra["z"] - ro["z"])
    df = des.domain_counts(both)["df"]
    ro_bp = three_ses(des, arr(xj, "htn_bp", bool), both)
    ra_bp = three_ses(des, arr(xj, "htn_bp_a", bool), both)
    vb, _ = des.var(ra_bp["z"] - ro_bp["z"])
    dsbp = np.nan_to_num(arr(xj, "sbp_a") - arr(xj, "sbp"))
    m, zm = lin_mean(dsbp, des.w, both.astype(float))
    vm, _ = des.var(zm)
    return {"osc": ro, "aus": ra, "diff": ra["est"] - ro["est"], "diff_se": v ** 0.5, "df": df,
            "osc_bp": ro_bp, "aus_bp": ra_bp, "bp_diff": ra_bp["est"] - ro_bp["est"], "bp_diff_se": vb ** 0.5,
            "sbp_diff": m, "sbp_diff_se": vm ** 0.5,
            "n": int(both.sum()), "psus": des.n_psu, "strata": des.n_str}


def svy_check_nhanes(x, mine):
    """Second implementation: svy 0.28 Taylor path, domain via where=."""
    import svy
    fr = x.select(
        pl.col("SDMVSTRA").cast(pl.Int64),
        (pl.col("SDMVSTRA").cast(pl.Int64) * 10 + pl.col("SDMVPSU").cast(pl.Int64)).alias("psu_key"),
        pl.col("wt"),
        pl.col("htn").cast(pl.Float64).alias("y_htn"),
        pl.col("aware").cast(pl.Float64).alias("y_aware"),
        pl.col("analytic").cast(pl.Int32).alias("dom_prev"),
        (pl.col("analytic") & pl.col("htn") & pl.col("aware_known")).cast(pl.Int32).alias("dom_aware"),
    )
    s = svy.Sample(fr, design=svy.Design(stratum="SDMVSTRA", psu="psu_key", wgt="wt"))
    out = []
    for y, dom, key in [("y_htn", "dom_prev", ("prev", "all")), ("y_aware", "dom_aware", ("aware", "all"))]:
        e = s.estimation.mean(y, where=svy.col(dom) == 1, deff="wr").estimates[0]
        r = mine[key]
        out.append({"estimand": f"NHANES 2021-2023 {key[0]}", "svy_est": e.est, "svy_se": e.se,
                    "svy_df": int(e.df), "svy_deff": e.deff, "mine_est": r["est"], "mine_se": r["se_d"],
                    "mine_df": r["df"], "mine_deff": r["deff"],
                    "max_abs_diff": max(abs(e.est - r["est"]), abs(e.se - r["se_d"]), abs(e.deff - r["deff"]))})
    return out


# ---------------------------------------------------------------- NHIS 2023: domains
def load_nhis():
    con = duckdb.connect()
    x = con.sql(
        "select YEAR, SERIAL, PERNUM, STRATA, PSU, SAMPWEIGHT, ASTATFLG, HYPERTENEV, DELAYCOST, "
        "HINOTCOVE, HEALTH, AGE, REGION, CAST(race_eth5 AS VARCHAR) AS race_eth5, "
        "CAST(educ4 AS VARCHAR) AS educ4, citizen_b, female, CAST(age_group AS VARCHAR) AS age_group "
        f"from read_parquet('{NHIS}') where YEAR = 2023"
    ).pl()
    INPUTS.append({"path": NHIS, "rows": int(x.height),
                   "note": "YEAR = 2023; sample adults ASTATFLG = 1; SAMPWEIGHT; (STRATA, PSU) composite key built for 2023; "
                           "group contrasts use AGE, REGION, race_eth5, educ4, citizen_b, female, age_group"})
    ad = x.filter(pl.col("ASTATFLG") == 1).sort(["SERIAL", "PERNUM"])
    return ad.with_columns(
        (pl.col("STRATA").cast(pl.Int64) * 1000 + pl.col("PSU").cast(pl.Int64)).alias("psu_key"),
        pl.when(pl.col("HYPERTENEV") == 2).then(1.0).when(pl.col("HYPERTENEV") == 1).then(0.0)
        .otherwise(None).alias("hyp"),
        pl.when(pl.col("DELAYCOST") == 2).then(1.0).when(pl.col("DELAYCOST") == 1).then(0.0)
        .otherwise(None).alias("delay"),
        (pl.col("HINOTCOVE") == 2).fill_null(False).alias("unins"),
        pl.when(pl.col("HINOTCOVE") == 2).then(1.0).when(pl.col("HINOTCOVE") == 1).then(0.0)
        .otherwise(None).alias("unins_y"),
        (pl.col("HEALTH") == 5).fill_null(False).alias("poor"),
    )


def nhis_design(ad):
    return Design(arr(ad, "STRATA", np.int64), arr(ad, "PSU", np.int64), arr(ad, "SAMPWEIGHT"))


RULES = ["certainty", "adjust", "average"]


def domain_compare(des, y, d):
    """Declare-then-estimate (all PSUs kept) versus delete-rows-then-declare."""
    y = np.nan_to_num(np.asarray(y, dtype=np.float64))
    d = np.asarray(d, dtype=np.float64)
    m = d > 0
    n = int(m.sum())
    R, z = lin_mean(y, des.w, d)
    v_full, _ = des.var(z)
    _, zs = lin_mean(y[m], des.w[m], np.ones(n))
    zt = des.w * d * y
    se_sub, se_tot_sub, info = {}, {}, None
    for rule in RULES:
        v, info = strat_var(zs, des.pidx[m], des.psu_str, des.n_psu, des.n_str, rule)
        se_sub[rule] = v ** 0.5
        vt, _ = strat_var(zt[m], des.pidx[m], des.psu_str, des.n_psu, des.n_str, rule)
        se_tot_sub[rule] = vt ** 0.5
    try:
        strat_var(zs, des.pidx[m], des.psu_str, des.n_psu, des.n_str, "fail")
        fails = False
    except LonelyPSUError:
        fails = True
    vt_full, _ = des.var(zt)
    return {"est": R, "n": n, "total": float(zt.sum()), "se_full": v_full ** 0.5,
            "se_sub": se_sub, "se_total_full": vt_full ** 0.5, "se_total_sub": se_tot_sub,
            "psus": info["psus"], "strata": info["strata"], "single": info["single"],
            "df_sub": info["df"], "fail_raises": fails, "deff": v_full / (R * (1 - R) / (n - 1)),
            "strata_full": des.n_str, "psus_full": des.n_psu}


def thinning(des, y, valid):
    """Controlled thinning: random domains of shrinking size, same outcome."""
    rng = np.random.default_rng(SEED)
    y = np.nan_to_num(np.asarray(y, dtype=np.float64))
    idx = np.flatnonzero(valid)
    N = len(idx)
    rows = []
    for frac in THIN_FRACS:
        k = int(round(frac * N))
        draws = 1 if frac == 1.0 else THIN_DRAWS
        ratio, psus, single, dfs = [], [], [], []
        for _ in range(draws):
            pick = idx if frac == 1.0 else np.sort(rng.choice(idx, size=k, replace=False))
            d = np.zeros(des.n)
            d[pick] = 1.0
            _, z = lin_mean(y, des.w, d)
            v_full, _ = des.var(z)
            m = d > 0
            _, zs = lin_mean(y[m], des.w[m], np.ones(k))
            v_sub, info = strat_var(zs, des.pidx[m], des.psu_str, des.n_psu, des.n_str, "certainty")
            ratio.append((v_sub / v_full) ** 0.5)
            psus.append(info["psus"])
            single.append(info["single"])
            dfs.append(info["df"])
        ratio = np.array(ratio)
        rows.append({"frac": frac, "n": k, "draws": draws,
                     "psus": float(np.median(psus)), "single": float(np.median(single)),
                     "df": float(np.median(dfs)), "ratio_med": float(np.median(ratio)),
                     "ratio_p10": float(np.percentile(ratio, 10)), "ratio_p90": float(np.percentile(ratio, 90)),
                     "share_short": float(np.mean(ratio < 0.9))})
    return rows


def svy_check_nhis(ad, sparse):
    """svy on the sparse domain: where= (declared design) and subset-first."""
    import svy
    fr = ad.select(
        pl.col("STRATA").cast(pl.Int64), pl.col("psu_key"), pl.col("SAMPWEIGHT"), pl.col("delay"),
        (pl.col("unins") & pl.col("poor") & pl.col("delay").is_not_null()).cast(pl.Int32).alias("dom"),
    )
    des = svy.Design(stratum="STRATA", psu="psu_key", wgt="SAMPWEIGHT")
    s = svy.Sample(fr, design=des)
    e = s.estimation.mean("delay", where=svy.col("dom") == 1, drop_nulls=True).estimates[0]
    sub = svy.Sample(fr.filter(pl.col("dom") == 1), design=des)
    try:
        sub.estimation.mean("delay", drop_nulls=True)
        err = "no error"
    except Exception as ex:  # svy raises SingletonError rather than guessing
        err = type(ex).__name__
    e_cert = sub.singleton.handle("certainty").estimation.mean("delay", drop_nulls=True).estimates[0]
    e_cent = sub.singleton.handle("center").estimation.mean("delay", drop_nulls=True).estimates[0]
    return [
        {"estimand": "NHIS 2023 sparse domain, declared design (where=)", "svy_se": e.se, "mine_se": sparse["se_full"],
         "svy_df": int(e.df), "mine_df_nchs": sparse["df_sub"], "abs_diff": abs(e.se - sparse["se_full"])},
        {"estimand": "NHIS 2023 sparse domain, subset first, no rule", "svy_result": err},
        {"estimand": "NHIS 2023 sparse domain, subset first, certainty", "svy_se": e_cert.se,
         "mine_se": sparse["se_sub"]["certainty"], "abs_diff": abs(e_cert.se - sparse["se_sub"]["certainty"])},
        {"estimand": "NHIS 2023 sparse domain, subset first, center (R adjust)", "svy_se": e_cent.se,
         "mine_se": sparse["se_sub"]["adjust"], "abs_diff": abs(e_cent.se - sparse["se_sub"]["adjust"])},
    ]


# ---------------------------------------------------------------- NHIS 2023: group contrasts in one sample
# A pre-specified family: the uninsured share among sample adults 18-64, compared between
# groups along six dimensions. Every pair is one comparison; the family is fixed before any
# result is seen (region 6, race/ethnicity 10, education 6, citizenship 1, sex 1, age 3 = 27).
REGION_LABEL = {1: "Northeast", 2: "Midwest", 3: "South", 4: "West"}
GROUP_DIMS = [
    ("REGION", "Census region", lambda v: REGION_LABEL[int(v)]),
    ("race_eth5", "Race and Hispanic origin", None),
    ("educ4", "Education", None),
    ("citizen_b", "Citizenship", lambda v: "Citizen" if int(v) == 1 else "Not a citizen"),
    ("female", "Sex", lambda v: "Women" if int(v) == 1 else "Men"),
    ("age_group", "Age group", None),
]
GROUP_ORDER = {"educ4": ["Less than HS", "HS", "Some college", "BA+"],
               "race_eth5": ["White NH", "Black NH", "Hispanic", "Asian/PI NH", "Other/Multiple NH"],
               "age_group": ["18-29", "30-44", "45-64"]}
GEO_DIM = "REGION"


def group_contrasts(des, ad, y, base):
    """All within-dimension pairs of domain means in one sample, with four standard errors:
    naive iid (independent SRS), weights-only, full design with the covariance (Taylor on
    z_a - z_b), and full design treating the two domains as independent."""
    import itertools
    y = np.nan_to_num(np.asarray(y, dtype=np.float64))
    valid = ~np.isnan(np.asarray(ad["unins_y"].to_numpy(), dtype=np.float64))
    rows, means = [], {}
    for col, dim_label, fmt in GROUP_DIMS:
        raw = ad[col].to_list()
        g = np.array([None if v is None else str(v) for v in raw], dtype=object)
        levels = sorted(set(v for v in g.tolist() if v is not None), key=str)
        if col in GROUP_ORDER:
            levels = [l for l in GROUP_ORDER[col] if l in levels]
        est = {}
        for l in levels:
            d = (base & valid & (g == l)).astype(float)
            n = int(d.sum())
            if n < 100:
                continue
            R, z = lin_mean(y, des.w, d)
            v_d, _ = des.var(z)
            m = d > 0
            est[l] = {"est": R, "z": z, "n": n, "v_n": R * (1 - R) / (n - 1.0), "v_w": wonly_var(z, m), "v_d": v_d,
                      "label": fmt(l) if fmt else l}
        means[col] = est
        for a, b in itertools.combinations(levels, 2):
            if a not in est or b not in est:
                continue
            A, B_ = est[a], est[b]
            diff = A["est"] - B_["est"]
            se_n = (A["v_n"] + B_["v_n"]) ** 0.5
            se_w = (A["v_w"] + B_["v_w"]) ** 0.5
            v_d, _ = des.var(A["z"] - B_["z"])
            se_d = v_d ** 0.5
            se_ind = (A["v_d"] + B_["v_d"]) ** 0.5
            df = des.domain_counts((A["z"] != 0) | (B_["z"] != 0))["df"]
            rows.append({"dim": col, "dim_label": dim_label, "a": A["label"], "b": B_["label"],
                         "est_a": A["est"], "est_b": B_["est"], "n_a": A["n"], "n_b": B_["n"], "diff": diff,
                         "se_n": se_n, "se_w": se_w, "se_d": se_d, "se_ind": se_ind, "df": df, "t_crit": tcrit(df),
                         "p_n": 2 * stats.norm.sf(abs(diff / se_n)), "p_w": 2 * stats.norm.sf(abs(diff / se_w)),
                         "p_d": 2 * stats.t.sf(abs(diff / se_d), df)})
    return rows, means


# ---------------------------------------------------------------- BRFSS
TERRITORIES = [66, 72, 78]


def load_brfss():
    con = duckdb.connect()
    b = con.sql(
        "select iyear, xststr, xpsu, xllcpwt, xstate, xrfhlth, bphigh "
        f"from read_parquet('{BRFSS}') where iyear in (2023, 2024)"
    ).pl().sort(["iyear", "xststr", "xpsu"])
    INPUTS.append({"path": BRFSS, "rows": int(b.height),
                   "note": "iyear in 2023, 2024; _STSTR, _PSU, _LLCPWT, _STATE, _RFHLTH, BPHIGH6 (2023 only; odd-year item)"})
    return b


def brfss_block(b):
    out = {}
    x = b.filter(pl.col("iyear") == 2024)
    des = Design(arr(x, "xststr", np.int64), arr(x, "xpsu", np.int64), arr(x, "xllcpwt"))
    fp = x.select(pl.when(pl.col("xrfhlth") == 2).then(1.0).when(pl.col("xrfhlth") == 1).then(0.0)
                  .otherwise(None).alias("fp"))["fp"]
    d = fp.is_not_null().to_numpy()
    r = three_ses(des, np.nan_to_num(fp.to_numpy().astype(float)), d, lonely="adjust")
    try:
        des.var(r["z"], lonely="fail")
        fails = False
    except LonelyPSUError:
        fails = True
    nh = np.bincount(des.psu_str, minlength=des.n_str)
    out["y2024"] = {**r, "n_file": des.n, "psus_full": des.n_psu, "strata_full": des.n_str,
                    "df_full": des.n_psu - des.n_str, "single_full": int((nh == 1).sum()), "fail_raises": fails}
    x = b.filter(pl.col("iyear") == 2023)
    des = Design(arr(x, "xststr", np.int64), arr(x, "xpsu", np.int64), arr(x, "xllcpwt"))
    terr = x["xstate"].is_in(TERRITORIES).to_numpy()
    bp = x["bphigh"].to_numpy()
    d = np.isin(bp, [1, 2, 3, 4]) & ~terr  # CDC _RFHYPE6: yes = 1; no = 2, 3, 4
    out["bphigh2023"] = three_ses(des, (bp == 1).astype(float), d, lonely="adjust")
    out["bphigh2023"]["jurisdictions"] = int(x.filter(~pl.col("xstate").is_in(TERRITORIES))["xstate"].n_unique())
    return out


# ---------------------------------------------------------------- artifacts
FACTS, FIGS, LEDGERS = {}, {}, {}
W_L, W_P = "WTMEC2YR", "WTMECPRP"


def put_fact(key, value, display, estimand, source, unit=None, se=None, ci=None, ci_display=None,
             df=None, n=None, weight=None, variance="none", benchmark=None, note=""):
    assert key not in FACTS, key
    FACTS[key] = {
        "value": sig(value), "display": display, "unit": unit, "se": sig(se),
        "ci_low": sig(ci[0]) if ci else None, "ci_high": sig(ci[1]) if ci else None,
        "ci_display": ci_display, "df": None if df is None else int(round(df)),
        "n": None if n is None else int(n), "weight": weight, "variance": variance,
        "estimand": estimand, "source": source, "benchmark": benchmark, "note": note,
    }


def fact_prop(key, r, estimand, source, weight, benchmark=None, note="", d=1):
    lo, hi, _ = ci_t(r)
    put_fact(key, r["est"], pct(r["est"], d), estimand, source, unit="percent", se=r["se_d"],
             ci=(lo, hi), ci_display=ci_pct(lo, hi, d), df=r["df"], n=r["n"], weight=weight,
             variance="taylor", benchmark=benchmark, note=note)


def fact_num(key, value, display, estimand, source, unit=None, n=None, weight=None,
             variance="none", note="", benchmark=None, df=None):
    put_fact(key, value, display, estimand, source, unit=unit, n=n, weight=weight,
             variance=variance, note=note, benchmark=benchmark, df=df)


def db(key):
    e, se, ci, n = DB511[key]
    return f"external benchmark: NCHS Data Brief 511 reports {e}% (95% CI {ci}), SE {se}, n = {n:,}"


def db_ci(key):
    lo, hi = DB511[key][2].split("-")
    return float(lo) / 100, float(hi) / 100


def nhanes_artifacts(xL, xP, xJ, desL, L, P, CHG, I):
    ss, ssp = SRC_NHANES_L, SRC_NHANES_P
    adults = "U.S. civilian noninstitutionalized adults 18+ (pregnant women excluded), Aug 2021-Aug 2023"
    hyp = "adults 18+ with hypertension (SBP >= 130 or DBP >= 80 mm Hg, or taking BP medication), Aug 2021-Aug 2023"
    fact_prop("htn_prev", L[("prev", "all")], f"Crude prevalence of hypertension among {adults}", ss, W_L, db("prev_crude"))
    fact_prop("htn_aware", L[("aware", "all")], f"Share told by a health professional they have hypertension, among {hyp}", ss, W_L, db("aware"))
    fact_prop("htn_treat", L[("treat", "all")], f"Share taking prescribed BP medication, among {hyp}", ss, W_L, db("treat"))
    fact_prop("htn_control", L[("control", "all")], f"Share with SBP < 130 and DBP < 80 mm Hg, among {hyp}", ss, W_L, db("control"))
    fact_prop("htn_prev_adj", L["adj_all"], f"Age-adjusted prevalence (2000 standard, 18-39/40-59/60+) among {adults}", ss, W_L, db("prev_adj"))
    for sx in ("men", "women"):
        fact_prop(f"htn_prev_{sx}", L[("prev", sx)], f"Crude hypertension prevalence, {sx} 18+, Aug 2021-Aug 2023", ss, W_L, db(f"prev_{sx}_crude"))
        fact_prop(f"htn_prev_{sx}_adj", L[f"adj_{sx}"], f"Age-adjusted hypertension prevalence, {sx} 18+, Aug 2021-Aug 2023", ss, W_L, db(f"prev_{sx}_adj"))
    for gkey, zc, zadj in [("crude", (L[("prev", "men")], L[("prev", "women")]), None),
                           ("adj", (L["adj_men"], L["adj_women"]), None)]:
        a, b = zc
        v, _ = desL.var(a["z"] - b["z"])
        g = {"est": a["est"] - b["est"], "se_d": v ** 0.5, "df": 15}
        lo, hi, _ = ci_t(g)
        put_fact(f"sex_gap_{gkey}", g["est"], pp(g["est"]),
                 f"Men minus women, {'crude' if gkey == 'crude' else 'age-adjusted'} hypertension prevalence (percentage points), Aug 2021-Aug 2023",
                 ss, unit="percentage points", se=g["se_d"], ci=(lo, hi), ci_display=ci_pp(lo, hi), df=15,
                 n=a["n"] + b["n"], weight=W_L, variance="taylor")
    r = L[("prev", "all")]
    fact_num("htn_n", r["n"], integer(r["n"]), "Examined adults 18+ in the analytic sample (not pregnant, at least one valid BP reading)", ss, n=r["n"], benchmark="NCHS Data Brief 511: n = 6,084")
    unk = int((arr(xL, "analytic", bool) & ~arr(xL, "htn_bp", bool) & ~arr(xL, "med_known", bool)).sum())
    fact_num("htn_unknown_med", unk, str(unk), "Analytic adults with readings below 130/80 and unknown medication status, counted as not hypertensive", ss,
             benchmark="keeping them reproduces the NCHS Data Brief 511 denominator of 6,084")
    fact_num("htn_n_hyp", L[("control", "all")]["n"], integer(L[("control", "all")]["n"]), "Examined adults with hypertension (control denominator)", ss, benchmark="NCHS Data Brief 511: n = 3,242")
    for k, lab in [("naive", "naive iid"), ("w", "weights-only (HC1-type)"), ("d", "full-design Taylor")]:
        fact_num(f"se_prev_{k}", r[f"se_{'naive' if k == 'naive' else k}"] * 100, num(r[f"se_{'naive' if k == 'naive' else k}"] * 100, 2),
                 f"Standard error of crude prevalence, {lab}, percentage points", ss, unit="percentage points", n=r["n"], weight=W_L,
                 variance={"naive": "none", "w": "weights_only_understated", "d": "taylor"}[k])
    for st, key in [("prev", "deff_prev"), ("aware", "deff_aware"), ("treat", "deff_treat"), ("control", "deff_control")]:
        fact_num(key, L[(st, "all")]["deff"], num(L[(st, "all")]["deff"], 2), f"Design effect (Taylor variance / SRS-with-replacement variance), {STAGE_LABEL[st].lower()}, Aug 2021-Aug 2023", ss, n=L[(st, "all")]["n"], weight=W_L, variance="taylor")
    fact_num("deff_prev_1839", L[("prev", "a0")]["deff"], num(L[("prev", "a0")]["deff"], 2), "Design effect, hypertension prevalence among adults 18-39, Aug 2021-Aug 2023", ss, n=L[("prev", "a0")]["n"], weight=W_L, variance="taylor")
    fact_num("deff_prev_pre", P[("prev", "all")]["deff"], num(P[("prev", "all")]["deff"], 2), "Design effect, crude hypertension prevalence, 2017-March 2020", ssp, n=P[("prev", "all")]["n"], weight=W_P, variance="taylor")
    fact_num("wfac_prev", r["wfac"], num(r["wfac"], 2), "Weighting factor: (weights-only SE / naive SE) squared, crude prevalence, Aug 2021-Aug 2023", ss, weight=W_L)
    fact_num("cfac_prev", r["cfac"], num(r["cfac"], 2), "Clustering-and-stratification factor: (design SE / weights-only SE) squared, crude prevalence, Aug 2021-Aug 2023", ss, weight=W_L)
    fact_num("wfac_prev_pre", P[("prev", "all")]["wfac"], num(P[("prev", "all")]["wfac"], 2), "Weighting factor, crude prevalence, 2017-March 2020", ssp, weight=W_P)
    fact_num("neff_prev", r["n"] / r["deff"], integer(r["n"] / r["deff"]), "Design-based effective sample size n / DEFF, crude prevalence", ss, n=r["n"])
    D = L["design"]
    fact_num("nhanes_psu", D["psus"], integer(D["psus"]), "Masked variance PSUs, Aug 2021-Aug 2023 MEC sample", ss)
    fact_num("nhanes_strata", D["strata"], integer(D["strata"]), "Masked variance strata, Aug 2021-Aug 2023 MEC sample", ss)
    fact_num("nhanes_df", D["df"], integer(D["df"]), "Design degrees of freedom (#PSU - #strata), Aug 2021-Aug 2023", ss)
    fact_num("t_crit_df", tcrit(D["df"]), num(tcrit(D["df"]), 2), f"97.5th percentile of t with {D['df']} df", "scipy.stats.t")
    fact_num("t_crit_z", 1.959963985, "1.96", "97.5th percentile of the standard normal", "scipy.stats.norm")
    ratio = tcrit(r["df"]) * r["se_d"] / (1.959963985 * r["se_naive"])
    fact_num("ci_width_ratio", ratio, num(ratio, 1), "Full-design 95% CI width (t, df 15) divided by naive 95% CI width, crude prevalence", ss)
    Dp = P["design"]
    fact_num("pre_df", Dp["df"], integer(Dp["df"]), "Design degrees of freedom, 2017-March 2020 pre-pandemic file", ssp)
    mbar = r["n"] / r["psus"]
    fact_num("moulton_mbar", mbar, integer(mbar), "Average analytic-sample size per PSU (6,084 adults / 30 PSUs)", ss)
    rho = (r["cfac"] - 1) / (mbar - 1)
    fact_num("moulton_rho", rho, num(rho, 3), "Intraclass correlation implied by the observed clustering factor under the equal-cluster Moulton formula 1 + (m - 1) rho", ss,
             note="Back-of-envelope: ignores unequal cluster sizes and the stratification gain folded into the factor")
    for st, key, bkey in [("prev", "pre_prev", None), ("aware", "pre_aware", "pre_aware"), ("treat", "pre_treat", "pre_treat"), ("control", "pre_control", "pre_control")]:
        fact_prop(key, P[(st, "all")], f"{STAGE_LABEL[st]}, {STAGE_DENOM[st]}, 2017-March 2020", ssp, W_P, db(bkey) if bkey else None)
    return ratio


def change_artifacts(CHG):
    ss = f"{SRC_NHANES_L}; {SRC_NHANES_P}"
    wt = "WTMEC2YR (2021-2023) / WTMECPRP (2017-March 2020)"
    for k, col, lab in [("naive", "p_n", "naive iid (normal)"), ("wonly", "p_w", "weights-only"), ("design", "p_d", "full-design Taylor (t, Satterthwaite df)")]:
        c = sum(r[col] < 0.05 for r in CHG)
        fact_num(f"chg_sig_{k}", c, str(c), f"Number of the 24 period comparisons (4 cascade stages x 6 groups) with p < 0.05 under {lab}", ss)
    pick = {("control", "all"): "chg_control", ("control", "men"): "chg_control_men",
            ("prev", "a2"): "chg_prev_60", ("aware", "a0"): "chg_aware_1839"}
    for r in CHG:
        key = pick.get((r["stage"], r["group"]))
        if not key:
            continue
        lo, hi = r["diff"] - r["t_crit"] * r["se_d"], r["diff"] + r["t_crit"] * r["se_d"]
        put_fact(key, r["diff"], pp(r["diff"]),
                 f"Change in {STAGE_LABEL[r['stage']].lower()} ({STAGE_DENOM[r['stage']]}; {r['group_label']}), Aug 2021-Aug 2023 minus 2017-March 2020, percentage points",
                 ss, unit="percentage points", se=r["se_d"], ci=(lo, hi), ci_display=ci_pp(lo, hi), df=r["df"],
                 n=r["n_post"] + r["n_pre"], weight=wt, variance="taylor",
                 note=f"naive p = {r['p_n']:.3f}; design p = {r['p_d']:.3f} (Satterthwaite df {r['df']:.1f})")
        fact_num(f"{key}_p_naive", r["p_n"], num(r["p_n"], 3), f"Two-sided naive p-value for {key}", ss)
        fact_num(f"{key}_p_design", r["p_d"], num(r["p_d"], 3), f"Two-sided full-design p-value for {key}", ss)
    shown = [("all", None), ("men", "control"), ("a2", "prev"), ("a0", "aware")]
    rows = []
    for r in CHG:
        if r["group"] == "all" or any(r["group"] == g and r["stage"] == s for g, s in shown[1:]):
            lab = STAGE_LABEL[r["stage"]] + ("" if r["group"] == "all" else f", {r['group_label'].lower()}")
            z = 1.959963985
            rows.append({"label": lab, "estimate": sig(r["diff"] * 100, 6), "ci_low": sig((r["diff"] - z * r["se_n"]) * 100, 6),
                         "ci_high": sig((r["diff"] + z * r["se_n"]) * 100, 6), "group": "Naive iid interval", "role": "naive"})
            rows.append({"label": lab, "estimate": sig(r["diff"] * 100, 6), "ci_low": sig((r["diff"] - r["t_crit"] * r["se_d"]) * 100, 6),
                         "ci_high": sig((r["diff"] + r["t_crit"] * r["se_d"]) * 100, 6), "group": "Full-design interval", "role": "design"})
    FIGS["change_intervals"] = {
        "type": "dot", "title": "Did the cascade change after the pandemic?",
        "subtitle": "Aug 2021–Aug 2023 minus 2017–March 2020, percentage points, 95% intervals",
        "alt": "Dot plot of period changes in hypertension prevalence, awareness, treatment and control, overall and for the three subgroups that naive intervals flag, each shown with a narrow naive interval and a wider full-design interval; only the full-design intervals for the overall stages and two of the three subgroups cross zero.",
        "rows": rows, "x_label": "Change (percentage points)", "reference": {"value": 0, "label": "No change"},
        "format": "num1", "source": "NHANES 2017–March 2020 and August 2021–August 2023; chapter calculations",
        "note": "Overall stages plus the three subgroup comparisons (of 24) that naive intervals flag. Design intervals use t with Satterthwaite df from 15 and 25."}
    FIGS["change_tests"] = {
        "type": "table", "title": "All 24 period comparisons",
        "alt": "Table of 24 comparisons of hypertension cascade estimates between 2017–March 2020 and August 2021–August 2023 by stage and group, with naive and full-design p-values.",
        "columns": [{"key": "stage", "label": "Stage"}, {"key": "group", "label": "Group"},
                    {"key": "pre", "label": "2017–Mar 2020", "format": "pct1", "align": "right"},
                    {"key": "post", "label": "Aug 2021–Aug 2023", "format": "pct1", "align": "right"},
                    {"key": "change", "label": "Change (pp)", "format": "num1", "align": "right"},
                    {"key": "p_naive", "label": "p, naive", "format": "num3", "align": "right"},
                    {"key": "p_design", "label": "p, full design", "format": "num3", "align": "right"}],
        "rows": [], "highlight_key": "highlight",
        "source": "NHANES; chapter calculations", "note": "Highlighted rows: p < 0.05 under at least one method. No adjustment for multiple comparisons."}
    return FIGS["change_tests"]


def instrument_artifacts(I):
    sj = SRC_NHANES_J
    base = "examined adults 18+ (not pregnant) in 2017-2018 with valid readings from both protocols"
    fact_prop("instr_osc", I["osc"], f"Hypertension (>= 130/80 or medication) using oscillometric readings, {base}", sj, W_L)
    fact_prop("instr_aus", I["aus"], f"Hypertension (>= 130/80 or medication) using auscultatory readings, {base}", sj, W_L)
    t = tcrit(I["df"])
    for key, est, se, lab in [("instr_diff", I["diff"], I["diff_se"], "hypertension (>= 130/80 or medication)"),
                              ("instr_bp_diff", I["bp_diff"], I["bp_diff_se"], "measured BP >= 130/80 alone")]:
        lo, hi = est - t * se, est + t * se
        put_fact(key, est, pp(est), f"Auscultatory minus oscillometric prevalence of {lab}, same participants and weight, percentage points",
                 sj, unit="percentage points", se=se, ci=(lo, hi), ci_display=ci_pp(lo, hi), df=I["df"], n=I["n"], weight=W_L, variance="taylor")
    lo, hi = I["sbp_diff"] - t * I["sbp_diff_se"], I["sbp_diff"] + t * I["sbp_diff_se"]
    put_fact("instr_sbp_diff", I["sbp_diff"], num(I["sbp_diff"], 1), "Mean systolic BP, auscultatory minus oscillometric, same participants (mm Hg)",
             sj, unit="mm Hg", se=I["sbp_diff_se"], ci=(lo, hi), ci_display=f"{num(lo, 1)} to {num(hi, 1)}", df=I["df"], n=I["n"], weight=W_L, variance="taylor")
    fact_num("instr_n", I["n"], integer(I["n"]), f"Analytic sample, {base}", sj, n=I["n"])


def constructs_artifacts(L, nr, br):
    fact_prop("nhanes_selfreport", L["selfreport"], "Share of adults 18+ (not pregnant) ever told by a health professional they had hypertension (self-report, BPQ020), NHANES Aug 2021-Aug 2023 MEC sample", SRC_NHANES_L, W_L)
    fact_prop("nhanes_htn140", L["htn140"], "Hypertension defined as SBP >= 140 or DBP >= 90 or medication (the pre-2017 threshold), adults 18+, Aug 2021-Aug 2023", SRC_NHANES_L, W_L)
    fact_prop("nhis_hyp", nr, "Share of 2023 sample adults ever told they had hypertension (HYPERTENEV)", SRC_NHIS, "SAMPWEIGHT", benchmark="prior in-house verification: 32.26%, DEFF 1.64, df 610")
    b = br["bphigh2023"]
    fact_prop("brfss_bphigh", b, "Share of adults 18+ ever told they have high blood pressure (CDC _RFHYPE6 coding of BPHIGH6: 1 = yes; 2, 3, 4 = no), 48 states and DC, BRFSS 2023", SRC_BRFSS23, "_LLCPWT",
              note="lonely-PSU rule: adjust (centre single-PSU strata at the grand mean); territories excluded as a domain")
    rows = [
        ("BRFSS 2023: told high blood pressure", b, "Self-reported diagnosis", "cat1"),
        ("NHIS 2023: told hypertension", nr, "Self-reported diagnosis", "cat1"),
        ("NHANES 2021–23: told high blood pressure", L["selfreport"], "Self-reported diagnosis", "cat1"),
        ("NHANES 2021–23: measured ≥140/90 or medication", L["htn140"], "Measured", "cat2"),
        ("NHANES 2021–23: measured ≥130/80 or medication", L[("prev", "all")], "Measured", "cat2"),
    ]
    out = []
    for lab, r, grp, role in rows:
        lo, hi, _ = ci_t(r)
        out.append({"label": lab, "estimate": sig(r["est"], 6), "ci_low": sig(lo, 6), "ci_high": sig(hi, 6), "group": grp, "role": role, "n": int(r["n"])})
    FIGS["constructs"] = {
        "type": "dot", "title": "Three surveys, two constructs",
        "subtitle": "Adults 18+, share with high blood pressure, 95% full-design intervals",
        "alt": "Dot plot: three self-reported diagnosis estimates from BRFSS, NHIS and NHANES cluster between about 31 and 34 percent, while NHANES measured hypertension is about 32 percent at the 140/90 threshold and about 48 percent at 130/80.",
        "rows": out, "x_label": "Percent of adults", "format": "pct1", "domain": [0.2, 0.55],
        "source": "CDC BRFSS 2023; IPUMS NHIS 2023; NHANES August 2021–August 2023; chapter calculations",
        "note": "BRFSS 2023 covers 48 states and DC (Kentucky and Pennsylvania did not meet data standards). Calendar periods differ slightly."}


def nhis_artifacts(nr, Dd, Ds, TH):
    s = SRC_NHIS
    fact_num("nhis_n", nr["n"], integer(nr["n"]), "2023 sample adults with a valid hypertension response", s, n=nr["n"])
    fact_num("nhis_strata", nr["strata"], integer(nr["strata"]), "NHIS 2023 variance strata", s)
    fact_num("nhis_psu", nr["psus"], integer(nr["psus"]), "NHIS 2023 PSUs, (STRATA, PSU) composite key", s)
    fact_num("nhis_df", nr["df"], integer(nr["df"]), "NHIS 2023 design df (#PSU - #strata)", s)
    fact_num("nhis_deff", nr["deff"], num(nr["deff"], 2), "Design effect, ever-told hypertension, NHIS 2023 sample adults", s, weight="SAMPWEIGHT", variance="taylor")
    dr = {"est": Dd["est"], "se_d": Dd["se_full"], "df": Dd["df_sub"], "n": Dd["n"]}
    fact_prop("dense_est", dr, "Share who delayed medical care because of cost in the past 12 months, among 2023 sample adults ever told they had hypertension", s, "SAMPWEIGHT",
              note="domain estimated on the full declared design; df counts PSUs and strata containing domain members (NCHS convention)")
    fact_num("dense_n", Dd["n"], integer(Dd["n"]), "Unweighted n, delayed care among adults with hypertension", s, n=Dd["n"])
    gap = 1 - Dd["se_sub"]["certainty"] / Dd["se_full"]
    fact_num("dense_se_gap", gap, pct(gap, 2), "How much smaller the delete-rows-first SE is than the declared-design SE, dense domain", s)
    fact_num("sparse_n", Ds["n"], integer(Ds["n"]), "Unweighted n, uninsured adults in poor health with a valid delayed-care response", s, n=Ds["n"],
             note="Shown only to study its standard error; the proportion itself would fail NCHS presentation standards (effective n below 30)")
    fact_num("sparse_neff", Ds["n"] / Ds["deff"], integer(Ds["n"] / Ds["deff"]), "Effective sample size n / DEFF, sparse domain", s)
    for key, val, lab in [("sparse_se_full", Ds["se_full"], "declared design (all 662 PSUs kept)"),
                          ("sparse_se_sub", Ds["se_sub"]["certainty"], "rows deleted first, single-PSU strata as certainty units"),
                          ("sparse_se_adjust", Ds["se_sub"]["adjust"], "rows deleted first, single-PSU strata centred at the grand mean"),
                          ("sparse_se_average", Ds["se_sub"]["average"], "rows deleted first, single-PSU strata given the average contribution")]:
        fact_num(key, val * 100, num(val * 100, 2), f"SE of the delayed-care proportion in the sparse domain, {lab}, percentage points", s, unit="percentage points", n=Ds["n"], weight="SAMPWEIGHT", variance="taylor")
    short = 1 - Ds["se_sub"]["certainty"] / Ds["se_full"]
    fact_num("sparse_short", short, pct(short, 1), "Shortfall of the delete-rows-first SE (certainty rule) relative to the declared-design SE, proportion", s)
    tshort = 1 - Ds["se_total_sub"]["certainty"] / Ds["se_total_full"]
    fact_num("sparse_total_short", tshort, pct(tshort, 0), "Shortfall of the delete-rows-first SE (certainty rule) for the weighted count of adults who delayed care, sparse domain", s)
    for key, val, lab in [("sparse_psus", Ds["psus"], "PSUs containing sparse-domain members"), ("sparse_strata", Ds["strata"], "strata containing sparse-domain members"),
                          ("sparse_single", Ds["single"], "strata left with a single PSU after deleting rows"), ("sparse_df", Ds["df_sub"], "df after deleting rows (#PSU - #strata among survivors)")]:
        fact_num(key, val, integer(val), f"NHIS 2023 sparse domain: {lab}", s)
    fr = {r["frac"]: r for r in TH}
    t2 = fr[0.002]
    fact_num("thin_n_02", t2["n"], integer(t2["n"]), "Domain size when 0.2% of sample adults are kept", s)
    fact_num("thin_ratio_02", t2["ratio_med"], num(t2["ratio_med"], 2), "Median SE ratio (delete-rows-first / declared design) over 200 random 0.2% domains", s, variance="simulation")
    fact_num("thin_share_02", t2["share_short"], pct(t2["share_short"], 0), "Share of 200 random 0.2% domains whose delete-rows-first SE is more than 10% too small", s, variance="simulation")
    fact_num("thin_single_02", t2["single"], integer(t2["single"]), "Median number of single-PSU strata, 0.2% domains", s, variance="simulation")
    t1 = fr[0.01]
    fact_num("thin_ratio_1", t1["ratio_med"], num(t1["ratio_med"], 3), "Median SE ratio over 200 random 1% domains", s, variance="simulation")
    FIGS["thinning"] = {
        "type": "table", "title": "Thinning one domain: the understatement grows as strata collapse",
        "alt": "Table: as a random domain of NHIS 2023 sample adults shrinks from 100% to 0.2% of the sample, PSUs with members fall from 662 to about 56, single-PSU strata rise from 0 to about 19, and the median ratio of the delete-rows-first SE to the correct SE falls from 1.00 to about 0.81.",
        "columns": [{"key": "kept", "label": "Share of adults kept", "format": "pct1", "align": "right"},
                    {"key": "n", "label": "n", "format": "int", "align": "right"},
                    {"key": "psus", "label": "PSUs with members", "format": "int", "align": "right"},
                    {"key": "single", "label": "Single-PSU strata", "format": "int", "align": "right"},
                    {"key": "df", "label": "df after deletion", "format": "int", "align": "right"},
                    {"key": "ratio_med", "label": "SE ratio, median", "format": "num3", "align": "right"},
                    {"key": "ratio_p10", "label": "10th pct", "format": "num3", "align": "right"},
                    {"key": "share_short", "label": "Draws >10% too small", "format": "pct0", "align": "right"}],
        "rows": [{"kept": r["frac"], "n": r["n"], "psus": sig(r["psus"], 6), "single": sig(r["single"], 6), "df": sig(r["df"], 6),
                  "ratio_med": sig(r["ratio_med"], 6), "ratio_p10": sig(r["ratio_p10"], 6), "share_short": sig(r["share_short"], 6),
                  "highlight": r["share_short"] > 0.5} for r in TH],
        "highlight_key": "highlight",
        "source": "IPUMS NHIS 2023 sample adults; outcome: ever told hypertension; chapter calculations",
        "note": f"Each row below 100% summarizes {THIN_DRAWS} seeded random domains of fixed size (seed {SEED}). SE ratio = SE after deleting non-domain rows (single-PSU strata as certainty units) / SE from the declared design. Medians shown."}
    rows = [{"approach": "Declare the design, then estimate the domain", "lone": "not applicable: all 662 PSUs kept", "se": Ds["se_full"] * 100, "ratio": 1.0,
             "se_tot": Ds["se_total_full"], "ratio_tot": 1.0, "highlight": True}]
    for rule, lab, lone in [("certainty", "Delete rows first; certainty or remove", "contributes zero"),
                            ("adjust", "Delete rows first; adjust", "deviation from the grand mean"),
                            ("average", "Delete rows first; average", "average of the other strata")]:
        rows.append({"approach": lab, "lone": lone, "se": Ds["se_sub"][rule] * 100, "ratio": Ds["se_sub"][rule] / Ds["se_full"],
                     "se_tot": Ds["se_total_sub"][rule], "ratio_tot": Ds["se_total_sub"][rule] / Ds["se_total_full"], "highlight": False})
    FIGS["lonely_rules"] = {
        "type": "table", "title": "One sparse domain, four answers",
        "alt": "Table comparing standard errors for delayed care among uninsured adults in poor health: the declared-design SE versus three delete-rows-first SEs under certainty, adjust and average lonely-PSU rules, for the proportion and for the weighted count.",
        "columns": [{"key": "approach", "label": "Approach"}, {"key": "lone", "label": "A single-PSU stratum"},
                    {"key": "se", "label": "SE, proportion (pp)", "format": "num2", "align": "right"},
                    {"key": "ratio", "label": "Ratio", "format": "ratio2", "align": "right"},
                    {"key": "se_tot", "label": "SE, weighted count", "format": "int", "align": "right"},
                    {"key": "ratio_tot", "label": "Ratio", "format": "ratio2", "align": "right"}],
        "rows": [{k: (sig(v, 8) if isinstance(v, float) else v) for k, v in r.items()} for r in rows],
        "highlight_key": "highlight",
        "source": "IPUMS NHIS 2023 sample adults; chapter calculations; checked against svy 0.28 and R survey 4.5",
        "note": f"Domain: uninsured sample adults in poor self-rated health with a valid delayed-care response (n = {Ds['n']}). After deleting rows, {Ds['single']} of {Ds['strata']} surviving strata have one PSU. R's default rule (fail) and svy's default both refuse to compute."}


def group_artifacts(nu, GC, means):
    """Facts, figure and ledger for the NHIS 2023 group-contrast family (uninsured, adults 18-64)."""
    s = SRC_NHIS
    pop = "sample adults 18-64 with a known coverage status, NHIS 2023"
    fact_prop("nhis_unins_wa", nu, f"Share without health insurance coverage at interview (HINOTCOVE), {pop}", s, "SAMPWEIGHT",
              note="domain of the full 2023 sample-adult design; df counts PSUs and strata with domain members")
    fact_num("grp_k", len(GC), str(len(GC)), "Number of pre-specified pairwise group comparisons of the uninsured share among adults 18-64 "
             "(region 6, race/Hispanic origin 10, education 6, citizenship 1, sex 1, age group 3)", s)
    for k, col, lab in [("naive", "p_n", "naive iid (independent simple random samples)"), ("wonly", "p_w", "weights-only"),
                        ("design", "p_d", "full-design Taylor with the covariance (t, domain df)")]:
        c = sum(r[col] < 0.05 for r in GC)
        fact_num(f"grp_sig_{k}", c, str(c), f"Number of the {len(GC)} group comparisons with p < 0.05 under {lab}", s)
    flips = [r for r in GC if (r["p_n"] < 0.05) != (r["p_d"] < 0.05)]
    fact_num("grp_flips", len(flips), str(len(flips)), f"Number of the {len(GC)} group comparisons whose 5 percent verdict differs between the naive and the full-design test", s)
    ne_mw = next(r for r in GC if r["dim"] == GEO_DIM and r["a"] == "Northeast" and r["b"] == "Midwest")
    assert (ne_mw["p_n"] < 0.05) and (ne_mw["p_d"] >= 0.05), "the Northeast-Midwest example no longer flips; revise the prose"
    lo, hi = ne_mw["diff"] - ne_mw["t_crit"] * ne_mw["se_d"], ne_mw["diff"] + ne_mw["t_crit"] * ne_mw["se_d"]
    put_fact("grp_ne_mw", ne_mw["diff"], pp(ne_mw["diff"]), "Uninsured share, Northeast minus Midwest, adults 18-64, NHIS 2023 (percentage points)",
             s, unit="percentage points", se=ne_mw["se_d"], ci=(lo, hi), ci_display=ci_pp(lo, hi), df=ne_mw["df"],
             n=ne_mw["n_a"] + ne_mw["n_b"], weight="SAMPWEIGHT", variance="taylor",
             note=f"naive p = {ne_mw['p_n']:.3f}; weights-only p = {ne_mw['p_w']:.3f}; design p = {ne_mw['p_d']:.3f}")
    for k, col in [("p_naive", "p_n"), ("p_wonly", "p_w"), ("p_design", "p_d")]:
        fact_num(f"grp_ne_mw_{k}", ne_mw[col], num(ne_mw[col], 3), f"Two-sided {k.replace('p_', '')} p-value, Northeast minus Midwest uninsured share", s)
    for k, col, lab, var in [("se_naive", "se_n", "naive iid", "none"), ("se_wonly", "se_w", "weights-only", "weights_only_understated"),
                             ("se_design", "se_d", "full design", "taylor")]:
        fact_num(f"grp_ne_mw_{k}", ne_mw[col] * 100, num(ne_mw[col] * 100, 2), f"Standard error of the Northeast minus Midwest difference, {lab}, percentage points",
                 s, unit="percentage points", weight="SAMPWEIGHT", variance=var)
    reg = means[GEO_DIM]
    for code, key in [("1", "ne"), ("2", "mw")]:
        r = reg[code]
        fact_num(f"grp_{key}_rate", r["est"], pct(r["est"]), f"Uninsured share, {r['label']}, adults 18-64, NHIS 2023", s, n=r["n"],
                 weight="SAMPWEIGHT", variance="taylor")
    geo = [r["se_d"] / r["se_n"] for r in GC if r["dim"] == GEO_DIM]
    dem = [r["se_d"] / r["se_n"] for r in GC if r["dim"] != GEO_DIM]
    fact_num("grp_geo_ratio", float(np.median(geo)), num(float(np.median(geo)), 2), "Median ratio of the full-design to the naive SE of the difference over the 6 region comparisons", s)
    fact_num("grp_demo_ratio", float(np.median(dem)), num(float(np.median(dem)), 2), "Median ratio of the full-design to the naive SE of the difference over the 21 non-geographic comparisons", s)
    assert float(np.median(geo)) > float(np.median(dem)), "prose: region comparisons inflate more than the others"
    cov = [(r["se_d"] / r["se_ind"], r) for r in GC]
    cmin = min(cov, key=lambda t: t[0])
    # The prose names this pair; fail rather than drift if the data change.
    assert cmin[1]["dim"] == "female" and {cmin[1]["a"], cmin[1]["b"]} == {"Men", "Women"}, (cmin[1]["a"], cmin[1]["b"])
    fact_num("grp_cov_min", cmin[0], num(cmin[0], 2), f"Smallest ratio of the design SE with the covariance to the design SE assuming the two domains independent, over the {len(GC)} comparisons ({cmin[1]['a']} vs {cmin[1]['b']})", s)
    geo_cov = [r["se_d"] / r["se_ind"] for r in GC if r["dim"] == GEO_DIM]
    fact_num("grp_geo_cov", float(np.median(geo_cov)), num(float(np.median(geo_cov)), 2), "Median covariance ratio (design SE with covariance / design SE assuming independence) over the 6 region comparisons", s)
    FIGS["group_contrasts"] = {
        "type": "table", "title": "One sample, 27 group comparisons of the uninsured share",
        "alt": (f"Table of {len(GC)} pairwise comparisons of the uninsured share among adults 18 to 64 in NHIS 2023 across region, race and Hispanic origin, "
                "education, citizenship, sex, and age group, with naive and full-design p-values; the region comparisons show the largest inflation "
                "of the standard error and the Northeast-Midwest comparison changes verdict."),
        "columns": [{"key": "dim", "label": "Dimension"}, {"key": "a", "label": "Group A"}, {"key": "b", "label": "Group B"},
                    {"key": "est_a", "label": "A", "format": "pct1", "align": "right"},
                    {"key": "est_b", "label": "B", "format": "pct1", "align": "right"},
                    {"key": "diff", "label": "A − B (pp)", "format": "num1", "align": "right"},
                    {"key": "se_ratio", "label": "SE ratio, design ÷ naive", "format": "ratio2", "align": "right"},
                    {"key": "cov_ratio", "label": "Covariance ratio", "format": "ratio2", "align": "right"},
                    {"key": "p_naive", "label": "p, naive", "format": "num3", "align": "right"},
                    {"key": "p_design", "label": "p, full design", "format": "num3", "align": "right"}],
        "rows": [{"dim": r["dim_label"], "a": r["a"], "b": r["b"], "est_a": sig(r["est_a"], 6), "est_b": sig(r["est_b"], 6),
                  "diff": sig(r["diff"] * 100, 6), "se_ratio": sig(r["se_d"] / r["se_n"], 6), "cov_ratio": sig(r["se_d"] / r["se_ind"], 6),
                  "p_naive": sig(r["p_n"], 6), "p_design": sig(r["p_d"], 6),
                  "highlight": bool((r["p_n"] < 0.05) != (r["p_d"] < 0.05))} for r in GC],
        "highlight_key": "highlight",
        "source": "IPUMS NHIS 2023 sample adults 18–64; chapter calculations",
        "note": ("Uninsured at interview (HINOTCOVE). Naive: independent simple random samples, normal reference. Full design: Taylor variance of the "
                 "difference on the declared (STRATA, PSU) design, covariance included, t reference with the df of PSUs and strata containing either "
                 "group. Covariance ratio = design SE of the difference ÷ the design SE that treats the two groups as independent. "
                 "Highlighted rows change verdict at the 5 percent level. No adjustment for multiple comparisons.")}
    LEDGERS["nhis_groups"] = {
        "title": "Which groups of adults differ in coverage? (NHIS 2023)",
        "target_population": "U.S. civilian noninstitutionalized adults 18–64 in 2023, by Census region, race and Hispanic origin, education, citizenship, sex, and age group",
        "estimand": "Differences between pairs of groups in the finite-population share without health insurance at interview; 27 pre-specified comparisons",
        "estimator": "Difference of two weighted ratio (Hájek) means, each a domain of the full sample-adult design",
        "explicit_weights": "SAMPWEIGHT, the sample-adult weight",
        "implicit_weights": "None",
        "randomness": "One stratified multistage sample; both groups in every comparison come from the same PSUs, so their estimates covary",
        "variance_estimator": "Taylor linearization of the difference on the declared design, (STRATA, PSU) composite key, covariance included; t with the df of PSUs and strata containing either group; compared with naive iid and weights-only variances",
        "assumptions": "With-replacement PSU approximation; item nonresponse on coverage excluded; no multiplicity adjustment; descriptive contrasts, not effects",
        "facts": ["ch3.nhis_unins_wa", "ch3.grp_k", "ch3.grp_sig_naive", "ch3.grp_sig_design", "ch3.grp_ne_mw"],
    }
    return ne_mw


def contrast_artifacts(L, nr, br):
    y = br["y2024"]
    s = SRC_BRFSS24
    fact_num("brfss_n", y["n_file"], integer(y["n_file"]), "Respondents in the BRFSS 2024 public file", s)
    fact_num("brfss_strata", y["strata_full"], integer(y["strata_full"]), "BRFSS 2024 strata (_STSTR)", s)
    fact_num("brfss_psu", y["psus_full"], integer(y["psus_full"]), "BRFSS 2024 PSUs, (_STSTR, _PSU) composite key; one respondent per PSU", s)
    fact_num("brfss_df", y["df_full"], integer(y["df_full"]), "BRFSS 2024 design df (#PSU - #strata)", s)
    fact_num("brfss_single", y["single_full"], integer(y["single_full"]), "BRFSS 2024 strata containing a single respondent", s)
    fact_num("brfss_cv", y["cv_w"], num(y["cv_w"], 2), "Coefficient of variation of _LLCPWT among respondents with a valid general-health answer, BRFSS 2024", s)
    fact_num("brfss_deff", y["deff"], num(y["deff"], 2), "Design effect, fair or poor self-rated health, BRFSS 2024", s, weight="_LLCPWT", variance="taylor")
    fact_num("brfss_wfac", y["wfac"], num(y["wfac"], 2), "Weighting factor, fair or poor health, BRFSS 2024", s)
    fact_num("brfss_cfac", y["cfac"], num(y["cfac"], 2), "Clustering-and-stratification factor, fair or poor health, BRFSS 2024", s)
    fact_prop("brfss_fp", y, "Share of adults reporting fair or poor general health (CDC _RFHLTH), BRFSS 2024 participating jurisdictions", s, "_LLCPWT",
              note="lonely-PSU rule: adjust; 110 single-respondent strata in the full design")
    rN = L[("prev", "all")]
    D = L["design"]
    rows = [
        {"survey": "NHANES Aug 2021–Aug 2023", "estimand": "Hypertension, measured or medicated", "n": rN["n"], "strata": D["strata"], "psus": D["psus"],
         "df": D["df"], "t": tcrit(D["df"]), "kish": rN["kish"], "wfac": rN["wfac"], "cfac": rN["cfac"], "deff": rN["deff"]},
        {"survey": "NHIS 2023 sample adults", "estimand": "Ever told hypertension", "n": nr["n"], "strata": nr["strata"], "psus": nr["psus"],
         "df": nr["df"], "t": tcrit(nr["df"]), "kish": nr["kish"], "wfac": nr["wfac"], "cfac": nr["cfac"], "deff": nr["deff"]},
        {"survey": "BRFSS 2024", "estimand": "Fair or poor general health", "n": y["n"], "strata": y["strata_full"], "psus": y["psus_full"],
         "df": y["df_full"], "t": tcrit(y["df_full"]), "kish": y["kish"], "wfac": y["wfac"], "cfac": y["cfac"], "deff": y["deff"]},
    ]
    FIGS["df_contrast"] = {
        "type": "table", "title": "Complex surveys, opposite sources of uncertainty",
        "alt": "Table comparing NHANES, NHIS and BRFSS: NHANES has 30 PSUs and 15 design degrees of freedom and its design effect comes mostly from clustering; BRFSS has one respondent per PSU and about 455,000 degrees of freedom and its design effect comes almost entirely from unequal weights.",
        "columns": [{"key": "survey", "label": "Survey"}, {"key": "estimand", "label": "Example estimand"},
                    {"key": "n", "label": "Analytic n", "format": "int", "align": "right"},
                    {"key": "strata", "label": "Strata", "format": "int", "align": "right"},
                    {"key": "psus", "label": "PSUs", "format": "int", "align": "right"},
                    {"key": "df", "label": "Design df", "format": "int", "align": "right"},
                    {"key": "t", "label": "t(0.975)", "format": "num2", "align": "right"},
                    {"key": "kish", "label": "1 + CV(w)²", "format": "ratio2", "align": "right"},
                    {"key": "wfac", "label": "Weighting factor", "format": "ratio2", "align": "right"},
                    {"key": "cfac", "label": "Clustering × strata factor", "format": "ratio2", "align": "right"},
                    {"key": "deff", "label": "DEFF", "format": "ratio2", "align": "right"}],
        "rows": [{k: (sig(v, 8) if isinstance(v, float) else v) for k, v in r.items()} for r in rows],
        "source": "NHANES August 2021–August 2023; IPUMS NHIS 2023; CDC BRFSS 2024; chapter calculations",
        "note": "DEFF = weighting factor × clustering-and-stratification factor, by construction: (weights-only SE / naive SE)² × (design SE / weights-only SE)². BRFSS 2024 omits Tennessee; its Taylor SE uses the adjust rule for 110 single-respondent strata."}


def nhanes_figures(L, P):
    rows = []
    for st, bkey in [("prev", "prev_crude"), ("aware", "aware"), ("treat", "treat"), ("control", "control")]:
        r = L[(st, "all")]
        lo, hi, _ = ci_t(r)
        lab = STAGE_LABEL[st] + (" (all adults)" if st == "prev" else " (with hypertension)")
        rows.append({"label": lab, "estimate": sig(r["est"], 6), "ci_low": sig(lo, 6), "ci_high": sig(hi, 6),
                     "group": "This chapter (Taylor, df 15)", "role": "design", "n": r["n"]})
        blo, bhi = db_ci(bkey)
        rows.append({"label": lab, "estimate": sig(DB511[bkey][0] / 100, 6), "ci_low": sig(blo, 6), "ci_high": sig(bhi, 6),
                     "group": "NCHS Data Brief 511 (published)", "role": "benchmark", "n": DB511[bkey][3]})
    FIGS["cascade"] = {
        "type": "dot", "title": "The hypertension cascade, August 2021–August 2023",
        "subtitle": "Adults 18+; awareness, treatment and control are shares of adults with hypertension; 95% intervals",
        "alt": "Dot plot of hypertension prevalence (about 48 percent of adults) and, among adults with hypertension, awareness (about 59 percent), treatment (about 51 percent) and control (about 21 percent), each estimated in this chapter and matching the published NCHS values within 0.1 percentage point.",
        "rows": rows, "x_label": "Percent", "format": "pct1", "domain": [0, 0.8],
        "source": "NHANES August 2021–August 2023; NCHS Data Brief 511; chapter calculations",
        "note": "Chapter intervals: estimate ± t(15)·SE. NCHS publishes Korn–Graubard intervals, so endpoints can differ in the last digit."}
    rows = []
    for lab, r in [("Hypertension, crude", L[("prev", "all")]), ("Hypertension, age-adjusted", L["adj_all"]),
                   ("Awareness", L[("aware", "all")]), ("Treatment", L[("treat", "all")]), ("Control", L[("control", "all")])]:
        rows.append({"estimand": lab, "est": sig(r["est"], 6), "n": r["n"], "se_naive": sig(r["se_naive"] * 100, 6),
                     "se_w": sig(r["se_w"] * 100, 6), "se_d": sig(r["se_d"] * 100, 6), "deff": sig(r["deff"], 6), "df": r["df"]})
    FIGS["three_ses"] = {
        "type": "table", "title": "One estimate, three standard errors",
        "alt": "Table of five hypertension estimates for August 2021–August 2023 with their naive, weights-only and full-design standard errors, design effects between about 1.7 and 3.1, and 15 design degrees of freedom.",
        "columns": [{"key": "estimand", "label": "Estimate"}, {"key": "est", "label": "Value", "format": "pct1", "align": "right"},
                    {"key": "n", "label": "n", "format": "int", "align": "right"},
                    {"key": "se_naive", "label": "SE, naive (pp)", "format": "num2", "align": "right"},
                    {"key": "se_w", "label": "SE, weights only (pp)", "format": "num2", "align": "right"},
                    {"key": "se_d", "label": "SE, full design (pp)", "format": "num2", "align": "right"},
                    {"key": "deff", "label": "DEFF", "format": "ratio2", "align": "right"},
                    {"key": "df", "label": "Design df", "format": "int", "align": "right"}],
        "rows": rows, "source": "NHANES August 2021–August 2023; chapter calculations",
        "note": "Naive: √(p(1−p)/(n−1)), ignoring weights and design. Weights only: every respondent its own PSU, no strata (the HC1 sandwich for a weighted mean). Full design: Taylor linearization with SDMVSTRA and SDMVPSU. DEFF = (full-design SE / naive SE)²."}
    rows = []
    for per, R, role in [("Aug 2021–Aug 2023", L, "cat1"), ("2017–Mar 2020", P, "cat2")]:
        for lab, k in [("Prevalence", ("prev", "all")), ("Awareness", ("aware", "all")), ("Treatment", ("treat", "all")),
                       ("Control", ("control", "all")), ("Prevalence, ages 18–39", ("prev", "a0"))]:
            rows.append({"label": lab, "estimate": sig(R[k]["deff"], 6), "group": per, "role": role, "n": R[k]["n"]})
    FIGS["deff_by_estimand"] = {
        "type": "dot", "title": "There is no single NHANES design effect",
        "subtitle": "Design effect by estimand and survey period",
        "alt": "Dot plot of design effects for hypertension prevalence, awareness, treatment, control and prevalence among adults 18 to 39, ranging from about 1.6 to 5.3 and differing between the 2017–March 2020 and August 2021–August 2023 samples.",
        "rows": rows, "x_label": "Design effect (variance ÷ simple-random-sample variance)",
        "reference": {"value": 1, "label": "Simple random sample"}, "format": "num2",
        "source": "NHANES 2017–March 2020 and August 2021–August 2023; chapter calculations",
        "note": "Subgroup pre-specified before estimation. The 2017–March 2020 sample oversampled by race, Hispanic origin and income; the August 2021–August 2023 sample did not."}
    rows = []
    for lab, rc, ra, grp in [("All adults", L[("prev", "all")], L["adj_all"], "Aug 2021–Aug 2023"),
                             ("Men", L[("prev", "men")], L["adj_men"], "Aug 2021–Aug 2023"),
                             ("Women", L[("prev", "women")], L["adj_women"], "Aug 2021–Aug 2023"),
                             ("All adults", P[("prev", "all")], P["adj_all"], "2017–Mar 2020")]:
        for kind, r, role in [("crude", rc, "cat1"), ("age-adjusted", ra, "cat2")]:
            lo, hi, _ = ci_t(r)
            rows.append({"label": f"{lab}, {kind}", "estimate": sig(r["est"], 6), "ci_low": sig(lo, 6), "ci_high": sig(hi, 6),
                         "group": grp, "role": role, "n": r["n"]})
    FIGS["crude_vs_adjusted"] = {
        "type": "dot", "title": "Survey weights and standardization weights answer different questions",
        "subtitle": "Hypertension prevalence, crude and age-adjusted to the 2000 U.S. standard population, 95% intervals",
        "alt": "Dot plot: age-adjusted prevalence is about 3 points below crude prevalence for all adults, and the gap between men and women is wider after age adjustment (about 49 versus 40 percent) than before (about 51 versus 45 percent).",
        "rows": rows, "x_label": "Percent of adults", "format": "pct1", "domain": [0.3, 0.6],
        "source": "NHANES; 2000 U.S. standard population (Census P25-1130); chapter calculations",
        "note": "Standardization weights s_a = 0.4203 (18–39), 0.3572 (40–59), 0.2225 (60+)."}


def make_ledgers():
    LEDGERS["nhanes_cascade"] = {
        "title": "How many adults have hypertension, know it, treat it, and control it? (NHANES August 2021–August 2023)",
        "target_population": "U.S. civilian noninstitutionalized adults 18 and older, excluding pregnant women, August 2021–August 2023",
        "estimand": "Finite-population proportions: hypertension among adults; awareness, treatment and control among adults with hypertension (NCHS Data Brief 511 definitions). Also the prevalence directly standardized to the 2000 U.S. population",
        "estimator": "Weighted ratio (Hájek) means over domains of the declared design; age-adjusted prevalence = Σ_a s_a p̂_a over 18–39, 40–59, 60+",
        "explicit_weights": "WTMEC2YR, the examination weight: base weights for unequal selection probabilities with nonresponse and calibration adjustments. s_a = 2000 standard-population shares (0.4203, 0.3572, 0.2225) in the age-adjusted estimate",
        "implicit_weights": "None beyond the explicit weights; every estimate is a weighted mean of a 0/1 indicator",
        "randomness": "Selection of PSUs and of people within PSUs in a stratified multistage sample; nonresponse treated as handled by the weight adjustments",
        "variance_estimator": "Taylor linearization with 15 masked strata and 30 PSUs (with-replacement approximation); design df 15; 95% intervals estimate ± t(15)·SE",
        "assumptions": "Weights correct for differential nonresponse; the oscillometric protocol measures blood pressure comparably across participants; medication use is self-reported; averaging up to three readings defines the participant's blood pressure",
        "facts": ["ch3.htn_prev", "ch3.htn_aware", "ch3.htn_treat", "ch3.htn_control", "ch3.htn_prev_adj"],
    }
    LEDGERS["period_change"] = {
        "title": "Did awareness, treatment, or control change after the pandemic?",
        "target_population": "U.S. civilian noninstitutionalized adults 18+ with hypertension (pregnant women excluded) in 2017–March 2020 and in August 2021–August 2023",
        "estimand": "Differences between the two periods in finite-population proportions, overall and in five pre-specified groups (24 comparisons)",
        "estimator": "Difference of two independent weighted ratio means",
        "explicit_weights": "WTMECPRP (2017–March 2020 pre-pandemic file) and WTMEC2YR (August 2021–August 2023)",
        "implicit_weights": "None",
        "randomness": "Two independent stratified multistage samples",
        "variance_estimator": "Sum of the two Taylor variances (15 and 25 df), t with Satterthwaite df; compared with naive iid and weights-only variances",
        "assumptions": "Comparable definitions and instruments (oscillometric in both periods; medication question changed wording and skip pattern in 2021–2023); no adjustment for multiple comparisons, as in NCHS reports",
        "facts": ["ch3.chg_control", "ch3.pre_aware", "ch3.pre_treat", "ch3.pre_control", "ch3.chg_sig_naive", "ch3.chg_sig_design"],
    }
    LEDGERS["nhis_domain"] = {
        "title": "A sparse domain, estimated two ways (NHIS 2023)",
        "target_population": "U.S. civilian noninstitutionalized adults 18+ without health insurance and in poor self-rated health, 2023",
        "estimand": "Share (and number) who delayed medical care because of cost in the past 12 months",
        "estimator": "Weighted ratio mean and weighted total within the domain",
        "explicit_weights": "SAMPWEIGHT, the sample-adult weight",
        "implicit_weights": "None",
        "randomness": "Selection of PSUs within 52 strata and of households and adults within PSUs; domain membership is itself random",
        "variance_estimator": "Taylor linearization on the full declared design, (STRATA, PSU) composite key (662 PSUs); contrasted with deleting non-domain rows first under certainty, adjust, and average lonely-PSU rules",
        "assumptions": "With-replacement PSU approximation; the domain proportion is shown only to study its standard error (effective n below 30 fails NCHS presentation standards)",
        "facts": ["ch3.sparse_se_full", "ch3.sparse_se_sub", "ch3.sparse_short", "ch3.sparse_total_short"],
    }


def read_r():
    p = SCR / "verify_R_results.csv"
    if not p.exists():
        return {}
    with open(p, newline="", encoding="utf-8") as f:
        return {row["check"]: row["value"] for row in csv.DictReader(f)}


def validation_block(L, P, nr, Ds, br, svy_rows, nu=None, GC=None):
    V = []
    for row in svy_rows:
        V.append({"kind": "svy 0.28 dual path", **{k: (sig(v) if isinstance(v, float) else v) for k, v in row.items()}})
    pairs = [("prev_crude", L[("prev", "all")]), ("prev_adj", L["adj_all"]), ("prev_men_crude", L[("prev", "men")]),
             ("prev_women_crude", L[("prev", "women")]), ("prev_men_adj", L["adj_men"]), ("prev_women_adj", L["adj_women"]),
             ("prev_18_39", L[("prev", "a0")]), ("prev_40_59", L[("prev", "a1")]), ("prev_60p", L[("prev", "a2")]),
             ("aware", L[("aware", "all")]), ("treat", L[("treat", "all")]), ("control", L[("control", "all")]),
             ("pre_aware", P[("aware", "all")]), ("pre_treat", P[("treat", "all")]), ("pre_control", P[("control", "all")])]
    for key, r in pairs:
        e, se, ci, n = DB511[key]
        V.append({"kind": "external benchmark: NCHS Data Brief 511", "quantity": key, "published_pct": e, "published_se": se,
                  "published_n": n, "ours_pct": round(r["est"] * 100, 3), "ours_se": round(r["se_d"] * 100, 3), "ours_n": r["n"],
                  "diff_pp": round(r["est"] * 100 - e, 3), "match_at_published_rounding": bool(round(r["est"] * 100, 1) == e and r["n"] == n)})
    R = read_r()
    if not R:
        V.append({"kind": "R survey 4.5", "status": "pending: run verify.R, then build.py again"})
        return V
    y = br["y2024"]
    comp = [("nhanes_prev_n", L[("prev", "all")]["n"]), ("nhanes_prev_est", L[("prev", "all")]["est"]),
            ("nhanes_prev_se", L[("prev", "all")]["se_d"]), ("nhanes_prev_deff", L[("prev", "all")]["deff"]),
            ("nhanes_prev_df", L[("prev", "all")]["df"]), ("nhanes_prev_adj_est", L["adj_all"]["est"]),
            ("nhanes_prev_adj_se", L["adj_all"]["se_d"]), ("nhanes_aware_est", L[("aware", "all")]["est"]),
            ("nhanes_aware_se", L[("aware", "all")]["se_d"]), ("nhanes_aware_deff", L[("aware", "all")]["deff"]),
            ("nhis_hyp_est", nr["est"]), ("nhis_hyp_se", nr["se_d"]), ("nhis_hyp_deff", nr["deff"]), ("nhis_df", nr["df"]),
            ("nhis_sparse_n", Ds["n"]), ("nhis_sparse_se", Ds["se_full"]), ("nhis_sparse_total_se", Ds["se_total_full"]),
            ("nhis_sparse_df", Ds["df_sub"])]
    for rule in ("certainty", "adjust", "average"):
        comp += [(f"nhis_subset_{rule}_se", Ds["se_sub"][rule]), (f"nhis_subset_{rule}_total_se", Ds["se_total_sub"][rule])]
    comp += [("nhis_subset_remove_se", Ds["se_sub"]["certainty"]), ("nhis_subset_remove_total_se", Ds["se_total_sub"]["certainty"]),
             ("brfss_fp_est", y["est"]), ("brfss_fp_se", y["se_d"]), ("brfss_fp_deff", y["deff"]), ("brfss_df", y["df_full"])]
    if nu is not None and GC is not None:
        ne_mw = next(r for r in GC if r["dim"] == GEO_DIM and r["a"] == "Northeast" and r["b"] == "Midwest")
        sex = next(r for r in GC if r["dim"] == "female" and r["a"] == "Men" and r["b"] == "Women")
        comp += [("nhis_unins_wa_est", nu["est"]), ("nhis_unins_wa_se", nu["se_d"]),
                 ("nhis_ne_mw_diff", ne_mw["diff"]), ("nhis_ne_mw_se", ne_mw["se_d"]), ("nhis_ne_mw_df", ne_mw["df"]),
                 ("nhis_sex_diff", sex["diff"]), ("nhis_sex_se", sex["se_d"])]
    for k, mine in comp:
        if k not in R:
            V.append({"kind": "R survey 4.5", "quantity": k, "status": "missing from verify_R_results.csv"})
            continue
        rv = float(R[k])
        diff = abs(rv - float(mine))
        rel = diff / abs(rv) if rv else diff
        V.append({"kind": "R survey 4.5", "quantity": k, "python": sig(mine), "r": sig(rv), "abs_diff": sig(diff),
                  "rel_diff": sig(rel), "pass": bool(rel < 1e-6)})
    for k in ("nhis_subset_fail", "brfss_fail"):
        V.append({"kind": "R survey 4.5", "quantity": f"{k} (survey.lonely.psu = 'fail')",
                  "r_errors": R.get(f"{k}_errors") == "1", "r_message": R.get(f"{k}_message", ""),
                  "python_raises": bool(Ds["fail_raises"] if k.startswith("nhis") else y["fail_raises"])})
    V.append({"kind": "R survey 4.5", "quantity": "versions", "r": R.get("r_version", ""), "survey": R.get("survey_version", "")})
    return V


def dump(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, sort_keys=True, indent=2, ensure_ascii=False)
        f.write("\n")


def main():
    import scipy
    import svy
    ART.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    for p in FIG.glob("*.json"):
        p.unlink()
    d = load_nhanes()
    xL, xP, xJ = derive_nhanes(d, 2021), derive_nhanes(d, 2019), derive_nhanes(d, 2017)
    desL, L = cascade(xL)
    _, P = cascade(xP)
    CHG = period_changes(L, P)
    I = instrument(xJ)
    svy_rows = svy_check_nhanes(xL, L)
    nhanes_artifacts(xL, xP, xJ, desL, L, P, CHG, I)
    fact_prop("pre_prev_adj", P["adj_all"], "Age-adjusted hypertension prevalence, adults 18+, 2017-March 2020", SRC_NHANES_P, W_P)
    tab = change_artifacts(CHG)
    tab["rows"] = [{"stage": STAGE_LABEL[r["stage"]], "group": r["group_label"], "pre": sig(P[(r["stage"], r["group"])]["est"], 6),
                    "post": sig(L[(r["stage"], r["group"])]["est"], 6), "change": sig(r["diff"] * 100, 6),
                    "p_naive": sig(r["p_n"], 6), "p_design": sig(r["p_d"], 6),
                    "highlight": bool(r["p_n"] < 0.05 or r["p_d"] < 0.05)} for r in CHG]
    instrument_artifacts(I)
    nhanes_figures(L, P)

    ad = load_nhis()
    desN = nhis_design(ad)
    hyp = ad["hyp"]
    nr = three_ses(desN, np.nan_to_num(hyp.to_numpy()), hyp.is_not_null().to_numpy())
    delay = ad["delay"].to_numpy()
    dense = ((ad["hyp"] == 1).fill_null(False) & ad["delay"].is_not_null()).to_numpy()
    sparse = (ad["unins"] & ad["poor"] & ad["delay"].is_not_null()).to_numpy()
    Dd = domain_compare(desN, delay, dense)
    Ds = domain_compare(desN, delay, sparse)
    svy_rows += svy_check_nhis(ad, Ds)
    TH = thinning(desN, np.nan_to_num(hyp.to_numpy()), hyp.is_not_null().to_numpy())
    nhis_artifacts(nr, Dd, Ds, TH)
    age = ad["AGE"].to_numpy()
    wa = (age >= 18) & (age <= 64)
    uy = ad["unins_y"].to_numpy().astype(float)
    nu = three_ses(desN, np.nan_to_num(uy), wa & ~np.isnan(uy))
    GC, GM = group_contrasts(desN, ad, uy, wa)
    assert len(GC) == 27, len(GC)
    ne_mw = group_artifacts(nu, GC, GM)

    br = brfss_block(load_brfss())
    constructs_artifacts(L, nr, br)
    contrast_artifacts(L, nr, br)
    make_ledgers()
    V = validation_block(L, P, nr, Ds, br, svy_rows, nu, GC)

    dump(ART / "facts.json", {"key": KEY, "facts": FACTS})
    dump(ART / "ledger.json", {"key": KEY, "ledgers": LEDGERS})
    for k, g in FIGS.items():
        dump(FIG / f"{k}.json", g)
    dump(ART / "manifest.json", {
        "key": KEY, "slug": SLUG, "inputs": INPUTS, "code": "build.py", "validation": V,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "software": {"python_svy": svy.__version__, "polars": pl.__version__, "duckdb": duckdb.__version__,
                     "numpy": np.__version__, "scipy": scipy.__version__},
        "settings": {"seed": SEED, "thinning_draws": THIN_DRAWS, "thinning_fractions": THIN_FRACS,
                     "std_pop_2000": STD_POP_COUNTS, "confidence": 0.95,
                     "lonely_psu": "fail everywhere except BRFSS (adjust) and the labelled delete-rows-first comparisons",
                     "missing_data": "item nonresponse excluded from each domain (drop_nulls equivalent), recorded per fact"},
    })
    fails = [v for v in V if v.get("pass") is False]
    print(f"facts {len(FACTS)}  figures {len(FIGS)}  ledgers {len(LEDGERS)}  validation {len(V)}  R failures {len(fails)}")


if __name__ == "__main__":
    main()
