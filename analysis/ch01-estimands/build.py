#!/usr/bin/env python
"""Chapter 1 -- What Are We Trying to Estimate?    key: ch1    slug: ch01-estimands

    python build.py          regenerate artifacts/ (facts, ledgers, and figures are
                             byte-identical across runs; only manifest.json carries a
                             timestamp)
    python build.py --no-r   skip the R `survey` oracle (verify.R)

Inputs (cleaned IPUMS store, read-only):
    analysis/atus/atus_respondent.parquet               ATUS 2023 diaries, weight WT06
    analysis/cps/cps_voter.parquet                      CPS November voting supplements 2008-2024
    analysis/cps/cps_foodsec.parquet                    CPS December 2023 Food Security Supplement
    analysis/cps/cps_asec/part_2020_2025.parquet        CPS ASEC, survey years 2020-2025
    analysis/cps/cps_asec_repwt/part_2020_2025.parquet  160 SDR person replicate weights

Variance tiers are properties of the extracts (book CONTRACT, section 6):
    ATUS and the two CPS supplements   weights_only_understated: point estimates only
    CPS ASEC                           replicate_sdr(160): (4/160) sum_r (theta_r - theta)^2,
                                       df = 159, centred on the full-sample estimate

Two implementations everywhere: every point estimate is computed in numpy on a sorted
frame and again in DuckDB SQL (must agree to 1e-9); every ASEC standard error is
computed with svy (method="replication", variance_center="estimate", df asserted = 159)
and again by hand (must agree to 1e-10). verify.R re-derives four ASEC results with
R `survey`; build.py runs it and records the comparison in manifest.validation.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path

os.environ.setdefault("NO_COLOR", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import polars as pl  # noqa: E402
import scipy  # noqa: E402
import svy  # noqa: E402
from scipy import stats  # noqa: E402

KEY, SLUG = "ch1", "ch01-estimands"
HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
FIG = ART / "figures"
SCRATCH = HERE / "_scratch"
STORE = Path("C:/Users/Vishal Singh/Box/ipums/analysis")
ATUS = STORE / "atus" / "atus_respondent.parquet"
VOTER = STORE / "cps" / "cps_voter.parquet"
# Raw IPUMS codes for the same records: VOTED = 99 is "Not in universe".
VOTER_RAW = Path("C:/Users/Vishal Singh/Box/ipums/parquet/cps/cps_voter.parquet")
FOODSEC = STORE / "cps" / "cps_foodsec.parquet"
ASEC = STORE / "cps" / "cps_asec" / "part_2020_2025.parquet"
REPWT = STORE / "cps" / "cps_asec_repwt" / "part_2020_2025.parquet"
RSCRIPT = Path("C:/Program Files/R/R-4.6.1/bin/x64/Rscript.exe")

N_REPS, SDR_SCALE, SDR_DF = 160, 4 / 160, 159
T975 = float(stats.t.ppf(0.975, SDR_DF))
WEIGHTS_ONLY = "weights_only_understated"
SDR160 = "replicate_sdr(160)"

FACTS: dict[str, dict] = {}
LEDGERS: dict[str, dict] = {}
FIGURES: dict[str, dict] = {}
VALIDATION: list[dict] = []
INPUTS: list[dict] = []
DIAG: dict[str, object] = {}  # printed for NOTES.md; never written to the deterministic artifacts

# --------------------------------------------------------------------------- benchmarks
# External benchmarks (CONTRACT section 6: "benchmarks are not truth"). Each value is
# quoted from the named publication; None means the value was not verified this pass.
BLS = {
    "hours_per_day": 3.56, "pct_engaged": 43.9, "hours_if_engaged": 8.13,
    "source": "BLS, American Time Use Survey - 2023 Results, USDL-24-1208 (June 27, 2024), "
              "Table 1, 'Working and work-related activities'",
}
TURNOUT_PUBLISHED = {2008: 63.6, 2010: 45.5, 2012: 61.8, 2014: 41.9, 2016: 61.4, 2018: 53.4,
                     2020: 66.8, 2022: 52.2, 2024: 65.3}
TURNOUT_SOURCE = {
    **{y: "Census Bureau, reported voting rates of the citizen population 18+ (historical "
          "Table A-1), as recorded in logs/validation_benchmarks_clean.md"
       for y in (2008, 2010, 2012, 2014, 2016, 2018, 2020)},
    2022: "Census Bureau release, May 2, 2023: 52.2% of the citizen voting-age population voted",
    2024: "Census Bureau release, April 30, 2025: 65.3% of the citizen voting-age population voted",
}
USDA = {
    "hh_pct": 13.5, "hh_million": 18.0, "hh_sample": 30863, "people_million": 47.4,
    "people_pct": 14.3, "adults_million": 33.6, "children_million": 13.8,
    "children_in_hh_with_fi_children_pct": 9.9, "hh_with_children_fi_children_pct": 8.9,
    "source": "USDA ERS, Household Food Security in the United States in 2023 "
              "(ERR-337; Rabbitt, Reed-Jones, Hales, and Burke, September 2024)",
}
# Census published poverty rates by income year (percent), read from the reports' tables:
# official from P60-287 Table A-3 (historical, 2019-2024) cross-checked with P60-277 and
# P60-280 Table A-1; SPM from P60-287 Table B-2 (historical) and B-3, and P60-277/P60-280
# Table B-3. P60-287 prints two SPM rows for 2019; the unfootnoted row (the estimate as
# first published) is the comparator for SPMPOV from the 2020 ASEC. The 2020 rates are
# the revised values printed in P60-277 and P60-287 (official 11.5, SPM 9.2).
POV_PUBLISHED = {
    ("official", "all"): {2019: 10.5, 2020: 11.5, 2021: 11.6, 2022: 11.5, 2023: 11.1, 2024: 10.6},
    ("official", "child"): {2019: 14.4, 2020: 16.0, 2021: 15.3, 2022: 15.0, 2023: 15.3, 2024: 14.3},
    ("official", "age65"): {2019: 8.9, 2020: 8.9, 2021: 10.3, 2022: 10.2, 2023: 9.7, 2024: 9.9},
    ("spm", "all"): {2019: 11.7, 2020: 9.2, 2021: 7.8, 2022: 12.4, 2023: 12.9, 2024: 12.9},
    ("spm", "child"): {2019: 12.5, 2020: 9.7, 2021: 5.2, 2022: 12.4, 2023: 13.7, 2024: 13.4},
    ("spm", "age65"): {2019: 12.8, 2020: 9.5, 2021: 10.7, 2022: 14.1, 2023: 14.2, 2024: 15.0},
}
POV_SOURCE = ("Census Bureau, Poverty in the United States: 2021 (P60-277), 2022 (P60-280), "
              "and 2024 (P60-287), Tables A-1, A-3, B-2, and B-3")

SRC_ATUS = "IPUMS ATUS 2023 (analysis/atus/atus_respondent.parquet)"
SRC_FS = "IPUMS CPS, December 2023 Food Security Supplement (analysis/cps/cps_foodsec.parquet)"
POP_ATUS = "U.S. civilian noninstitutional population aged 15 and older"


def src_voter(year: int) -> str:
    return (f"IPUMS CPS, November {year} Voting and Registration Supplement "
            "(analysis/cps/cps_voter.parquet; raw VOTED codes from parquet/cps/cps_voter.parquet)")


def src_asec(survey_year: int) -> str:
    return (f"IPUMS CPS ASEC {survey_year} (analysis/cps/cps_asec/part_2020_2025.parquet; "
            "replicate weights analysis/cps/cps_asec_repwt/part_2020_2025.parquet)")


# --------------------------------------------------------------------------- helpers
def rnd(x, d: int = 6):
    return None if x is None else float(round(float(x), d))


def pct(p: float, d: int = 1) -> str:
    return f"{100 * p:.{d}f}%"


def pct_ci(lo: float, hi: float, d: int = 1) -> str:
    return f"{100 * lo:.{d}f}%–{100 * hi:.{d}f}%"


def pts(x: float, d: int = 1) -> str:
    return f"{100 * x:.{d}f}"


def pts_ci(lo: float, hi: float, d: int = 1) -> str:
    return f"{100 * lo:.{d}f}–{100 * hi:.{d}f}"


def cnt(n) -> str:
    return f"{int(n):,}"


def sq(p: Path) -> str:
    return "'" + p.as_posix() + "'"


def query(sql: str) -> pl.DataFrame:
    con = duckdb.connect()
    try:
        return con.execute(sql).pl()
    finally:
        con.close()


def query_row(sql: str) -> tuple:
    con = duckdb.connect()
    try:
        return con.execute(sql).fetchone()
    finally:
        con.close()


def agree(a: float, b: float, tol: float, what: str) -> None:
    if not abs(float(a) - float(b)) <= tol:
        raise AssertionError(f"{what}: {a!r} vs {b!r} (tolerance {tol})")


def fact(key: str, value, display: str, *, estimand: str, source: str, unit=None, n=None,
         weight=None, variance: str = WEIGHTS_ONLY, se=None, ci=None, ci_display=None,
         df=None, benchmark=None, note: str = "", digits: int = 6) -> None:
    if key in FACTS:
        raise KeyError(f"duplicate fact {key}")
    if n is not None and n < 100:
        raise ValueError(f"{key}: unweighted n = {n} is below the suppression floor of 100")
    lo, hi = ci if ci is not None else (None, None)
    if isinstance(value, (float, np.floating)):
        value = rnd(value, digits)
    FACTS[key] = {
        "value": value, "display": display, "unit": unit,
        "se": rnd(se, 8), "ci_low": rnd(lo, 8), "ci_high": rnd(hi, 8), "ci_display": ci_display,
        "df": df, "n": None if n is None else int(n), "weight": weight, "variance": variance,
        "estimand": estimand, "source": source, "benchmark": benchmark, "note": note,
    }


def ledger(key: str, **fields) -> None:
    need = ["title", "target_population", "estimand", "estimator", "explicit_weights",
            "implicit_weights", "randomness", "variance_estimator", "assumptions"]
    missing = [f for f in need if not fields.get(f)]
    if missing:
        raise ValueError(f"ledger {key}: missing {missing}")
    for f in fields.get("facts", []):
        if f.split(".", 1)[1] not in FACTS:
            raise KeyError(f"ledger {key} cites unknown fact {f}")
    LEDGERS[key] = fields


def check(id_: str, kind: str, ours, reference, source: str, ok=None, note: str = "") -> None:
    VALIDATION.append({
        "id": id_, "kind": kind, "ours": ours, "reference": reference, "source": source,
        "result": "recorded" if ok is None else ("match" if ok else "differs"), "note": note,
    })


# =========================================================================== ATUS
def build_atus() -> None:
    df = query(f"""
        SELECT CASEID, WT06, BLS_WORK, DAY, HOLIDAY, CAST(emp3 AS VARCHAR) AS emp3
        FROM read_parquet({sq(ATUS)}) WHERE YEAR = 2023 ORDER BY CASEID""")
    n = df.height
    INPUTS.append({"path": "analysis/atus/atus_respondent.parquet", "rows": n,
                   "note": "YEAR = 2023; CASEID, WT06, BLS_WORK, DAY, HOLIDAY, emp3"})
    w = df["WT06"].to_numpy().astype(float)
    y = df["BLS_WORK"].to_numpy().astype(float)
    day = df["DAY"].to_numpy()
    hol = df["HOLIDAY"].to_numpy()
    emp = df["emp3"].to_numpy()
    assert n == 8548 and np.all(w > 0) and not np.isnan(y).any()
    assert set(np.unique(emp).tolist()) == {"Employed", "Unemployed", "Not in labor force"}
    weekday = (day >= 2) & (day <= 6)  # DAY codes: 1 = Sunday ... 7 = Saturday (dictionary)
    weekend = (day == 1) | (day == 7)
    assert np.all(weekday ^ weekend)
    employed = emp == "Employed"  # emp3 from EMPSTAT: employed at work or absent
    worked = y > 0
    everyone = np.ones(n, dtype=bool)

    # id, fact key, label, population of days, what the population conditions on, mask, weighted
    specs = [
        ("all_unweighted", "atus_work_unweighted", "All person-days, unweighted",
         "All person-days (each diary counted once)", "nothing", everyone, False),
        ("all_weighted", "atus_work_weighted", "All person-days",
         "All person-days", "nothing", everyone, True),
        ("weekdays", "atus_work_weekday", "Weekdays only",
         "Monday–Friday person-days", "the day of the week", weekday, True),
        ("employed", "atus_work_employed", "Employed people",
         "Person-days of employed people", "employment status", employed, True),
        ("days_worked", "atus_work_anywork", "Days with any work",
         "Person-days that include some work", "the outcome itself", worked, True),
        ("employed_days_worked", "atus_work_employed_worked", "Employed people, on days they worked",
         "Work days of employed people", "employment and the outcome", employed & worked, True),
    ]
    est: dict[str, dict] = {}
    for id_, fkey, label, popn, cond, m, weighted in specs:
        ww = w[m] if weighted else np.ones(int(m.sum()))
        est[id_] = {"est": float(np.sum(ww * y[m]) / np.sum(ww)), "n": int(m.sum()), "fkey": fkey,
                    "label": label, "population": popn, "conditions": cond, "weighted": weighted}

    sql_row = query_row(f"""
        SELECT AVG(BLS_WORK), SUM(WT06 * BLS_WORK) / SUM(WT06),
          SUM(WT06 * BLS_WORK) FILTER (WHERE DAY BETWEEN 2 AND 6) / SUM(WT06) FILTER (WHERE DAY BETWEEN 2 AND 6),
          SUM(WT06 * BLS_WORK) FILTER (WHERE emp3 = 'Employed') / SUM(WT06) FILTER (WHERE emp3 = 'Employed'),
          SUM(WT06 * BLS_WORK) FILTER (WHERE BLS_WORK > 0) / SUM(WT06) FILTER (WHERE BLS_WORK > 0),
          SUM(WT06 * BLS_WORK) FILTER (WHERE emp3 = 'Employed' AND BLS_WORK > 0)
            / SUM(WT06) FILTER (WHERE emp3 = 'Employed' AND BLS_WORK > 0)
        FROM read_parquet({sq(ATUS)}) WHERE YEAR = 2023""")
    for spec, v in zip(specs, sql_row):
        agree(est[spec[0]]["est"], v, 1e-9, f"ATUS {spec[0]} numpy vs SQL")
    audition = {"all_unweighted": (155.4, 8548), "all_weighted": (213.8, 8548), "weekdays": (272.0, 4366),
                "employed": (325.8, 4976), "days_worked": (487.5, 2897), "employed_days_worked": (496.4, 2804)}
    for id_, (v, nn) in audition.items():
        ok = round(est[id_]["est"], 1) == v and est[id_]["n"] == nn
        check(f"atus_{id_}_vs_v4_audition", "regression", round(est[id_]["est"], 4), v,
              "docs/PLAN_v4_implementation.md section 3.1 (raw store)", ok, f"n = {est[id_]['n']} vs {nn}")
        assert ok, (id_, est[id_])

    share_worked = float(np.sum(w * worked) / np.sum(w))
    wkend_sample = float(np.mean(weekend))
    wkend_weighted = float(np.sum(w * weekend) / np.sum(w))
    wsum = float(np.sum(w))
    persons = wsum / 365.0

    m_bls = weekday & (hol == 0)
    DIAG["atus_weekday_nonholiday_min"] = round(float(np.sum(w[m_bls] * y[m_bls]) / np.sum(w[m_bls])), 2)
    DIAG["atus_weekday_nonholiday_n"] = int(m_bls.sum())
    DIAG["atus_holiday_diaries"] = int(np.sum(hol == 1))
    DIAG["atus_day_of_week_only_reweighting_min"] = round(
        5 / 7 * float(np.mean(y[weekday])) + 2 / 7 * float(np.mean(y[weekend])), 2)
    DIAG["atus_unweighted_share_days_worked"] = round(float(np.mean(worked)), 4)
    DIAG["atus_weighted_share_employed_persondays"] = round(float(np.sum(w * employed) / np.sum(w)), 4)

    # ---- facts
    wt = "WT06"
    activity = ("working and work-related activities (BLS major category; includes work-related travel)")
    fact("atus_n", n, cnt(n), unit="diaries", source=SRC_ATUS, variance="none",
         estimand="Number of 2023 ATUS respondents; each reports one designated diary day")
    estimands = {
        "all_unweighted": (f"Unweighted mean minutes of {activity} over all 2023 ATUS diaries, each "
                           "diary counted once. An estimator of the all-person-days mean, not a "
                           "separate estimand."),
        "all_weighted": f"Mean minutes per person-day of {activity}, all 2023 person-days, {POP_ATUS}",
        "weekdays": f"Mean minutes per person-day of {activity}, Monday–Friday person-days in 2023, {POP_ATUS}",
        "employed": (f"Mean minutes per person-day of {activity}, 2023 person-days of people employed "
                     f"at their ATUS interview, {POP_ATUS}"),
        "days_worked": f"Mean minutes of {activity} on 2023 person-days that included any such activity, {POP_ATUS}",
        "employed_days_worked": (f"Mean minutes of {activity} on 2023 person-days on which employed people "
                                 f"did any such activity, {POP_ATUS}"),
    }
    for id_, e in est.items():
        bench = None
        if id_ == "all_weighted":
            bench = f"BLS ATUS 2023, Table 1: {BLS['hours_per_day']} hours per day (external benchmark)"
        elif id_ == "days_worked":
            bench = (f"BLS ATUS 2023, Table 1: {BLS['hours_if_engaged']} hours per day for those who "
                     "engaged in the activity (external benchmark)")
        fact(e["fkey"], e["est"], f"{e['est']:.1f}", unit="minutes per day", n=e["n"],
             weight=wt if e["weighted"] else "none", estimand=estimands[id_], source=SRC_ATUS,
             benchmark=bench, digits=4)
    for id_, key in [("all_weighted", "atus_work_weighted_hours"), ("days_worked", "atus_work_anywork_hours"),
                     ("employed_days_worked", "atus_work_employed_worked_hours")]:
        h = est[id_]["est"] / 60
        bench = None
        if id_ == "all_weighted":
            bench = f"BLS ATUS 2023, Table 1: {BLS['hours_per_day']} hours per day (external benchmark)"
        if id_ == "days_worked":
            bench = f"BLS ATUS 2023, Table 1: {BLS['hours_if_engaged']} hours (external benchmark)"
        fact(key, h, f"{h:.2f}", unit="hours per day", n=est[id_]["n"], weight=wt,
             estimand=estimands[id_].replace("Mean minutes", "Mean hours"), source=SRC_ATUS,
             benchmark=bench, digits=4)
    fact("atus_share_days_worked", share_worked, pct(share_worked), n=n, weight=wt, source=SRC_ATUS,
         estimand=f"Share of 2023 person-days that included any {activity}, {POP_ATUS}",
         benchmark=f"BLS ATUS 2023, Table 1: {BLS['pct_engaged']}% engaged per day (external benchmark)")
    fact("atus_weekend_share_sample", wkend_sample, pct(wkend_sample), n=n, weight="none",
         variance="none", source=SRC_ATUS,
         estimand="Share of 2023 ATUS diaries that fall on a Saturday or Sunday (unweighted count of diaries)")
    fact("atus_weekend_share_weighted", wkend_weighted, pct(wkend_weighted), n=n, weight=wt,
         source=SRC_ATUS, estimand="Share of 2023 person-days that are Saturdays or Sundays, weighted by WT06",
         note="Weekend days are 2/7 = 28.6% of calendar days; the weighted share differs slightly "
              "because the number of weekend days and the population vary by quarter.")
    fact("atus_weight_sum", wsum, f"{wsum / 1e9:.1f} billion", unit="person-days", n=n, weight=wt,
         variance="none", source=SRC_ATUS, digits=0,
         estimand="Sum of WT06 over 2023 respondents: the number of person-days the sample represents")
    fact("atus_persons_implied", persons, f"{persons / 1e6:.1f} million", unit="people", n=n, weight=wt,
         variance="none", source=SRC_ATUS, digits=0,
         estimand="Sum of WT06 over 2023 respondents divided by 365: average population represented")
    check("atus_weighted_hours_vs_bls", "benchmark", round(est["all_weighted"]["est"] / 60, 4),
          BLS["hours_per_day"], BLS["source"], round(est["all_weighted"]["est"] / 60, 2) == BLS["hours_per_day"])
    check("atus_share_engaged_vs_bls", "benchmark", round(100 * share_worked, 3), BLS["pct_engaged"],
          BLS["source"], round(100 * share_worked, 1) == BLS["pct_engaged"])
    check("atus_hours_if_engaged_vs_bls", "benchmark", round(est["days_worked"]["est"] / 60, 4),
          BLS["hours_if_engaged"], BLS["source"],
          round(est["days_worked"]["est"] / 60, 2) == BLS["hours_if_engaged"])

    # ---- ledgers (one per option, so the switcher can show each estimand's ledger)
    common = {
        "randomness": ("Sampling (ATUS draws households from those completing the CPS, one person aged "
                       "15+ per household, and assigns the diary day) and response."),
        "variance_estimator": ("Not computed. The store carries no ATUS replicate weights (BLS publishes "
                               "them as RWT06), so an SE from WT06 alone would leave out the design, and its "
                               "error could run in either direction."),
    }
    wt_text = (f"WT06, the ATUS final weight. Each diary counts for the number of person-days it "
               f"represents: the 2023 weights sum to {wsum / 1e9:.1f} billion person-days, about 365 for "
               f"each of {persons / 1e6:.1f} million people. BLS constructs it so that weekday and weekend "
               f"diaries add up to the weekday and weekend person-days in each quarter, for the population "
               f"and selected subgroups.")
    ledger_text = {
        "all_unweighted": dict(
            title="All person-days, unweighted (ATUS 2023)",
            target_population=f"All 2023 person-days of the {POP_ATUS} (the same target as the weighted row)",
            estimand=estimands["all_weighted"],
            estimator="Unweighted mean of BLS_WORK over all 8,548 diaries",
            explicit_weights=("None: every diary counts once. Weekend diaries are "
                              f"{pct(wkend_sample)} of the sample but {pct(wkend_weighted)} of the "
                              "weighted person-days, so they get far more than their share."),
            implicit_weights="Equal weights per diary, which over-represents weekend days and groups that respond more often.",
            assumptions="Only if the sample were a simple random sample of person-days would this target the population mean. ATUS is not one.",
            facts=["ch1.atus_work_unweighted", "ch1.atus_weekend_share_sample"]),
        "all_weighted": dict(
            title="How much do Americans work? All person-days (ATUS 2023)",
            target_population=f"All 2023 person-days of the {POP_ATUS}",
            estimand=estimands["all_weighted"],
            estimator="Weighted mean sum(w_i y_i) / sum(w_i) over all 2023 diaries, w = WT06",
            explicit_weights=wt_text,
            implicit_weights="None beyond WT06.",
            assumptions=("The designated diary day represents that person's days of its type; WT06's "
                         "calibration population matches the target; BLS_WORK classifies activities as BLS does."),
            facts=["ch1.atus_work_weighted", "ch1.atus_work_weighted_hours", "ch1.atus_weight_sum"]),
        "weekdays": dict(
            title="Weekdays only (ATUS 2023)",
            target_population=f"Monday–Friday person-days in 2023 of the {POP_ATUS}",
            estimand=estimands["weekdays"],
            estimator="Weighted mean over diaries with DAY in 2–6, w = WT06",
            explicit_weights=wt_text,
            implicit_weights="Relative to the all-days mean, weekend days get zero weight.",
            assumptions="As for all person-days. Holidays that fall on a weekday are included; BLS's own weekday tables exclude them.",
            facts=["ch1.atus_work_weekday"]),
        "employed": dict(
            title="Employed people, all days (ATUS 2023)",
            target_population=f"2023 person-days of employed members of the {POP_ATUS}",
            estimand=estimands["employed"],
            estimator="Weighted mean over diaries with emp3 = Employed, w = WT06",
            explicit_weights=wt_text,
            implicit_weights="Relative to the all-days mean, person-days of people not employed get zero weight.",
            assumptions="Employment status measured at the ATUS interview describes the diary day.",
            facts=["ch1.atus_work_employed"]),
        "days_worked": dict(
            title="Days with any work (ATUS 2023)",
            target_population=f"2023 person-days with some work, {POP_ATUS}",
            estimand=estimands["days_worked"],
            estimator="Weighted mean over diaries with BLS_WORK above zero, w = WT06",
            explicit_weights=wt_text,
            implicit_weights="Relative to the all-days mean, days without work get zero weight.",
            assumptions=("The population is defined by the outcome, so this is a conditional mean "
                         "(an intensive margin), not a population average."),
            facts=["ch1.atus_work_anywork", "ch1.atus_share_days_worked"]),
        "employed_days_worked": dict(
            title="Employed people, on days they worked (ATUS 2023)",
            target_population=f"2023 work days of employed members of the {POP_ATUS}",
            estimand=estimands["employed_days_worked"],
            estimator="Weighted mean over diaries with emp3 = Employed and BLS_WORK above zero, w = WT06",
            explicit_weights=wt_text,
            implicit_weights="Relative to the all-days mean, zero weight on days of the non-employed and on non-work days.",
            assumptions=("As above. BLS's headline 'hours worked on days worked' counts time working "
                         "at jobs only, a narrower activity, so it is yet another estimand."),
            facts=["ch1.atus_work_employed_worked", "ch1.atus_work_employed_worked_hours"]),
    }
    ledger_ids = {"all_weighted": "atus_work", "all_unweighted": "atus_work_unweighted",
                  "weekdays": "atus_work_weekday", "employed": "atus_work_employed",
                  "days_worked": "atus_work_anywork", "employed_days_worked": "atus_work_employed_worked"}
    for id_, fields in ledger_text.items():
        ledger(ledger_ids[id_], **{**common, **fields})

    # ---- figures
    notes = {
        "all_unweighted": ("Same target as the next option, wrong estimator: weekend diaries are "
                           f"{pct(wkend_sample)} of the sample but {pct(wkend_weighted)} of weighted days."),
        "all_weighted": f"The figure BLS publishes: {est['all_weighted']['est'] / 60:.2f} hours a day.",
        "weekdays": "A different population of days: Saturdays and Sundays are excluded.",
        "employed": "A different population of people: those employed at their interview.",
        "days_worked": f"Conditions on the outcome: only the {pct(share_worked)} of days that include work.",
        "employed_days_worked": "Conditions on both employment and the outcome.",
    }
    units = {"all_unweighted": "person-day", "all_weighted": "person-day", "weekdays": "weekday person-day",
             "employed": "person-day of an employed person", "days_worked": "person-day with work",
             "employed_days_worked": "work day of an employed person"}
    FIGURES["atus_estimands"] = {
        "type": "estimand-set",
        "title": "How much do Americans work? Six defensible answers",
        "subtitle": "ATUS 2023, minutes per day of working and work-related activities",
        "question": "How much do Americans work?",
        "format": "min1",
        "alt": ("An interactive list of six answers to 'how much do Americans work', from "
                f"{est['all_unweighted']['est']:.1f} minutes per day (all diaries, unweighted) to "
                f"{est['employed_days_worked']['est']:.1f} minutes (employed people on days they worked); "
                "each option names its population of days, weight, and sample size."),
        "source": SRC_ATUS,
        "note": "Weights-only extract: point estimates only; no intervals.",
        "options": [
            {"id": id_, "label": e["label"], "unit": units[id_],
             "weight": "WT06" if e["weighted"] else "none", "estimate": rnd(e["est"], 4),
             "display": f"{e['est']:.1f}", "n": e["n"], "note": notes[id_],
             "ledger": f"{KEY}.{ledger_ids[id_]}"}
            for id_, e in est.items()
        ],
    }
    FIGURES["atus_six_estimands"] = {
        "type": "table",
        "title": "Six answers to one question",
        "subtitle": "ATUS 2023: minutes per day of working and work-related activities",
        "alt": ("Table of six estimates of daily work time from ATUS 2023: 155.4 minutes unweighted, "
                "213.8 weighted over all person-days, 272.0 on weekdays, 325.8 for employed people, "
                "487.5 on days with any work, and 496.4 for employed people on days they worked, with "
                "the population of days, weight, and number of diaries for each."),
        "source": SRC_ATUS,
        "note": ("Weights-only extract: point estimates only. The first two rows share a target; each "
                 "later row changes the population of days."),
        "columns": [
            {"key": "label", "label": "Answer", "align": "left"},
            {"key": "population", "label": "Population of days", "align": "left"},
            {"key": "conditions", "label": "Conditions on", "align": "left"},
            {"key": "weight", "label": "Weight", "align": "left"},
            {"key": "n", "label": "Diaries", "format": "int", "align": "right"},
            {"key": "minutes", "label": "Minutes per day", "format": "min1", "align": "right"},
            {"key": "hours", "label": "Hours per day", "format": "num2", "align": "right"},
        ],
        "rows": [
            {"label": e["label"], "population": e["population"], "conditions": e["conditions"],
             "weight": "WT06" if e["weighted"] else "none", "n": e["n"],
             "minutes": rnd(e["est"], 4), "hours": rnd(e["est"] / 60, 4)}
            for e in est.values()
        ],
    }
    # audit the alt text numbers against the estimates (no stale hand-typed values)
    for e in est.values():
        assert f"{e['est']:.1f}" in FIGURES["atus_six_estimands"]["alt"], e


# =========================================================================== CPS voting
def build_turnout() -> None:
    # "Not in universe" is read from the raw codes. The cleaned layer nullifies VOTED = 99 along with
    # item nonresponse, and the store's voted_census (corrected 2026-09-10) no longer leaves those
    # records null, so neither can flag them.
    df = query(f"""
        SELECT a.YEAR, a.SERIAL, a.PERNUM, a.VOSUPPWT, a.WTFINL, a.voted_census, a.voted_selfreport,
               r.VOTED AS VOTED_RAW
        FROM read_parquet({sq(VOTER)}) a
        LEFT JOIN read_parquet({sq(VOTER_RAW)}) r
          ON a.YEAR = r.YEAR AND a.SERIAL = r.SERIAL AND a.PERNUM = r.PERNUM
        WHERE a.YEAR >= 2008 AND a.citizen_b = 1 AND a.AGE >= 18
        ORDER BY a.YEAR, a.SERIAL, a.PERNUM""")
    assert df["VOTED_RAW"].null_count() == 0, "every cleaned record should match one raw record"
    assert not df.select(["YEAR", "SERIAL", "PERNUM"]).is_duplicated().any(), "the join must be 1:1"
    INPUTS.append({"path": "analysis/cps/cps_voter.parquet", "rows": df.height,
                   "note": "citizens 18+ (citizen_b = 1, AGE >= 18), November supplements 2008-2024"})
    INPUTS.append({"path": "parquet/cps/cps_voter.parquet", "rows": df.height,
                   "note": "raw VOTED codes for the same records (joined on YEAR, SERIAL, PERNUM), to flag 'Not in universe'"})
    years = sorted(TURNOUT_PUBLISHED)
    res: dict[int, dict] = {}
    for yr in years:
        d = df.filter(pl.col("YEAR") == yr)
        w = d["VOSUPPWT"].to_numpy().astype(float)
        wf = d["WTFINL"].to_numpy().astype(float)
        vc = d["voted_census"].fill_null(-1).to_numpy()
        sr = d["voted_selfreport"].fill_null(-1).to_numpy()
        vraw = d["VOTED_RAW"].to_numpy()
        counted = w > 0                      # everyone the supplement weight counts
        voter = sr == 1
        responded = sr >= 0                  # answered: voted or did not vote
        niu = vraw == 99                     # raw VOTED = 99 'Not in universe'
        assert np.array_equal(voter, vc == 1)
        assert np.array_equal(voter, vraw == 2)
        assert np.all(niu[~counted]), "zero-weight citizen adults should all be out of universe"
        assert np.allclose(w[counted], wf[counted], atol=0.01), "VOSUPPWT should equal WTFINL"
        in_recode = counted & ~niu           # a recode that treats 'not in universe' as structural
        r = {
            "census": float(np.sum(w[counted & voter]) / np.sum(w[counted])),
            "recode": float(np.sum(w[in_recode & voter]) / np.sum(w[in_recode])),
            "respondents": float(np.sum(w[counted & responded & voter]) / np.sum(w[counted & responded])),
            "unweighted": float(np.mean(voter[counted & responded])),
            "nonresponse": float(np.sum(w[counted & ~responded]) / np.sum(w[counted])),
            "n_counted": int(counted.sum()), "n_responded": int((counted & responded).sum()),
            "n_niu_counted": int((counted & niu).sum()), "n_zero": int((~counted).sum()),
            "cvap_m": float(np.sum(w[counted]) / 1e6),
        }
        res[yr] = r
    sql = query(f"""
        SELECT a.YEAR AS YEAR,
          SUM(a.VOSUPPWT * (a.voted_selfreport = 1)::INT) FILTER (WHERE a.VOSUPPWT > 0) / SUM(a.VOSUPPWT) FILTER (WHERE a.VOSUPPWT > 0) AS census,
          SUM(a.VOSUPPWT * (r.VOTED = 2)::INT) FILTER (WHERE a.VOSUPPWT > 0 AND r.VOTED <> 99)
            / SUM(a.VOSUPPWT) FILTER (WHERE a.VOSUPPWT > 0 AND r.VOTED <> 99) AS recode,
          SUM(a.VOSUPPWT * a.voted_selfreport) FILTER (WHERE a.VOSUPPWT > 0 AND a.voted_selfreport IS NOT NULL)
            / SUM(a.VOSUPPWT) FILTER (WHERE a.VOSUPPWT > 0 AND a.voted_selfreport IS NOT NULL) AS respondents,
          AVG(a.voted_selfreport) FILTER (WHERE a.VOSUPPWT > 0 AND a.voted_selfreport IS NOT NULL) AS unweighted
        FROM read_parquet({sq(VOTER)}) a
        JOIN read_parquet({sq(VOTER_RAW)}) r ON a.YEAR = r.YEAR AND a.SERIAL = r.SERIAL AND a.PERNUM = r.PERNUM
        WHERE a.YEAR >= 2008 AND a.citizen_b = 1 AND a.AGE >= 18
        GROUP BY a.YEAR ORDER BY a.YEAR""")
    for row in sql.iter_rows(named=True):
        for k in ("census", "recode", "respondents", "unweighted"):
            agree(res[row["YEAR"]][k], row[k], 1e-9, f"turnout {row['YEAR']} {k} numpy vs SQL")
    for yr in years:
        ours = round(100 * res[yr]["census"], 1)
        ok = ours == TURNOUT_PUBLISHED[yr]
        check(f"turnout_census_{yr}_vs_published", "benchmark", round(100 * res[yr]["census"], 3),
              TURNOUT_PUBLISHED[yr], TURNOUT_SOURCE[yr], ok,
              "Census convention: all citizen adults with a positive supplement weight in the "
              "denominator; supplement nonrespondents count as nonvoters.")
        assert ok, (yr, ours)
        if yr >= 2022:
            check(f"turnout_recode_{yr}_vs_published", "benchmark", round(100 * res[yr]["recode"], 3),
                  TURNOUT_PUBLISHED[yr], TURNOUT_SOURCE[yr], False,
                  f"A recode that treats VOTED = 'Not in universe' as structural (as the store's voted_census did "
                  f"until its 2026-09-10 correction) drops "
                  f"{res[yr]['n_niu_counted']:,} positive-weight citizen adults (supplement nonrespondents "
                  f"since 'No Response' was removed as a category in November 2022).")
    check("vosuppwt_equals_wtfinl", "internal", "max |VOSUPPWT - WTFINL| <= 0.01 on every positive-weight record",
          "2008-2024 citizen adults", "analysis/cps/cps_voter.parquet", True,
          "The voting supplement weight carries no adjustment for supplement nonresponse.")
    DIAG["turnout"] = {yr: {k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items()}
                       for yr, r in res.items()}

    r20, r22, r24 = res[2020], res[2022], res[2024]
    wt = "VOSUPPWT"
    cvap = "U.S. citizens 18 and older in the civilian noninstitutional population, not in the armed forces"
    fact("turnout_census_2020", r20["census"], pct(r20["census"]), n=r20["n_counted"], weight=wt,
         source=src_voter(2020),
         estimand=(f"Share of {cvap} who reported voting in November 2020, supplement nonrespondents "
                   "counted as nonvoters (Census Bureau convention)"),
         benchmark="Census Bureau published 66.8% (external benchmark)")
    fact("turnout_resp_2020", r20["respondents"], pct(r20["respondents"]), n=r20["n_responded"], weight=wt,
         source=src_voter(2020),
         estimand=f"Share who reported voting among {cvap} who answered the voting question, November 2020")
    fact("turnout_unw_2020", r20["unweighted"], pct(r20["unweighted"]), n=r20["n_responded"], weight="none",
         source=src_voter(2020),
         estimand="Unweighted share reporting a vote among citizen adults who answered the voting question, November 2020")
    fact("turnout_nonresp_2020", r20["nonresponse"], pct(r20["nonresponse"]), n=r20["n_counted"], weight=wt,
         source=src_voter(2020),
         estimand=f"Weighted share of {cvap} with no answer to the voting question, November 2020")
    gap_d = r20["respondents"] - r20["census"]
    gap_w = r20["unweighted"] - r20["respondents"]
    fact("turnout_gap_denominator_2020", gap_d, pts(gap_d, 0), unit="percentage points", n=r20["n_counted"],
         weight=wt, source=src_voter(2020),
         estimand="Respondents-only turnout minus Census-convention turnout, November 2020 (rounded to a whole point)")
    fact("turnout_gap_weighting_2020", gap_w, pts(gap_w, 1), unit="percentage points", n=r20["n_responded"],
         weight=wt, source=src_voter(2020),
         estimand="Unweighted minus weighted respondents-only turnout, November 2020")
    for yr, r in ((2022, r22), (2024, r24)):
        fact(f"turnout_census_{yr}", r["census"], pct(r["census"]), n=r["n_counted"], weight=wt,
             source=src_voter(yr),
             estimand=(f"Share of {cvap} who reported voting in November {yr}, every positive-weight "
                       "citizen adult in the denominator (Census convention)"),
             benchmark=f"Census Bureau published {TURNOUT_PUBLISHED[yr]}% (external benchmark)")
        fact(f"turnout_recode_{yr}", r["recode"], pct(r["recode"]), n=int(r["n_counted"] - r["n_niu_counted"]),
             weight=wt, source=src_voter(yr),
             estimand=(f"Turnout in November {yr} computed from a recode that treats VOTED = 'Not in "
                       "universe' as structural, dropping supplement nonrespondents from the denominator"),
             note="The analysis store's voted_census behaved this way for 2022 and 2024 until its correction on 2026-09-10.")
        fact(f"turnout_niu_{yr}", r["n_niu_counted"], cnt(r["n_niu_counted"]), unit="records",
             weight=wt, variance="none", source=src_voter(yr),
             estimand=(f"Citizen adults with a positive supplement weight coded VOTED = 'Not in universe', "
                       f"November {yr}"))
        fact(f"turnout_nonresp_{yr}", r["nonresponse"], pct(r["nonresponse"]), n=r["n_counted"], weight=wt,
             source=src_voter(yr),
             estimand=(f"Weighted share of {cvap} with no answer to the voting question (including those "
                       f"coded 'Not in universe'), November {yr}"))
    pre = {yr: res[yr]["nonresponse"] for yr in years if yr <= 2020}
    lo_yr, hi_yr = min(pre, key=pre.get), max(pre, key=pre.get)
    fact("turnout_nonresp_low", pre[lo_yr], pct(pre[lo_yr]), n=res[lo_yr]["n_counted"], weight=wt,
         source=src_voter(lo_yr), estimand=f"Lowest weighted supplement nonresponse share among citizen adults, 2008-2020 ({lo_yr})")
    fact("turnout_nonresp_high", pre[hi_yr], pct(pre[hi_yr]), n=res[hi_yr]["n_counted"], weight=wt,
         source=src_voter(hi_yr), estimand=f"Highest weighted supplement nonresponse share among citizen adults, 2008-2020 ({hi_yr})")
    for yr, r in ((2022, r22), (2024, r24)):
        g = r["recode"] - r["census"]
        fact(f"turnout_recode_gap_{yr}", g, pts(g, 0), unit="percentage points", n=r["n_counted"],
             weight=wt, source=src_voter(yr),
             estimand=f"Label-trusting recode minus Census-convention turnout, November {yr} (whole points)")

    ledger("turnout_2020",
           title="What was turnout? (CPS November 2020)",
           target_population=f"{cvap}, November 2020",
           estimand="Share of that population who voted in the November 2020 election, as reported in the CPS",
           estimator=("Census convention: sum(w_i v_i) / sum(w_i) over every citizen adult with a "
                      "positive supplement weight, where v_i = 1 for a reported vote and 0 otherwise, "
                      "so supplement nonrespondents count as nonvoters. w = VOSUPPWT."),
           explicit_weights=("VOSUPPWT, identical on every record to WTFINL, the basic CPS final weight: "
                             "base weight, household noninterview adjustment, and calibration to "
                             "population controls. It carries no adjustment for supplement nonresponse."),
           implicit_weights=(f"None beyond w. The convention imputes 'did not vote' to the "
                             f"{pct(r20['nonresponse'])} (weighted) who did not answer; the respondents-"
                             "only alternative instead gives them zero weight, which assumes they vote like "
                             "respondents."),
           randomness="Sampling of housing units, household response to the CPS, and person response to the supplement.",
           variance_estimator=("Not computed: the extract carries no replicate weights or design variables "
                               "(weights-only tier); an SE from VOSUPPWT alone would not be design-based."),
           assumptions=("Supplement nonrespondents did not vote; respondents report their own voting "
                        "accurately. Both are assumptions, not data."),
           facts=["ch1.turnout_census_2020", "ch1.turnout_resp_2020", "ch1.turnout_nonresp_2020"])

    FIGURES["turnout_conventions"] = {
        "type": "table",
        "title": "What was turnout? Five answers per election",
        "subtitle": "Citizens 18 and older, CPS November supplements",
        "format": "pct1",
        "alt": ("Table of reported turnout by election, 2008 to 2024, under the Census convention, a "
                "recode that drops 'not in universe', respondents only (weighted), and respondents only "
                "(unweighted), next to the Census Bureau's published rate and the share who did not "
                "answer. The Census convention reproduces every published rate; the recode departs from "
                "it only in 2022 and 2024."),
        "source": ("IPUMS CPS November Voting and Registration Supplements, 2008-2024 (analysis/cps/cps_voter.parquet; "
                   "raw VOTED codes from parquet/cps/cps_voter.parquet)"),
        "note": ("Weights-only extract: point estimates only. Published rates: Census Bureau. From 2022 "
                 "supplement nonrespondents are coded 'Not in universe' but keep a positive weight."),
        "columns": [
            {"key": "election", "label": "Election", "align": "left"},
            {"key": "published", "label": "Census published", "format": "pct1", "align": "right"},
            {"key": "census", "label": "Everyone the weight counts", "format": "pct1", "align": "right"},
            {"key": "recode", "label": "Drop 'not in universe'", "format": "pct1", "align": "right"},
            {"key": "respondents", "label": "Respondents only", "format": "pct1", "align": "right"},
            {"key": "unweighted", "label": "Respondents, unweighted", "format": "pct1", "align": "right"},
            {"key": "nonresponse", "label": "Did not answer", "format": "pct1", "align": "right"},
        ],
        "rows": [
            {"election": str(yr), "published": rnd(TURNOUT_PUBLISHED[yr] / 100, 4),
             "census": rnd(res[yr]["census"]), "recode": rnd(res[yr]["recode"]),
             "respondents": rnd(res[yr]["respondents"]), "unweighted": rnd(res[yr]["unweighted"]),
             "nonresponse": rnd(res[yr]["nonresponse"])}
            for yr in years
        ],
    }


# =========================================================================== food security
def build_foodsec() -> None:
    df = query(f"""
        SELECT SERIAL, PERNUM, AGE, food_insecure, FSSUPPWTH, FSSUPPWT, FSHWTSCALE, HWTFINL
        FROM read_parquet({sq(FOODSEC)}) WHERE YEAR = 2023 AND MONTH = 12 ORDER BY SERIAL, PERNUM""")
    INPUTS.append({"path": "analysis/cps/cps_foodsec.parquet", "rows": df.height,
                   "note": "YEAR = 2023, MONTH = 12 (December 2023 Food Security Supplement)"})
    kids = df.group_by("SERIAL").agg((pl.col("AGE") < 18).any().alias("has_child"),
                                     pl.len().alias("m_all"))
    df = df.join(kids, on="SERIAL", how="left").sort(["SERIAL", "PERNUM"])
    fi = df["food_insecure"].fill_null(-1).to_numpy()
    valid = fi >= 0
    pernum = df["PERNUM"].to_numpy()
    age = df["AGE"].to_numpy()
    wh = df["FSSUPPWTH"].to_numpy().astype(float)
    wp = df["FSSUPPWT"].to_numpy().astype(float)
    wsc = df["FSHWTSCALE"].to_numpy().astype(float)
    wbm = df["HWTFINL"].to_numpy().astype(float)
    has_child = df["has_child"].to_numpy()

    hh_all = (pernum == 1) & (wh > 0)
    hh = hh_all & valid
    per = valid & (wp > 0)
    child = per & (age < 18)
    adult = per & (age >= 18)
    y = np.where(valid, fi, 0).astype(float)

    def wm(wt, m):
        return float(np.sum(wt[m] * y[m]) / np.sum(wt[m]))

    est = {
        "hh_fssuppwth": wm(wh, hh), "hh_fshwtscale": wm(wsc, hh), "hh_hwtfinl": wm(wbm, hh),
        "hh_unweighted": float(np.mean(y[hh])), "persons": wm(wp, per), "children": wm(wp, child),
        "adults": wm(wp, adult), "hh_with_children": wm(wh, hh & has_child),
        "hh_without_children": wm(wh, hh & ~has_child),
    }
    n = {"hh": int(hh.sum()), "hh_all": int(hh_all.sum()), "persons": int(per.sum()),
         "children": int(child.sum()), "adults": int(adult.sum()),
         "hh_with_children": int((hh & has_child).sum()), "hh_without_children": int((hh & ~has_child).sum())}
    counts = {"hh_fi_m": float(np.sum(wh[hh] * y[hh]) / 1e6), "hh_total_m": float(np.sum(wh[hh]) / 1e6),
              "people_fi_m": float(np.sum(wp[per] * y[per]) / 1e6),
              "children_fi_m": float(np.sum(wp[child] * y[child]) / 1e6),
              "adults_fi_m": float(np.sum(wp[adult] * y[adult]) / 1e6)}
    assert float(np.max(np.abs(wsc[hh] - wh[hh]))) == 0.0, "FSHWTSCALE should equal FSSUPPWTH in 2023"

    sql = query_row(f"""
        WITH t AS (SELECT * FROM read_parquet({sq(FOODSEC)}) WHERE YEAR = 2023 AND MONTH = 12)
        SELECT
          (SELECT SUM(FSSUPPWTH * food_insecure) / SUM(FSSUPPWTH) FROM t WHERE PERNUM = 1 AND FSSUPPWTH > 0 AND food_insecure IS NOT NULL),
          (SELECT SUM(HWTFINL * food_insecure) / SUM(HWTFINL) FROM t WHERE PERNUM = 1 AND FSSUPPWTH > 0 AND food_insecure IS NOT NULL),
          (SELECT AVG(food_insecure) FROM t WHERE PERNUM = 1 AND FSSUPPWTH > 0 AND food_insecure IS NOT NULL),
          (SELECT SUM(FSSUPPWT * food_insecure) / SUM(FSSUPPWT) FROM t WHERE FSSUPPWT > 0 AND food_insecure IS NOT NULL),
          (SELECT SUM(FSSUPPWT * food_insecure) / SUM(FSSUPPWT) FROM t WHERE FSSUPPWT > 0 AND food_insecure IS NOT NULL AND AGE < 18)""")
    for k, v in zip(["hh_fssuppwth", "hh_hwtfinl", "hh_unweighted", "persons", "children"], sql):
        agree(est[k], v, 1e-9, f"foodsec {k} numpy vs SQL")

    # the unit changes the implicit weights: size-weighted household rates for NOTES
    m_valid = df.filter(pl.col("food_insecure").is_not_null() & (pl.col("FSSUPPWT") > 0)).group_by("SERIAL").agg(
        pl.len().alias("m"), (pl.col("AGE") < 18).sum().alias("k"))
    hhdf = df.filter((pl.col("PERNUM") == 1) & (pl.col("FSSUPPWTH") > 0) & pl.col("food_insecure").is_not_null()).join(
        m_valid, on="SERIAL", how="left").fill_null(0)
    hw, hy = hhdf["FSSUPPWTH"].to_numpy().astype(float), hhdf["food_insecure"].to_numpy().astype(float)
    hm, hk = hhdf["m"].to_numpy().astype(float), hhdf["k"].to_numpy().astype(float)
    rate_size = float(np.sum(hw * hm * hy) / np.sum(hw * hm))
    rate_kids = float(np.sum(hw * hk * hy) / np.sum(hw * hk))
    fact("fs_hh_rate_size_weighted", rate_size, pct(rate_size, 2), n=n["hh"],
         weight="FSSUPPWTH times household members", source=SRC_FS,
         estimand=("Household food-insecurity rate reweighted by the number of household members with a status: "
                   "the implicit weight a person-level rate places on each household"))
    fact("fs_hh_rate_child_weighted", rate_kids, pct(rate_kids, 2), n=n["hh_with_children"],
         weight="FSSUPPWTH times children under 18", source=SRC_FS,
         estimand=("Household food-insecurity rate reweighted by the number of children in the household: the "
                   "implicit weight a child-level rate places on each household"))
    DIAG["foodsec_counts_million"] = {k: round(v, 3) for k, v in counts.items()}
    DIAG["foodsec_n"] = n

    wh_, wp_ = "FSSUPPWTH", "FSSUPPWT"
    defn = "food insecure (low or very low food security over the previous 12 months, USDA definition)"
    fact("fs_hh_rate", est["hh_fssuppwth"], pct(est["hh_fssuppwth"], 2), n=n["hh"], weight=wh_, source=SRC_FS,
         estimand=f"Share of U.S. households {defn}, December 2023 supplement",
         benchmark=f"USDA ERS published {USDA['hh_pct']}% of households (external benchmark)")
    fact("fs_hh_fshwtscale", est["hh_fshwtscale"], pct(est["hh_fshwtscale"], 2), n=n["hh"], weight="FSHWTSCALE",
         source=SRC_FS, estimand=f"Share of U.S. households {defn}, weighted by the food security scale weight",
         note="FSHWTSCALE equals FSSUPPWTH on every 2023 household record; it differs only in 1998, 1999, and 2007.")
    fact("fs_hh_hwtfinl", est["hh_hwtfinl"], pct(est["hh_hwtfinl"], 2), n=n["hh"], weight="HWTFINL",
         source=SRC_FS, estimand=f"Share of U.S. households {defn}, weighted by the basic monthly household weight")
    fact("fs_hh_unweighted", est["hh_unweighted"], pct(est["hh_unweighted"], 2), n=n["hh"], weight="none",
         source=SRC_FS, estimand="Unweighted share of interviewed households classified food insecure, December 2023")
    fact("fs_persons_rate", est["persons"], pct(est["persons"], 2), n=n["persons"], weight=wp_, source=SRC_FS,
         estimand="Share of people in the civilian noninstitutional population living in food-insecure households, 2023",
         benchmark=f"USDA ERS published {USDA['people_pct']}% of the population ({USDA['people_million']} million people) (external benchmark)")
    fact("fs_children_rate", est["children"], pct(est["children"], 2), n=n["children"], weight=wp_, source=SRC_FS,
         estimand="Share of children under 18 living in food-insecure households, 2023")
    fact("fs_adults_rate", est["adults"], pct(est["adults"], 2), n=n["adults"], weight=wp_, source=SRC_FS,
         estimand="Share of adults 18 and older living in food-insecure households, 2023")
    fact("fs_hh_with_children", est["hh_with_children"], pct(est["hh_with_children"], 2),
         n=n["hh_with_children"], weight=wh_, source=SRC_FS,
         estimand=f"Share of U.S. households with at least one member under 18 that are {defn}, 2023")
    fact("fs_hh_without_children", est["hh_without_children"], pct(est["hh_without_children"], 2),
         n=n["hh_without_children"], weight=wh_, source=SRC_FS,
         estimand=f"Share of U.S. households with no member under 18 that are {defn}, 2023")
    fact("fs_hh_n", n["hh"], cnt(n["hh"]), unit="households", variance="none", source=SRC_FS,
         estimand="Interviewed households with a food security status (householder records, positive FSSUPPWTH), December 2023")
    fact("fs_people_count", counts["people_fi_m"] * 1e6, f"{counts['people_fi_m']:.1f} million", unit="people",
         n=n["persons"], weight=wp_, source=SRC_FS, digits=0,
         estimand="Number of people living in food-insecure households, 2023 (weighted count)",
         benchmark=f"USDA ERS published {USDA['people_million']} million (external benchmark)")
    fact("usda_children_fi_children", USDA["children_in_hh_with_fi_children_pct"] / 100,
         f"{USDA['children_in_hh_with_fi_children_pct']}%", variance="none", source=USDA["source"],
         estimand=("Share of children living in households where at least one child was food insecure "
                   "(USDA's child-referenced measure), 2023"),
         note="Quoted from USDA for contrast; not computed in this chapter.")

    check("foodsec_households_vs_usda", "benchmark", round(100 * est["hh_fssuppwth"], 3), USDA["hh_pct"],
          USDA["source"], round(100 * est["hh_fssuppwth"], 1) == USDA["hh_pct"])
    check("foodsec_hh_sample_vs_usda", "benchmark", n["hh_all"], USDA["hh_sample"], USDA["source"],
          n["hh_all"] == USDA["hh_sample"],
          f"{n['hh']:,} with a food security status plus {n['hh_all'] - n['hh']} without")
    check("foodsec_fi_households_vs_usda", "benchmark", round(counts["hh_fi_m"], 3), USDA["hh_million"],
          USDA["source"], round(counts["hh_fi_m"], 1) == USDA["hh_million"])
    check("foodsec_people_rate_vs_usda", "benchmark", round(100 * est["persons"], 3), USDA["people_pct"],
          USDA["source"], round(100 * est["persons"], 1) == USDA["people_pct"])
    check("foodsec_people_count_vs_usda", "benchmark", round(counts["people_fi_m"], 3), USDA["people_million"],
          USDA["source"], round(counts["people_fi_m"], 1) == USDA["people_million"])
    check("foodsec_children_count_vs_usda", "benchmark", round(counts["children_fi_m"], 3),
          USDA["children_million"], USDA["source"], round(counts["children_fi_m"], 1) == USDA["children_million"],
          "USDA's child and adult counts may classify some household members differently; the people total matches.")
    check("foodsec_adults_count_vs_usda", "benchmark", round(counts["adults_fi_m"], 3), USDA["adults_million"],
          USDA["source"], round(counts["adults_fi_m"], 1) == USDA["adults_million"])

    ledger("foodsec_households",
           title="Food insecurity among households, 2023 (CPS December Food Security Supplement)",
           target_population="U.S. households in the civilian noninstitutional population, December 2023",
           estimand=f"Share of households {defn}",
           estimator="sum(w_h y_h) / sum(w_h) over householder records (PERNUM = 1) with a status, w = FSSUPPWTH",
           explicit_weights="FSSUPPWTH, the supplement household weight: each household counts for the households it represents.",
           implicit_weights="None beyond w; every household counts once regardless of its size.",
           randomness="Sampling of housing units, household response to the CPS, and response to the supplement.",
           variance_estimator="Not computed: the extract carries no replicate weights or design variables (weights-only tier).",
           assumptions="The 18-item scale classifies households as USDA does; households with a missing status are ignorable.",
           facts=["ch1.fs_hh_rate", "ch1.fs_hh_unweighted"])
    ledger("foodsec_children",
           title="Children in food-insecure households, 2023 (CPS December Food Security Supplement)",
           target_population="Children under 18 in the U.S. civilian noninstitutional population, December 2023",
           estimand="Share of children living in households classified food insecure over the previous 12 months",
           estimator="sum(w_i y_h(i)) / sum(w_i) over children in households with a status, w = FSSUPPWT; y_h(i) is the status of child i's household",
           explicit_weights="FSSUPPWT, the supplement person weight: each child counts for the children he or she represents.",
           implicit_weights=("Relative to the household rate, each household enters in proportion to the "
                             "number of children in it; households without children drop out."),
           randomness="Sampling of housing units, household response to the CPS, and response to the supplement.",
           variance_estimator="Not computed: the extract carries no replicate weights or design variables (weights-only tier).",
           assumptions=("A household's classification applies to every child in it. USDA's child-referenced "
                        "measure, whether the children themselves were food insecure, is a different estimand."),
           facts=["ch1.fs_children_rate", "ch1.fs_persons_rate", "ch1.fs_hh_rate"])

    rows = [
        ("Households, unweighted", est["hh_unweighted"], "Households", "unweighted", n["hh"]),
        ("Households, FSSUPPWTH", est["hh_fssuppwth"], "Households", "weighted", n["hh"]),
        ("Households, FSHWTSCALE", est["hh_fshwtscale"], "Households", "weighted", n["hh"]),
        ("Households, HWTFINL", est["hh_hwtfinl"], "Households", "weighted", n["hh"]),
        ("People, FSSUPPWT", est["persons"], "People", "cat2", n["persons"]),
        ("Children, FSSUPPWT", est["children"], "People", "highlight", n["children"]),
    ]
    FIGURES["foodsec_units"] = {
        "type": "dot",
        "title": "One indicator, three units, four weights",
        "subtitle": "Food insecurity, CPS December 2023 Food Security Supplement",
        "format": "pct2",
        "x_label": "Share in food-insecure households",
        "domain": [0.10, 0.21],
        "reference": {"value": USDA["hh_pct"] / 100, "label": f"USDA published, households: {USDA['hh_pct']}%"},
        "alt": (f"Dot plot of food insecurity in 2023: {pct(est['hh_unweighted'], 2)} of households unweighted; "
                f"{pct(est['hh_fssuppwth'], 2)} with the supplement household weight, "
                f"{pct(est['hh_fshwtscale'], 2)} with the scale weight, {pct(est['hh_hwtfinl'], 2)} with the "
                f"basic monthly household weight; {pct(est['persons'], 2)} of people and "
                f"{pct(est['children'], 2)} of children live in food-insecure households."),
        "source": SRC_FS,
        "note": "Weights-only extract: point estimates only, no intervals. Reference line: USDA ERS (ERR-337).",
        "rows": [{"label": lab, "estimate": rnd(v), "group": g, "role": role, "n": nn}
                 for lab, v, g, role, nn in rows],
    }


# =========================================================================== CPS ASEC poverty
def sdr(y: np.ndarray, w: np.ndarray, R: np.ndarray) -> tuple[float, float, np.ndarray]:
    theta = float(np.sum(w * y) / np.sum(w))
    reps = (R.T @ y) / R.sum(axis=0)
    se = float(np.sqrt(SDR_SCALE * np.sum((reps - theta) ** 2)))
    return theta, se, reps


def build_poverty() -> None:
    repcols = [f"REPWTP{i}" for i in range(1, N_REPS + 1)]
    groups = {"all": "All people", "child": "Children under 18", "age65": "People 65 and older"}
    measures = {"official": "Official", "spm": "SPM"}
    res: dict[tuple, dict] = {}
    total_rows = 0
    for sy in range(2020, 2026):
        cy = sy - 1
        n_asec = query_row(f"SELECT COUNT(*) FROM read_parquet({sq(ASEC)}) WHERE YEAR = {sy}")[0]
        df = query(f"""
            SELECT a.SERIAL, a.PERNUM, a.AGE, a.ASECWT, a.POVERTY, a.SPMPOV,
                   {', '.join('r.' + c for c in repcols)}
            FROM read_parquet({sq(ASEC)}) a
            JOIN read_parquet({sq(REPWT)}) r
              ON a.YEAR = r.YEAR AND a.SERIAL = r.SERIAL AND a.PERNUM = r.PERNUM
            WHERE a.YEAR = {sy} ORDER BY a.SERIAL, a.PERNUM""")
        assert df.height == n_asec, f"replicate join is not 1:1 in {sy}"
        total_rows += df.height
        df = df.with_columns(
            (pl.col("POVERTY") == 10).cast(pl.Float64).alias("poor_official"),  # POVERTY 10 = below poverty
            (pl.col("SPMPOV") == 1).cast(pl.Float64).alias("poor_spm"),         # SPMPOV 1 = below poverty (SPM)
        )
        age = df["AGE"].to_numpy()
        gmask = {"all": np.ones(df.height, dtype=bool), "child": age < 18, "age65": age >= 65}
        universe = {"official": df["POVERTY"].is_not_null().to_numpy(), "spm": df["SPMPOV"].is_not_null().to_numpy()}
        design = svy.Design(wgt="ASECWT", rep_wgts=svy.SdrWgts(prefix="REPWTP", n_reps=N_REPS))
        for mk in measures:
            ycol = f"poor_{mk}"
            for gk in groups:
                m = gmask[gk] & universe[mk]
                sub = df.filter(pl.Series(m)).select([ycol, "ASECWT", *repcols])
                e = svy.Sample(sub, design=design).estimation.mean(
                    ycol, method="replication", variance_center="estimate")
                row = e.to_polars().row(0, named=True)
                if e.method != "SDR" or int(row["df"]) != SDR_DF:
                    raise AssertionError(f"svy did not use the replicates: method={e.method}, df={row['df']}")
                y = sub[ycol].to_numpy().astype(float)
                w = sub["ASECWT"].to_numpy().astype(float)
                R = sub.select(repcols).to_numpy().astype(float)
                theta, se, reps = sdr(y, w, R)
                agree(row["est"], theta, 1e-12, f"svy vs hand estimate {sy} {mk} {gk}")
                agree(row["se"], se, 1e-10, f"svy vs hand SE {sy} {mk} {gk}")
                if se / theta > 0.30:
                    raise AssertionError(f"CV above 0.30 for {sy} {mk} {gk}")
                res[(mk, gk, cy)] = {"est": theta, "se": se, "reps": reps, "n": int(m.sum()), "sy": sy}
        DIAG[f"asec_official_universe_excluded_{sy}"] = int((~universe["official"]).sum())
    INPUTS.append({"path": "analysis/cps/cps_asec/part_2020_2025.parquet", "rows": total_rows,
                   "note": "survey years 2020-2025 (income years 2019-2024); AGE, ASECWT, POVERTY, SPMPOV"})
    INPUTS.append({"path": "analysis/cps/cps_asec_repwt/part_2020_2025.parquet", "rows": total_rows,
                   "note": "REPWTP1-REPWTP160, joined 1:1 on YEAR, SERIAL, PERNUM"})

    def ci(v):
        return (v["est"] - T975 * v["se"], v["est"] + T975 * v["se"])

    def diff(a, b):
        est = a["est"] - b["est"]
        reps = a["reps"] - b["reps"]
        se = float(np.sqrt(SDR_SCALE * np.sum((reps - est) ** 2)))
        return {"est": est, "se": se, "n": min(a["n"], b["n"]), "sy": a["sy"]}

    for (mk, gk), pub in POV_PUBLISHED.items():
        for cy, v in pub.items():
            ours = res[(mk, gk, cy)]["est"]
            ok = None if v is None else round(100 * ours, 1) == v
            check(f"poverty_{mk}_{gk}_{cy}", "benchmark", round(100 * ours, 3), v, POV_SOURCE, ok,
                  "" if v is not None else "published value not verified this pass")

    tally = {}
    for mk in ("official", "spm"):
        cells = [(round(100 * res[(mk, gk, cy)]["est"], 1) == v, abs(100 * res[(mk, gk, cy)]["est"] - v))
                 for (m2, gk), pub in POV_PUBLISHED.items() if m2 == mk
                 for cy, v in pub.items() if v is not None]
        tally[mk] = (sum(ok for ok, _ in cells), len(cells), max(d for _, d in cells))
    for mk, label in (("official", "official"), ("spm", "SPM")):
        k, tot, _ = tally[mk]
        fact(f"pov_match_{mk}", k, f"{k} of {tot}", unit="published rates", variance="none", source=POV_SOURCE,
             estimand=(f"Census-published {label} poverty rates (all people, children, and 65 and older; income "
                       "years 2019-2024) that this chapter's estimates equal after rounding to one decimal"))
    gap_max = tally["spm"][2] / 100
    fact("pov_max_spm_gap", gap_max, pts(gap_max, 2), unit="percentage points", variance="none",
         source=POV_SOURCE,
         estimand="Largest absolute difference between this chapter's SPM rates and the published rates, 2019-2024")
    DIAG["asec_match_tally"] = {mk: (k, tot, round(d, 3)) for mk, (k, tot, d) in tally.items()}

    defs = {
        "official": ("in families whose pre-tax money income is below the official poverty threshold "
                     "(IPUMS POVERTY = 10, 'Below poverty')"),
        "spm": ("in SPM units whose resources after taxes, transfers, and necessary expenses are below "
                "the SPM threshold (SPMPOV = 1)"),
    }

    def pov_fact(key, mk, gk, cy, *, with_ci=True):
        v = res[(mk, gk, cy)]
        lo, hi = ci(v)
        pub = POV_PUBLISHED[(mk, gk)].get(cy)
        fact(key, v["est"], pct(v["est"]), n=v["n"], weight="ASECWT", variance=SDR160, se=v["se"],
             ci=(lo, hi) if with_ci else None, ci_display=pct_ci(lo, hi) if with_ci else None,
             df=SDR_DF, source=src_asec(v["sy"]),
             estimand=f"Share of {groups[gk].lower()} {defs[mk]}, income year {cy}",
             benchmark=None if pub is None else f"Census Bureau published {pub}% (external benchmark)")

    pov_fact("pov_off_all_2021", "official", "all", 2021)
    pov_fact("pov_spm_all_2021", "spm", "all", 2021)
    pov_fact("pov_off_child_2021", "official", "child", 2021)
    pov_fact("pov_spm_child_2021", "spm", "child", 2021)
    pov_fact("pov_off_65_2021", "official", "age65", 2021)
    pov_fact("pov_spm_65_2021", "spm", "age65", 2021)
    pov_fact("pov_spm_child_2020", "spm", "child", 2020)
    pov_fact("pov_spm_child_2022", "spm", "child", 2022)
    pov_fact("pov_off_65_2024", "official", "age65", 2024)
    pov_fact("pov_spm_65_2024", "spm", "age65", 2024)
    g21 = diff(res[("official", "child", 2021)], res[("spm", "child", 2021)])
    lo, hi = g21["est"] - T975 * g21["se"], g21["est"] + T975 * g21["se"]
    fact("pov_gap_child_2021", g21["est"], pts(g21["est"]), unit="percentage points", n=g21["n"],
         weight="ASECWT", variance=SDR160, se=g21["se"], ci=(lo, hi), ci_display=pts_ci(lo, hi), df=SDR_DF,
         source=src_asec(2022),
         estimand="Official minus SPM poverty rate, children under 18, income year 2021 (each in its own universe)")
    g24 = diff(res[("spm", "age65", 2024)], res[("official", "age65", 2024)])
    lo, hi = g24["est"] - T975 * g24["se"], g24["est"] + T975 * g24["se"]
    fact("pov_gap_65_2024", g24["est"], pts(g24["est"]), unit="percentage points", n=g24["n"],
         weight="ASECWT", variance=SDR160, se=g24["se"], ci=(lo, hi), ci_display=pts_ci(lo, hi), df=SDR_DF,
         source=src_asec(2025),
         estimand="SPM minus official poverty rate, people 65 and older, income year 2024")
    ge = {cy: res[("spm", "age65", cy)]["est"] - res[("official", "age65", cy)]["est"] for cy in range(2019, 2025)}
    DIAG["asec_65_spm_minus_official_by_cy"] = {cy: round(100 * v, 2) for cy, v in ge.items()}
    DIAG["asec_child_official_minus_spm_by_cy"] = {
        cy: round(100 * (res[("official", "child", cy)]["est"] - res[("spm", "child", cy)]["est"]), 2)
        for cy in range(2019, 2025)}
    DIAG["asec_gap_child_2021"] = (round(g21["est"], 6), round(g21["se"], 8))
    DIAG["asec_gap_65_2024"] = (round(g24["est"], 6), round(g24["se"], 8))
    DIAG["asec_by_cy"] = {f"{mk}_{gk}_{cy}": (round(100 * v["est"], 2), round(100 * v["se"], 3), v["n"])
                          for (mk, gk, cy), v in sorted(res.items())}

    ledger("poverty_child_2021",
           title="Child poverty in 2021 under two definitions (CPS ASEC 2022)",
           target_population="Children under 18 in the civilian noninstitutional population (ASEC universe), calendar year 2021",
           estimand=("Two estimands: the share of children in families whose pre-tax money income is below "
                     "the official threshold, and the share in SPM units whose resources after taxes, "
                     "transfers, and necessary expenses are below the SPM threshold"),
           estimator="sum(w_i y_i) / sum(w_i) over children in each measure's universe, w = ASECWT",
           explicit_weights="ASECWT, the ASEC person weight.",
           implicit_weights=(f"None beyond w. The universes differ slightly: the official measure excludes "
                             f"unrelated children under 15 ({DIAG['asec_official_universe_excluded_2022']} "
                             "records in 2022); the SPM includes them."),
           randomness="Sampling of housing units, household response, and ASEC supplement response.",
           variance_estimator=("Successive difference replication with the 160 person replicate weights: "
                               "Var = (4/160) sum_r (theta_r - theta)^2, df = 159, centred on the full-sample "
                               "estimate. svy 0.28 with method='replication' and variance_center='estimate', "
                               "checked against a hand computation and R survey 4.5."),
           assumptions=("IPUMS POVERTY reproduces the official measure (an open pipeline decision); SPMPOV "
                        "weighted by ASECWT reproduces Census SPM rates (the SPM weight is not in the store); "
                        "reported income and benefits are accurate enough for both measures."),
           facts=["ch1.pov_off_child_2021", "ch1.pov_spm_child_2021", "ch1.pov_gap_child_2021"])

    series = []
    for gk, gname, roles in (("child", "Children", ("cat1", "cat2")), ("age65", "65 and older", ("cat3", "cat4"))):
        for mk, role in zip(("official", "spm"), roles):
            pts_ = []
            for cy in range(2019, 2025):
                v = res[(mk, gk, cy)]
                lo, hi = ci(v)
                pts_.append({"x": cy, "y": rnd(v["est"]), "lo": rnd(lo), "hi": rnd(hi)})
            # Census: "SPM estimates for 2019 and beyond reflect the implementation of revised SPM
            # methodology"; SPMPOV in the 2020 ASEC matches the unrevised 2019 rate, so the SPM
            # series breaks between 2019 and 2020. The official series has no definitional break.
            segs = [pts_] if mk == "official" else [pts_[:1], pts_[1:]]
            series.append({"name": f"{gname}, {measures[mk]}", "role": role, "segments": segs})
    FIGURES["poverty_official_spm"] = {
        "type": "line",
        "title": "Two definitions of poverty, opposite verdicts by age",
        "subtitle": "Share in poverty by income year, CPS ASEC 2020-2025, with 95% replicate intervals",
        "format": "pct1",
        "x_label": "Income year",
        "y_label": "Share in poverty",
        "y_domain": [0, 0.20],
        "annotations": [{"x": 2021, "label": "Expanded Child Tax Credit"}],
        "alt": (f"Line chart, 2019 to 2024: child poverty is {pct(res[('official', 'child', 2021)]['est'])} under "
                f"the official measure but {pct(res[('spm', 'child', 2021)]['est'])} under the SPM in 2021, "
                f"while poverty among people 65 and older is higher under the SPM in every year "
                f"({pct(res[('spm', 'age65', 2024)]['est'])} versus {pct(res[('official', 'age65', 2024)]['est'])} in 2024)."),
        "source": ("IPUMS CPS ASEC 2020-2025 (analysis/cps/cps_asec/part_2020_2025.parquet); 95% intervals "
                   "from 160 SDR replicate weights, df = 159"),
        "note": ("Income year = survey year minus 1. The official measure uses IPUMS POVERTY (open pipeline "
                 "decision #8). The SPM lines break between 2019 and 2020: Census revised the SPM methodology "
                 "from the 2019 estimates onward, and the 2019 point here is SPMPOV as first released, which "
                 "matches the unrevised published rate. Estimates from 2020 on use 2020 Census-based population "
                 "controls."),
        "series": series,
    }
    val_rows = []
    for mk in ("official", "spm"):
        for gk in ("all", "child", "age65"):
            for cy in range(2019, 2025):
                v = res[(mk, gk, cy)]
                lo, hi = ci(v)
                pub = POV_PUBLISHED[(mk, gk)].get(cy)
                match = "not compared" if pub is None else ("yes" if round(100 * v["est"], 1) == pub else "no")
                val_rows.append({"measure": measures[mk], "group": groups[gk], "year": str(cy),
                                 "ours": rnd(v["est"]), "ci": pct_ci(lo, hi),
                                 "published": None if pub is None else rnd(pub / 100, 4), "match": match})
    FIGURES["poverty_validation"] = {
        "type": "table",
        "title": "Replication check against Census published poverty rates",
        "subtitle": "CPS ASEC 2020-2025 (income years 2019-2024)",
        "alt": ("Table comparing this chapter's official and SPM poverty rates for all people, children, "
                "and people 65 and older, 2019 to 2024, with 95% replicate intervals, against the Census "
                "Bureau's published rates, and whether they agree to one decimal."),
        "source": f"This chapter's build; published rates from {POV_SOURCE}",
        "note": ("'Agrees' means equal after rounding to one decimal. Published values marked blank were "
                 "not verified in this pass."),
        "columns": [
            {"key": "measure", "label": "Measure", "align": "left"},
            {"key": "group", "label": "Group", "align": "left"},
            {"key": "year", "label": "Income year", "align": "left"},
            {"key": "ours", "label": "This chapter", "format": "pct1", "align": "right"},
            {"key": "ci", "label": "95% interval", "align": "right"},
            {"key": "published", "label": "Census published", "format": "pct1", "align": "right"},
            {"key": "match", "label": "Agrees", "align": "left"},
        ],
        "rows": val_rows,
    }
    return res


# =========================================================================== R oracle
def run_r_oracle(res: dict, enabled: bool) -> None:
    if not enabled:
        check("r_survey_oracle", "oracle", None, None, "verify.R", None, "skipped (--no-r)")
        return
    if not RSCRIPT.exists():
        check("r_survey_oracle", "oracle", None, None, "verify.R", None, f"skipped: {RSCRIPT} not found")
        return
    SCRATCH.mkdir(exist_ok=True)
    out = SCRATCH / "verify_r.csv"
    proc = subprocess.run([str(RSCRIPT), str(HERE / "verify.R"), str(out)], capture_output=True, text=True,
                          timeout=900)
    if proc.returncode != 0:
        raise RuntimeError(f"verify.R failed:\n{proc.stdout}\n{proc.stderr}")
    with open(out, newline="", encoding="utf-8") as f:
        rows = {r["check"]: r for r in csv.DictReader(f)}
    ours = {
        "pov_off_child_2021": res[("official", "child", 2021)],
        "pov_spm_child_2021": res[("spm", "child", 2021)],
        "pov_spm_65_2021": res[("spm", "age65", 2021)],
    }
    g = res[("official", "child", 2021)]["est"] - res[("spm", "child", 2021)]["est"]
    greps = res[("official", "child", 2021)]["reps"] - res[("spm", "child", 2021)]["reps"]
    ours["pov_gap_child_2021"] = {"est": g, "se": float(np.sqrt(SDR_SCALE * np.sum((greps - g) ** 2)))}
    for name, v in ours.items():
        rr = rows[name]
        d_est = abs(float(rr["estimate"]) - v["est"])
        d_se = abs(float(rr["se"]) - v["se"])
        ok = d_est < 1e-10 and d_se < 1e-10 and int(float(rr["df"])) == SDR_DF
        check(f"r_survey_{name}", "oracle",
              {"estimate": rnd(v["est"], 10), "se": rnd(v["se"], 10)},
              {"estimate": rnd(float(rr["estimate"]), 10), "se": rnd(float(rr["se"]), 10), "df": int(float(rr["df"]))},
              f"R {rr['r_version']}, survey {rr['survey_version']}: svrepdesign(type = 'successive-difference', mse = TRUE)",
              ok, f"|diff| estimate {d_est:.1e}, SE {d_se:.1e}")
        assert ok, (name, d_est, d_se)


# =========================================================================== write
def dump(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, sort_keys=True, indent=2, ensure_ascii=False)
        f.write("\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-r", action="store_true", help="skip the R survey oracle")
    args = ap.parse_args()

    build_atus()
    build_turnout()
    build_foodsec()
    res = build_poverty()
    check("svy_vs_hand_sdr", "internal", "36 ASEC estimates and SEs", "tolerance 1e-12 / 1e-10",
          "build.py", True, "svy 0.28 replication path (df = 159) against a numpy SDR computation")
    run_r_oracle(res, not args.no_r)

    for p in FIG.glob("*.json"):
        p.unlink()
    dump({"key": KEY, "facts": FACTS}, ART / "facts.json")
    dump({"key": KEY, "ledgers": LEDGERS}, ART / "ledger.json")
    for k, g in FIGURES.items():
        dump(g, FIG / f"{k}.json")
    hashes = {p.relative_to(ART).as_posix(): sha(p)
              for p in sorted([ART / "facts.json", ART / "ledger.json", *FIG.glob("*.json")])}
    manifest = {
        "key": KEY, "slug": SLUG, "status": "draft", "code": "build.py",
        "inputs": INPUTS, "validation": VALIDATION,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "artifact_sha256": hashes,
        "software": {"python": platform.python_version(), "duckdb": duckdb.__version__,
                     "polars": pl.__version__, "numpy": np.__version__, "scipy": scipy.__version__,
                     "svy": getattr(svy, "__version__", "unknown")},
    }
    dump(manifest, ART / "manifest.json")

    n_diff = sum(v["result"] == "differs" for v in VALIDATION)
    print(f"{KEY}: {len(FACTS)} facts, {len(LEDGERS)} ledgers, {len(FIGURES)} figures, "
          f"{len(VALIDATION)} validation entries ({n_diff} differ)")
    for v in VALIDATION:
        if v["result"] == "differs":
            print(f"  differs: {v['id']}: ours {v['ours']} vs {v['reference']}  {v['note']}")
    print(json.dumps(DIAG, indent=1, default=str))


if __name__ == "__main__":
    main()
