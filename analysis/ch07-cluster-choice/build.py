#!/usr/bin/env python
"""
Chapter 7 (key ch7): Which cluster? The variance menu in fixest, checked by simulation.

    python build.py            regenerate artifacts/ from _scratch/sim_results.json
    python build.py --run      run sim.R first (about 10 minutes at 1,000 replications)

No survey microdata is involved. sim.R (R + fixest) simulates six designs in which the
source of variation is fixed by construction and scores every candidate `vcov`
argument by how often a nominal 5% test rejects a true null. This script turns
sim.R's JSON into the chapter's artifacts and cross-checks the opening draw's
standard errors against pyfixest, recording the comparison in manifest.validation.

Deterministic: sim.R seeds every design; this script adds no randomness.
Only manifest.json carries a timestamp.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
FIG = ART / "figures"
SCR = HERE / "_scratch"
RESULTS = SCR / "sim_results.json"
OPENING_CSV = SCR / "opening_draw.csv"
RSCRIPT = r"C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe"

KEY, SLUG = "ch7", "ch07-cluster-choice"
TIMES, EN, MINUS = "\u00d7", "\u2013", "\u2212"

# ------------------------------------------------------------------ design metadata
DESIGNS = {
    "exp_individual": {
        "short": "Experiment, students randomized",
        "label": "D0a: experiment, treatment assigned student by student",
        "right": {"hetero"}, "valid": {"class", "school"},
    },
    "exp_classroom": {
        "short": "Experiment, classrooms randomized",
        "label": "D0b: experiment, treatment assigned to whole classrooms",
        "right": {"class"}, "valid": {"school"},
    },
    "moulton": {
        "short": "State-level regressor",
        "label": "D1: a regressor that varies only by state (Moulton)",
        "right": {"state"}, "valid": set(),
    },
    "did_g50": {
        "short": "DiD, 50 states, AR(1) shocks",
        "label": "D2a: difference-in-differences, 50 states, serially correlated state shocks",
        "right": {"state"}, "valid": {"twoway"},
    },
    "did_g10": {
        "short": "DiD, 10 states, AR(1) shocks",
        "label": "D2b: the same design with 10 states",
        "right": {"state"}, "valid": {"twoway"},
    },
    "twoway": {
        "short": "Region x industry cells",
        "label": "D3: region and industry shocks in both regressor and error",
        "right": {"twoway"}, "valid": set(),
    },
    "spatial": {
        "short": "Spatial lattice, 150 km range",
        "label": "D4: spatially correlated regressor and error on a lattice",
        "right": {"conley300"}, "valid": set(), "noisy": {"conley600"},
    },
    "common": {
        "short": "Panel, persistent common shocks",
        "label": "D5: panel with persistent common shocks in regressor and error",
        "right": {"dk"}, "valid": set(),
    },
}
VERDICT_TEXT = {
    "right": "matches the design",
    "valid": "valid, coarser or more conservative than needed",
    "wrong": "misses part of the dependence",
    "noisy": "cutoff too wide: the variance estimate is itself noisy",
}
ROLE = {"right": "highlight", "valid": "design", "wrong": "naive", "noisy": "muted"}
SOURCE = "Simulation: sim.R with R fixest (this chapter); no survey data"


def verdict(design: str, est: str) -> str:
    d = DESIGNS[design]
    if est in d["right"]:
        return "right"
    if est in d["valid"]:
        return "valid"
    if est in d.get("noisy", set()):
        return "noisy"
    return "wrong"


# ------------------------------------------------------------------ formatting
def fmt_pct1(p: float) -> str:
    return f"{100 * p:.1f}%"


def fmt_ratio(r: float) -> str:
    return f"{r:.1f}{TIMES}" if r >= 10 else f"{r:.2f}{TIMES}"


def fmt_num(v: float, nd: int) -> str:
    s = f"{abs(v):.{nd}f}"
    return (MINUS if v < 0 else "") + s


def fmt_int(n: int) -> str:
    return f"{n:,}"


def fmt_p(p: float) -> str:
    if p < 0.0001:
        return "< 0.0001"
    return f"{p:.4f}" if p < 0.01 else f"{p:.3f}"


def fact(value, display, estimand, *, unit=None, se=None, ci=None, df=None, n=None, variance="simulation",
         source=SOURCE, benchmark=None, note=""):
    ci_low, ci_high, ci_display = (None, None, None)
    if ci is not None:
        ci_low, ci_high, ci_display = ci
    return {
        "value": value, "display": display, "unit": unit,
        "se": se, "ci_low": ci_low, "ci_high": ci_high, "ci_display": ci_display, "df": df,
        "n": n, "weight": None, "variance": variance, "estimand": estimand, "source": source,
        "benchmark": benchmark, "note": note,
    }


def r4(x):
    return None if x is None else round(float(x), 4)


def r6(x):
    return None if x is None else round(float(x), 6)


# ------------------------------------------------------------------ pyfixest cross-check
def crosscheck(opening: dict) -> list[dict]:
    """Recompute the opening draw's standard errors with pyfixest; return validation records."""
    out = []
    try:
        import pandas as pd
        import pyfixest as pf
    except Exception as exc:  # pragma: no cover
        return [{"check": "pyfixest cross-check", "status": "SKIPPED", "detail": f"import failed: {exc}"}]
    if not OPENING_CSV.exists():
        return [{"check": "pyfixest cross-check", "status": "SKIPPED", "detail": "no _scratch/opening_draw.csv"}]
    d = pd.read_csv(OPENING_CSV)
    d["stateyear"] = d["state"].astype(str) + "_" + d["year"].astype(str)
    specs = {
        "iid": "iid",
        "hetero": "hetero",
        "stateyear": {"CRV1": "stateyear"},
        "twoway": {"CRV1": "state+year"},
        "state": {"CRV1": "state"},
    }
    fx = {e["key"]: e for e in opening["estimators"]}
    for k, v in specs.items():
        try:
            fit = pf.feols("y ~ d | state + year", data=d, vcov=v)
            se_py = float(fit.se().iloc[0])
            coef_py = float(fit.coef().iloc[0])
            se_r = fx[k]["se"]
            rel = abs(se_py - se_r) / se_r
            ok = rel < 1e-6 and abs(coef_py - opening["coef"]) < 1e-8
            out.append({
                "check": f"opening draw SE, {fx[k]['label']}",
                "status": "PASS" if ok else "DIFF",
                "fixest": round(se_r, 8), "pyfixest": round(se_py, 8), "rel_diff": float(f"{rel:.3g}"),
                "detail": f"pyfixest {pf.__version__}, vcov={v!r}; coefficient matches to {abs(coef_py - opening['coef']):.1e}",
            })
        except Exception as exc:
            out.append({"check": f"opening draw SE, {fx[k]['label']}", "status": "ERROR", "detail": str(exc)[:200]})
    return out


# ------------------------------------------------------------------ main
def main() -> None:
    if "--run" in sys.argv or not RESULTS.exists():
        print("running sim.R ...", flush=True)
        subprocess.run([RSCRIPT, str(HERE / "sim.R")], check=True, cwd=str(HERE))
    res = json.loads(RESULTS.read_text(encoding="utf-8"))
    reps = int(res["reps"])
    designs = res["designs"]
    opening = res["opening"]

    facts: dict[str, dict] = {}
    ART.mkdir(exist_ok=True)
    FIG.mkdir(exist_ok=True)

    # ---- constants
    facts["reps"] = fact(reps, fmt_int(reps), "Number of simulated data sets per design", unit="replications",
                         variance="none", note="Each design is drawn from its own fixed seed")
    mc_se = math.sqrt(0.05 * 0.95 / reps)
    facts["mc_se_at_5"] = fact(r4(mc_se), fmt_pct1(mc_se),
                               "Monte Carlo standard error of a rejection rate whose true value is 5%",
                               unit="percentage points", n=reps, variance="none")
    facts["fixest_version"] = fact(res["fixest_version"], res["fixest_version"], "fixest version used for every estimate",
                                   variance="none")

    # ---- the opening draw
    fx = {e["key"]: e for e in opening["estimators"]}
    se_iid = fx["iid"]["se"]
    facts["open_n"] = fact(opening["n_obs"], fmt_int(opening["n_obs"]),
                           "Observations in the opening data set (50 states, 20 years, 10 people per state-year)",
                           variance="none")
    facts["open_treated"] = fact(opening["treated_states"], str(opening["treated_states"]),
                                 "States that adopt the (placebo) policy in the opening data set", variance="none")
    facts["open_coef"] = fact(r4(opening["coef"]), fmt_num(opening["coef"], 3),
                              "Coefficient on the placebo policy indicator in the opening data set (true value 0)",
                              n=opening["n_obs"], variance="none")
    for k, e in fx.items():
        facts[f"open_se_{k}"] = fact(r6(e["se"]), fmt_num(e["se"], 3),
                                     f"Standard error of the opening coefficient, {e['label']} ({e['code']})",
                                     n=opening["n_obs"], variance="none")
        facts[f"open_ratio_{k}"] = fact(r4(e["se"] / se_iid), fmt_ratio(e["se"] / se_iid),
                                        f"Ratio of the {e['label']} standard error to the IID standard error, opening draw",
                                        unit="ratio", variance="none")
        facts[f"open_p_{k}"] = fact(r4(e["p"]), fmt_p(e["p"]),
                                    f"p-value for no effect under {e['label']}, opening draw (fixest reference distribution)",
                                    variance="none")
        facts[f"open_beta_{k}"] = fact(
            r4(opening["coef"]), fmt_num(opening["coef"], 3),
            f"Opening coefficient with its 95% interval under {e['label']}",
            se=r6(e["se"]), ci=(r4(e["ci_low"]), r4(e["ci_high"]), f"{fmt_num(e['ci_low'], 3)}{EN}{fmt_num(e['ci_high'], 3)}"),
            n=opening["n_obs"], variance="none")
    span = max(e["se"] for e in fx.values()) / min(e["se"] for e in fx.values())
    facts["open_span"] = fact(r4(span), fmt_ratio(span),
                              "Largest standard error divided by the smallest across the opening draw's vcov arguments",
                              unit="ratio", variance="none")

    # opening figure: SE relative to IID
    role_open = {"iid": "naive", "hetero": "naive", "stateyear": "naive", "twoway": "design", "state": "highlight", "dk": "cat1"}
    FIG.joinpath("opening_ratios.json").write_text(json.dumps({
        "type": "bar",
        "title": "One coefficient, six standard errors",
        "subtitle": "Placebo state policy in a simulated 50-state panel; standard error relative to the IID value",
        "alt": "Six horizontal bars: IID, HC1 and state-year clustering are near one; two-way and Driscoll-Kraay are larger; clustering by state is the largest, several times the IID value.",
        "format": "ratio2",
        "x_label": f"Standard error {TIMES} IID standard error",
        "rows": [{"label": e["label"], "value": r4(e["se"] / se_iid), "role": role_open.get(k, "muted")} for k, e in fx.items()],
        "source": SOURCE,
        "note": "Same data, same coefficient; only the vcov argument to feols changes.",
    }, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    # interactive menu explorer: the same options with what each assumes and the code in three languages
    MENU = {
        "iid": {
            "assumes": "Every observation is an independent draw with the same error variance. Ten people in the same state and year, and the same state in consecutive years, are treated as unrelated.",
            "verdict": "wrong",
            "r": 'feols(y ~ d | state + year, data = panel, vcov = "iid")', "arg_r": 'vcov = "iid"',
            "py": 'pf.feols("y ~ d | state + year", data=panel, vcov="iid")', "arg_py": 'vcov="iid"',
            "stata": "reghdfe y d, absorb(state year)", "arg_stata": "",
        },
        "hetero": {
            "assumes": "Error variances may differ across observations, but no two observations are correlated. Heteroskedasticity is not the problem in this design, so the number barely moves.",
            "verdict": "wrong",
            "r": 'feols(y ~ d | state + year, data = panel, vcov = "hetero")', "arg_r": 'vcov = "hetero"',
            "py": 'pf.feols("y ~ d | state + year", data=panel, vcov="hetero")', "arg_py": 'vcov="hetero"',
            "stata": "reghdfe y d, absorb(state year) vce(robust)", "arg_stata": "vce(robust)",
        },
        "stateyear": {
            "assumes": "People in the same state and year may be correlated in any way; a state's consecutive years are independent. Persistent state shocks and a policy that stays on violate this.",
            "verdict": "wrong",
            "r": "feols(y ~ d | state + year, data = panel, vcov = ~state^year)", "arg_r": "vcov = ~state^year",
            "py": 'pf.feols("y ~ d | state + year", data=panel, vcov={"CRV1": "state_year"})', "arg_py": 'vcov={"CRV1": "state_year"}',
            "stata": "egen state_year = group(state year)\nreghdfe y d, absorb(state year) vce(cluster state_year)", "arg_stata": "vce(cluster state_year)",
        },
        "twoway": {
            "assumes": "Observations may be correlated within a state across all years, and within a year across all states. Valid here; the year dimension adds little because year shocks are absorbed by the fixed effects.",
            "verdict": "valid",
            "r": "feols(y ~ d | state + year, data = panel, vcov = ~state + year)", "arg_r": "vcov = ~state + year",
            "py": 'pf.feols("y ~ d | state + year", data=panel, vcov={"CRV1": "state+year"})', "arg_py": 'vcov={"CRV1": "state+year"}',
            "stata": "reghdfe y d, absorb(state year) vce(cluster state year)", "arg_stata": "vce(cluster state year)",
        },
        "state": {
            "assumes": "Observations within a state may be correlated in any way across people and years; states are independent. The policy was assigned to states and the shocks persist within them: this is the design.",
            "verdict": "right",
            "r": "feols(y ~ d | state + year, data = panel, vcov = ~state)", "arg_r": "vcov = ~state",
            "py": 'pf.feols("y ~ d | state + year", data=panel, vcov={"CRV1": "state"})', "arg_py": 'vcov={"CRV1": "state"}',
            "stata": "reghdfe y d, absorb(state year) vce(cluster state)", "arg_stata": "vce(cluster state)",
        },
        "dk": {
            "assumes": "Correlation across all states within a year and across years up to the lag, through the period sums of the scores. Built for panels with long time dimensions and common shocks; 20 years is short for it.",
            "verdict": "noisy",
            "r": "feols(y ~ d | state + year, data = panel, vcov = DK(4) ~ year)", "arg_r": "vcov = DK(4) ~ year",
            "py": 'pf.feols("y ~ d | state + year", data=panel, vcov="DK", vcov_kwargs={"time_id": "year", "lag": 4})', "arg_py": 'vcov="DK", vcov_kwargs={"time_id": "year", "lag": 4}',
            "stata": "xtset state year\nxtscc y d i.year, fe lag(4)", "arg_stata": "xtscc ... lag(4)",
        },
    }
    menu_options = []
    for k, e in fx.items():
        m = MENU[k]
        menu_options.append({
            "key": k, "label": e["label"], "assumes": m["assumes"], "verdict": m["verdict"], "role": ROLE[m["verdict"]],
            "se": r6(e["se"]), "ratio": r4(e["se"] / se_iid), "ci_low": r4(e["ci_low"]), "ci_high": r4(e["ci_high"]), "p": r4(e["p"]),
            "se_display": fmt_num(e["se"], 3), "ratio_display": fmt_ratio(e["se"] / se_iid), "p_display": fmt_p(e["p"]),
            "ci_display": f"{fmt_num(e['ci_low'], 3)}{EN}{fmt_num(e['ci_high'], 3)}",
            "code": {"r": m["r"], "python": m["py"], "stata": m["stata"]},
            "arg": {"r": m["arg_r"], "python": m["arg_py"], "stata": m["arg_stata"]},
        })
    FIG.joinpath("vcov_menu.json").write_text(json.dumps({
        "type": "vcov-menu",
        "title": "One coefficient, one argument, six answers",
        "subtitle": "The opening panel: 50 states, 20 years, a placebo policy with a true effect of zero. Choose an estimator.",
        "alt": "Interactive: choosing a variance estimator shows its standard error, interval and p-value for the same coefficient, what it assumes, and the code in R, Python and Stata.",
        "format": "num3",
        "coef": r4(opening["coef"]), "coef_display": fmt_num(opening["coef"], 3), "truth": 0,
        "n_obs": opening["n_obs"], "states": opening["states"], "years": opening["years"], "treated_states": opening["treated_states"],
        "options": menu_options,
        "source": SOURCE,
        "note": "Ratios are relative to the IID standard error. Verdicts follow the design: the policy is assigned to states and state shocks persist across years.",
    }, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    # ---- rejection rates
    dot_rows, table_rows = [], []
    for dkey, d in designs.items():
        meta = DESIGNS[dkey]
        for e in d["estimators"]:
            v = verdict(dkey, e["key"])
            p = e["reject"]
            se = math.sqrt(max(p * (1 - p), 0.05 * 0.95 / 4) / reps)
            lo, hi = max(0.0, p - 1.96 * se), min(1.0, p + 1.96 * se)
            fk = f"rej_{dkey}_{e['key']}"
            facts[fk] = fact(r4(p), fmt_pct1(p),
                             f"Share of {fmt_int(reps)} simulated data sets in which a nominal 5% test rejected the true null; {meta['label']}; {e['label']} ({e['code']})",
                             unit="rejection rate", se=r4(se), ci=(r4(lo), r4(hi), f"{fmt_pct1(lo)}{EN}{fmt_pct1(hi)}"),
                             n=reps, note=VERDICT_TEXT[v])
            facts[f"ratio_{dkey}_{e['key']}"] = fact(
                r4(e["se_ratio_to_iid"]), fmt_ratio(e["se_ratio_to_iid"]),
                f"Mean ratio of the {e['label']} standard error to the IID standard error across replications; {meta['label']}",
                unit="ratio", n=reps)
            dot_rows.append({"label": e["label"], "group": meta["short"], "estimate": r4(p), "ci_low": r4(lo), "ci_high": r4(hi),
                             "role": ROLE[v], "n": reps})
            table_rows.append({"design": meta["short"], "estimator": e["label"], "code": e["code"],
                               "reject": r4(p), "ratio": r4(e["se_ratio_to_iid"]), "verdict": VERDICT_TEXT[v]})

    FIG.joinpath("rejection_rates.json").write_text(json.dumps({
        "type": "dot",
        "title": "How often a nominal 5% test rejects a true null",
        "subtitle": f"{fmt_int(reps)} simulated data sets per design; 95% Monte Carlo intervals",
        "alt": "Dot plot grouped by design. In every design the estimator that matches the source of variation sits near the 5% line; estimators that ignore part of the dependence sit far to the right, some above 50%.",
        "format": "pct1",
        "x_label": "Rejection rate of a nominal 5% test (true effect is zero)",
        "reference": {"value": 0.05, "label": "Nominal 5%"},
        "domain": [0, max(0.6, max(r["ci_high"] for r in dot_rows))],
        "rows": dot_rows,
        "source": SOURCE,
        "note": "Highlighted rows match the design; muted rows are valid but coarser than needed; the rest miss part of the dependence.",
    }, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    FIG.joinpath("rejection_table.json").write_text(json.dumps({
        "type": "table",
        "title": "The menu, scored",
        "subtitle": "Rejection rate of a nominal 5% test under a true null, and the mean standard error relative to IID",
        "alt": "Table of eight designs by their candidate vcov arguments with rejection rates and standard-error ratios.",
        "columns": [
            {"key": "design", "label": "Design", "align": "left"},
            {"key": "estimator", "label": "Estimator", "align": "left"},
            {"key": "code", "label": "fixest", "align": "left"},
            {"key": "reject", "label": "Rejects", "format": "pct1", "align": "right"},
            {"key": "ratio", "label": f"SE {TIMES} IID", "format": "ratio2", "align": "right"},
            {"key": "verdict", "label": "Verdict", "align": "left"},
        ],
        "rows": table_rows,
        "highlight_key": "reject",
        "source": SOURCE,
    }, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    # ---- design sizes and derived quantities
    ex = designs["exp_individual"]["extra"]
    facts["exp_n"] = fact(ex["students"], fmt_int(ex["students"]), "Students per simulated experiment (40 schools, 4 classrooms each, 25 students per classroom)", variance="none")
    facts["exp_classrooms"] = fact(ex["classrooms"], str(ex["classrooms"]), "Classrooms per simulated experiment", variance="none")
    mo = designs["moulton"]["extra"]
    facts["moulton_n"] = fact(designs["moulton"]["n_obs"], fmt_int(designs["moulton"]["n_obs"]), "Observations in the Moulton design (50 states, 200 people each)", variance="none")
    facts["moulton_icc"] = fact(r4(mo["icc"]), f"{mo['icc']:.2f}", "Intraclass correlation of the error within states in the Moulton design", variance="none")
    facts["moulton_pred"] = fact(r4(mo["moulton_factor"]), fmt_ratio(mo["moulton_factor"]),
                                 "Moulton factor predicted for the design: square root of 1 + (200 - 1) x 0.2, the ratio by which the IID standard error should be inflated",
                                 unit="ratio", variance="none")
    facts["did_n"] = fact(designs["did_g50"]["n_obs"], fmt_int(designs["did_g50"]["n_obs"]), "Observations in the 50-state difference-in-differences design (50 states, 20 years, 10 people per cell)", variance="none")
    facts["did10_n"] = fact(designs["did_g10"]["n_obs"], fmt_int(designs["did_g10"]["n_obs"]), "Observations in the 10-state difference-in-differences design", variance="none")
    facts["twoway_cells"] = fact(designs["twoway"]["n_obs"], fmt_int(designs["twoway"]["n_obs"]), "Region-by-industry cells (50 regions, 30 industries)", variance="none")
    facts["spatial_points"] = fact(designs["spatial"]["n_obs"], fmt_int(designs["spatial"]["n_obs"]), "Lattice points in the spatial design (40 by 40, half a degree apart)", variance="none")
    facts["common_n"] = fact(designs["common"]["n_obs"], fmt_int(designs["common"]["n_obs"]), "Observations in the common-shock panel (50 units, 400 periods)", variance="none")

    # ---- ledger
    ledger = {
        "simulation": {
            "title": "Six designs, one question: how often does a nominal 5% test reject a true null?",
            "target_population": "None. Each design is a synthetic data-generating process built so that the source of variation is known; the lab asks which variance estimator describes it",
            "estimand": "For each design and each candidate vcov argument, the probability that a 5% test of the true null (coefficient = 0) rejects, over repeated draws from the design",
            "estimator": f"Share of {fmt_int(reps)} independent draws in which fixest's p-value, under that vcov argument and its default small-sample corrections, is below 0.05",
            "explicit_weights": "None (unweighted OLS in every design)",
            "implicit_weights": "None beyond OLS",
            "randomness": "The design itself: new shocks, new assignment, new regressor in every draw; nothing is sampled from a real population",
            "variance_estimator": f"Monte Carlo: binomial standard error about {fmt_pct1(mc_se)} at a true rate of 5%",
            "assumptions": "The designs are stylized: Gaussian shocks, equal cluster sizes, AR(1) persistence, and an exponential spatial covariance. They fix the mechanism, not the magnitude, of each problem",
            "facts": ["ch7.reps", "ch7.mc_se_at_5", "ch7.rej_moulton_iid", "ch7.rej_moulton_state",
                      "ch7.rej_did_g50_state", "ch7.rej_twoway_twoway", "ch7.rej_spatial_conley300", "ch7.rej_common_dk"],
        }
    }

    # ---- validation and manifest
    validation = crosscheck(opening)
    validation.append({"check": "Moulton factor", "status": "INFO",
                       "predicted": round(mo["moulton_factor"], 3),
                       "mean_ratio_state_to_iid": round(next(e for e in designs["moulton"]["estimators"] if e["key"] == "state")["se_ratio_to_iid"], 3),
                       "detail": "sqrt(1 + (n_g - 1) rho) for a regressor constant within equal-sized clusters, versus the mean CRV1/IID ratio across replications"})
    manifest = {
        "key": KEY, "slug": SLUG,
        "inputs": [{"path": None, "rows": None, "note": "No survey data. Every number is simulated by sim.R (R " + res["r_version"] + ", fixest " + res["fixest_version"] + ")"}],
        "code": "build.py; sim.R",
        "software": {"R": res["r_version"], "fixest": res["fixest_version"], "ssc": res["ssc"]},
        "reps": reps, "alpha": res["alpha"],
        "designs": {k: {"n_obs": v["n_obs"], "seed": v["seed"], "seconds": v["seconds"], "extra": v["extra"]} for k, v in designs.items()},
        "validation": validation,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
    }

    (ART / "facts.json").write_text(json.dumps({"key": KEY, "facts": facts}, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (ART / "ledger.json").write_text(json.dumps({"key": KEY, "ledgers": ledger}, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    (ART / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(f"wrote {len(facts)} facts, 3 figures, 1 ledger; validation: " + ", ".join(v["status"] for v in validation))


if __name__ == "__main__":
    main()
