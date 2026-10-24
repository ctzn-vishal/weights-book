#!/usr/bin/env python
"""
Chapter 9 (key ch9): Can these data identify the quantity?

    python build.py

No microdata is read. Every number here is an algebraic consequence of facts that
Chapters 1 and 6 already export, so this script reads their artifacts and nothing else:

  ../ch01-estimands/artifacts/facts.json      2020 CPS turnout components by group
  ../ch06-clustering/artifacts/facts.json     expansion coefficient
  ../ch06-clustering/artifacts/figures/event_study.json   year-by-year coefficients

It computes
  (a) worst-case (Manski) bounds on 2020 turnout and on the White-Black gap, the gap
      under a common voting rate among nonrespondents, and the breakdown frontier:
      the pairs of nonrespondent voting rates at which the gap is zero;
  (b) for the Medicaid comparison, the identified set for the event-study effects
      under the Rambachan-Roth relative-magnitudes restriction, evaluated AT THE POINT
      ESTIMATES (no sampling uncertainty), and the breakdown value of M-bar.

What is deliberately NOT here (placeholders in the chapter): HonestDiD confidence sets
that add sampling uncertainty, and every planned replication (Mariel, Medicare at 65,
a randomized study, Angrist-Evans, the big-data paradox, validated turnout).

Deterministic: no randomness; only manifest.json carries a timestamp.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHAPTERS = HERE.parent
ART = HERE / "artifacts"
FIG = ART / "figures"

KEY, SLUG = "ch9", "ch09-identification"
EN, MINUS = "–", "−"

CH1_FACTS = CHAPTERS / "ch01-estimands" / "artifacts" / "facts.json"
CH6_FACTS = CHAPTERS / "ch06-clustering" / "artifacts" / "facts.json"
CH6_EVENT = CHAPTERS / "ch06-clustering" / "artifacts" / "figures" / "event_study.json"

SRC_CPS = ("Derived from Chapter 1 facts: IPUMS CPS, November 2020 Voting and Registration "
           "Supplement, weight VOSUPPWT (ch01-estimands/artifacts/facts.json)")
SRC_ACS = ("Derived from Chapter 6 artifacts: IPUMS USA, ACS 1-year samples 2011–2019, "
           "event-study coefficients clustered by state (ch06-clustering/artifacts)")


# ------------------------------------------------------------------ helpers
def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def r6(x: float) -> float:
    return round(float(x), 6)


def r4(x: float) -> float:
    return round(float(x), 4)


def fmt_pct1(p: float) -> str:
    return f"{100 * p:.1f}%"


def fmt_num(v: float, nd: int) -> str:
    s = f"{abs(v):.{nd}f}"
    return (MINUS if round(v, nd) < 0 else "") + s


def fact(value, display, estimand, *, source, unit=None, n=None, weight=None,
         variance="none", benchmark=None, note=""):
    return {
        "value": value, "display": display, "unit": unit,
        "se": None, "ci_low": None, "ci_high": None, "ci_display": None, "df": None,
        "n": n, "weight": weight, "variance": variance, "estimand": estimand,
        "source": source, "benchmark": benchmark, "note": note,
    }


def dump(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


# ------------------------------------------------------------------ (a) turnout bounds
def turnout(ch1: dict, validation: list) -> tuple[dict, dict]:
    facts: dict = {}
    figs: dict = {}
    groups = {
        "all": ("", "All citizen adults"),
        "white": ("_white", "Non-Hispanic White"),
        "black": ("_black", "Non-Hispanic Black"),
    }
    comp = {}
    for g, (sfx, label) in groups.items():
        census = ch1[f"turnout_census{sfx}_2020"]["value"]   # r*v : nonrespondents counted as nonvoters
        resp = ch1[f"turnout_resp{sfx}_2020"]["value"]       # v   : rate among those who answered
        nonresp = ch1[f"turnout_nonresp{sfx}_2020"]["value"]  # 1-r : weighted share with no answer
        n = ch1[f"turnout_census{sfx}_2020"]["n"]
        # identity: census convention = (1 - nonresponse) * respondent rate
        err = abs(census - (1 - nonresp) * resp)
        validation.append({
            "check": f"{label}: Census-convention rate equals (1 - nonresponse share) x respondents' rate",
            "abs_error": r6(err), "tolerance": 5e-6, "pass": err < 5e-6,
        })
        comp[g] = dict(label=label, lower=census, upper=census + nonresp, resp=resp, nonresp=nonresp, n=n)

    pop = "U.S. citizens 18 and older in the civilian noninstitutional population, not in the armed forces, November 2020"
    for g, c in comp.items():
        sfx = "" if g == "all" else f"_{g}"
        who = "" if g == "all" else f"{c['label']} "
        facts[f"turnout_upper{sfx}_2020"] = fact(
            r6(c["upper"]), fmt_pct1(c["upper"]),
            f"Upper worst-case bound on the share of {who}{pop} who reported voting: every person with no answer "
            f"to the voting question counted as a voter. The lower bound is the Census convention (Chapter 1).",
            source=SRC_CPS, n=c["n"], weight="VOSUPPWT", variance="none",
            note="A bound under an assumption about nonrespondents, not an estimate with sampling error. "
                 "Addresses missing answers only, not misreported votes or frame exclusions.")

    w, b = comp["white"], comp["black"]
    gap_census = w["lower"] - b["lower"]
    gap_lo = w["lower"] - b["upper"]
    gap_hi = w["upper"] - b["lower"]
    d_nr = b["nonresp"] - w["nonresp"]           # extra nonresponse among Black citizens
    gap_q1 = gap_census - d_nr                   # everyone without an answer voted, in both groups
    q_zero_common = gap_census / d_nr            # common rate at which the gap would be zero
    qb_at_qw0 = gap_census / b["nonresp"]
    qb_at_qwresp = (gap_census + w["nonresp"] * w["resp"]) / b["nonresp"]
    qw_max = (b["nonresp"] - gap_census) / w["nonresp"]

    chk = abs(gap_census - ch1["turnout_gap_race_census_2020"]["value"])
    validation.append({"check": "White-Black gap under the Census convention matches Chapter 1's fact",
                       "abs_error": r6(chk), "tolerance": 5e-6, "pass": chk < 5e-6})
    gap_resp = w["resp"] - b["resp"]
    chk = abs(gap_resp - ch1["turnout_gap_race_resp_2020"]["value"])
    validation.append({"check": "White-Black gap among respondents matches Chapter 1's fact",
                       "abs_error": r6(chk), "tolerance": 5e-6, "pass": chk < 5e-6})

    gap_pop = ("Non-Hispanic White minus non-Hispanic Black turnout among citizen adults, November 2020 "
               "(percentage points)")
    n_gap = w["n"] + b["n"]
    note_b = "A bound under assumptions about nonrespondents; no sampling uncertainty is attached."
    facts["gap_lower_2020"] = fact(r4(100 * gap_lo), fmt_num(100 * gap_lo, 1),
        f"{gap_pop}: lower worst-case bound (no White nonrespondent voted, every Black nonrespondent voted)",
        source=SRC_CPS, unit="percentage points", n=n_gap, weight="VOSUPPWT", note=note_b)
    facts["gap_upper_2020"] = fact(r4(100 * gap_hi), fmt_num(100 * gap_hi, 1),
        f"{gap_pop}: upper worst-case bound (every White nonrespondent voted, no Black nonrespondent voted)",
        source=SRC_CPS, unit="percentage points", n=n_gap, weight="VOSUPPWT", note=note_b)
    facts["gap_width_2020"] = fact(r4(100 * (gap_hi - gap_lo)), fmt_num(100 * (gap_hi - gap_lo), 1),
        f"{gap_pop}: width of the worst-case identified set, equal to the two groups' nonresponse shares added together",
        source=SRC_CPS, unit="percentage points", n=n_gap, weight="VOSUPPWT", note=note_b)
    facts["gap_common_all_voted_2020"] = fact(r4(100 * gap_q1), fmt_num(100 * gap_q1, 1),
        f"{gap_pop} if every nonrespondent in both groups voted: the smallest gap available when both groups' "
        f"nonrespondents are assumed to vote at one common rate",
        source=SRC_CPS, unit="percentage points", n=n_gap, weight="VOSUPPWT", note=note_b)
    facts["gap_zero_common_rate"] = fact(r6(q_zero_common), f"{100 * q_zero_common:.0f}%",
        "Common voting rate among both groups' nonrespondents at which the White-Black gap would be zero. "
        "Above 100%, so no common rate erases the gap.",
        source=SRC_CPS, n=n_gap, weight="VOSUPPWT", note=note_b)
    facts["gap_zero_black_rate_if_white_zero"] = fact(r6(qb_at_qw0), fmt_pct1(qb_at_qw0),
        "Voting rate among Black nonrespondents that would make the White-Black gap zero if no White nonrespondent voted",
        source=SRC_CPS, n=n_gap, weight="VOSUPPWT", note=note_b)
    facts["gap_zero_black_rate_if_white_resp"] = fact(r6(qb_at_qwresp), fmt_pct1(qb_at_qwresp),
        "Voting rate among Black nonrespondents that would make the White-Black gap zero if White nonrespondents "
        "voted at the rate of White respondents",
        source=SRC_CPS, n=n_gap, weight="VOSUPPWT", note=note_b)
    facts["gap_zero_white_rate_max"] = fact(r6(qw_max), fmt_pct1(qw_max),
        "Largest voting rate among White nonrespondents at which some voting rate among Black nonrespondents "
        "(at most 100%) still makes the gap zero",
        source=SRC_CPS, n=n_gap, weight="VOSUPPWT", note=note_b)

    # ---- figures
    xs = list(range(0, 101, 10))
    roles = {"all": "design", "white": "cat1", "black": "cat2"}
    figs["turnout_dial"] = {
        "type": "line",
        "title": "Turnout in 2020 depends on what is assumed about the people who gave no answer",
        "subtitle": "Implied turnout among citizen adults as the assumed voting rate of nonrespondents goes from none to all",
        "alt": ("Three straight rising lines, for all citizen adults, non-Hispanic White citizens, and non-Hispanic Black "
                "citizens. Each starts at the Census-convention rate when no nonrespondent is assumed to have voted and "
                "rises by that group's nonresponse share when all are assumed to have voted. The Black line is lowest at "
                "the left and rises fastest, because Black nonresponse is highest."),
        "format": "pct1",
        "x_label": "Assumed share of nonrespondents who voted (%)",
        "y_label": "Implied share of citizen adults who voted",
        "y_domain": [0.6, 0.9],
        "annotations": [{"x": 0, "label": "Census convention"}, {"x": 100, "label": "Every nonrespondent voted"}],
        "series": [
            {"name": comp[g]["label"], "role": roles[g],
             "segments": [[{"x": x, "y": r6(comp[g]["lower"] + comp[g]["nonresp"] * x / 100)} for x in xs]]}
            for g in ("white", "all", "black")
        ],
        "source": "IPUMS CPS, November 2020 Voting and Registration Supplement; weighted by VOSUPPWT; derived from Chapter 1's components",
        "note": ("Each line is an identity, not an estimate: observed weighted components plus an assumed rate. The "
                 "respondents-only convention sits where the assumed rate equals each group's own respondent rate. "
                 "Sampling error, misreported votes, and frame exclusions are not shown."),
    }

    def row(label, assume, gap):
        return {"scenario": label, "assumption": assume, "gap": r4(100 * gap)}
    figs["gap_scenarios"] = {
        "type": "table",
        "title": "The same file supports a White–Black turnout gap anywhere in a 34-point range until nonrespondents are described",
        "alt": ("Table of five assumptions about citizens who gave no answer to the 2020 voting question and the "
                "White-Black turnout gap each implies, from the lower worst-case bound through the respondents-only and "
                "Census conventions to the upper worst-case bound."),
        "columns": [
            {"key": "scenario", "label": "Scenario", "align": "left"},
            {"key": "assumption", "label": "What is assumed about people who gave no answer", "align": "left"},
            {"key": "gap", "label": "White − Black gap (pts)", "format": "num1", "align": "right"},
        ],
        "rows": [
            row("Lower worst case", "No White nonrespondent voted; every Black nonrespondent voted", gap_lo),
            row("Everyone voted", "Every nonrespondent in both groups voted", gap_q1),
            row("Respondents only", "Each group's nonrespondents voted at the rate of its respondents", gap_resp),
            row("Census convention", "No nonrespondent in either group voted", gap_census),
            row("Upper worst case", "Every White nonrespondent voted; no Black nonrespondent voted", gap_hi),
        ],
        "highlight_key": None,
        "source": "IPUMS CPS, November 2020 Voting and Registration Supplement; weighted by VOSUPPWT; derived from Chapter 1's components",
        "note": "Scenarios are assumptions applied to observed weighted components. None carries a sampling interval, and none addresses misreported votes.",
    }
    figs["gap_scenarios"].pop("highlight_key")

    # breakdown frontier: q_b that zeroes the gap, as a function of q_w
    fx = [x for x in range(0, 100, 5) if x / 100 <= qw_max]
    frontier = [{"x": x, "y": r4(100 * (gap_census + w["nonresp"] * x / 100) / b["nonresp"])} for x in fx]
    frontier.append({"x": r4(100 * qw_max), "y": 100.0})
    figs["gap_frontier"] = {
        "type": "line",
        "title": "Erasing the turnout gap requires Black nonrespondents to have voted far more often than White nonrespondents",
        "subtitle": "Voting rate among Black nonrespondents at which the 2020 White–Black gap is zero, for each assumed rate among White nonrespondents",
        "alt": ("A rising line that starts near 41 percent when no White nonrespondent voted and reaches 100 percent when "
                "about 85 percent of White nonrespondents voted. A second line marks equal rates in the two groups and lies "
                "below the first everywhere, so no common rate erases the gap."),
        "format": "num1",
        "x_label": "Assumed share of White nonrespondents who voted (%)",
        "y_label": "Share of Black nonrespondents who must have voted for a zero gap (%)",
        "y_domain": [0, 100],
        "series": [
            {"name": "Zero-gap frontier", "role": "highlight", "segments": [frontier]},
            {"name": "Equal rates", "role": "muted",
             "segments": [[{"x": 0, "y": 0.0}, {"x": 100, "y": 100.0}]]},
        ],
        "source": "IPUMS CPS, November 2020 Voting and Registration Supplement; weighted by VOSUPPWT; derived from Chapter 1's components",
        "note": "Above the frontier the gap reverses sign. The equal-rates line marks a common voting rate among both groups' nonrespondents. The frontier is an identity in the observed weighted components and carries no sampling interval.",
    }
    return facts, figs


# ------------------------------------------------------------------ (b) Medicaid: relative magnitudes at the point estimates
def medicaid(ch6: dict, event: dict, validation: list) -> tuple[dict, dict]:
    facts: dict = {}
    figs: dict = {}
    pts = {int(p["x"]): float(p["y"]) for p in event["series"][0]["segments"][0]}
    ref = 2013
    pre_years = sorted(y for y in pts if y <= ref)
    post_years = sorted(y for y in pts if y > ref)
    steps = [abs(pts[b_] - pts[a_]) for a_, b_ in zip(pre_years[:-1], pre_years[1:])]
    maxpre = max(steps)
    chk = abs(pts[2011] - ch6["lead_2011"]["value"]) + abs(pts[2019] - ch6["event_2019"]["value"])
    validation.append({"check": "Event-study figure coefficients match Chapter 6's lead_2011 and event_2019 facts to 4 decimals",
                       "abs_error": r6(chk), "tolerance": 2e-4, "pass": chk < 2e-4})

    # identified set for the effect k periods after the reference year: beta_k +/- k * Mbar * maxpre
    rows = []
    for y in post_years:
        k = y - ref
        rows.append({"year": str(y), "k": k, "coef": r4(pts[y]), "drift": r4(k * maxpre),
                     "breakdown": r4(abs(pts[y]) / (k * maxpre))})
    K = len(post_years)
    avg = sum(pts[y] for y in post_years) / K
    kbar = sum(y - ref for y in post_years) / K
    bd_avg = abs(avg) / (kbar * maxpre)
    rows.append({"year": f"Average, {post_years[0]}{EN}{post_years[-1]}", "k": None, "coef": r4(avg),
                 "drift": r4(kbar * maxpre), "breakdown": r4(bd_avg)})

    note = ("Evaluated at the point estimates: sampling uncertainty in the pre- and post-period coefficients is ignored, "
            "so the robust breakdown value is smaller. Two pre-period steps set the yardstick.")
    unit = "percentage points"
    facts["did_maxpre"] = fact(r4(maxpre), fmt_num(maxpre, 2),
        "Largest year-to-year change in the event-study gap before expansion (2011 to 2012, 2012 to 2013), percentage points",
        source=SRC_ACS, unit=unit, weight="PERWT", note=note)
    facts["did_avg_post"] = fact(r4(avg), fmt_num(avg, 1),
        "Simple average of the six event-study coefficients, 2014 to 2019, relative to 2013 (percentage points)",
        source=SRC_ACS, unit=unit, weight="PERWT",
        note="Unweighted across years; Chapter 6's pooled coefficient weights state-year cells by population.")
    for y, tag in ((2014, "2014"), (2019, "2019")):
        k = y - ref
        facts[f"did_breakdown_{tag}"] = fact(r4(abs(pts[y]) / (k * maxpre)), fmt_num(abs(pts[y]) / (k * maxpre), 2),
            f"Breakdown value of M-bar for the {y} effect: how many times the largest pre-period year-to-year change "
            f"each post-period step of the parallel-trends violation must reach before the identified set includes zero",
            source=SRC_ACS, weight="PERWT", note=note)
    facts["did_breakdown_avg"] = fact(r4(bd_avg), fmt_num(bd_avg, 2),
        "Breakdown value of M-bar for the average 2014 to 2019 effect under the relative-magnitudes restriction",
        source=SRC_ACS, weight="PERWT", note=note)
    for m in (2,):
        half = m * kbar * maxpre
        facts[f"did_set_m{m}_low"] = fact(r4(avg - half), fmt_num(avg - half, 1),
            f"Lower end of the identified set for the average 2014 to 2019 effect when M-bar = {m} (percentage points)",
            source=SRC_ACS, unit=unit, weight="PERWT", note=note)
        facts[f"did_set_m{m}_high"] = fact(r4(avg + half), fmt_num(avg + half, 1),
            f"Upper end of the identified set for the average 2014 to 2019 effect when M-bar = {m} (percentage points)",
            source=SRC_ACS, unit=unit, weight="PERWT", note=note)

    chk = abs(avg - ch6["beta"]["value"])
    validation.append({"check": "Simple average of post-period event-study coefficients against Chapter 6's pooled coefficient (informational)",
                       "abs_error": r6(chk), "tolerance": None, "pass": True})

    ms = [i * 0.5 for i in range(0, 9)]
    figs["medicaid_dial"] = {
        "type": "line",
        "title": "The Medicaid estimate keeps its sign until post-period drift reaches about three times the largest pre-period change",
        "subtitle": "Identified set for the average 2014–2019 effect as the allowed violation of parallel trends grows; evaluated at the point estimates",
        "alt": ("A horizontal centre line near minus 8 percentage points with an upper and a lower line fanning out from it "
                "as M-bar grows from 0 to 4. The upper line crosses zero just below M-bar equal to 3."),
        "format": "num1",
        "x_label": "M̄: allowed post-period step, as a multiple of the largest pre-period step",
        "y_label": "Average effect on the uninsured share, 2014–2019 (percentage points)",
        "annotations": [{"x": r4(bd_avg), "label": "Set reaches zero"}],
        "series": [
            {"name": "Upper end of set", "role": "muted",
             "segments": [[{"x": m, "y": r4(avg + m * kbar * maxpre)} for m in ms]]},
            {"name": "Exact parallel trends", "role": "design",
             "segments": [[{"x": m, "y": r4(avg)} for m in ms]]},
            {"name": "Lower end of set", "role": "muted",
             "segments": [[{"x": m, "y": r4(avg - m * kbar * maxpre)} for m in ms]]},
        ],
        "source": "IPUMS USA, ACS 1-year samples 2011–2019; PERWT-weighted event study from Chapter 6; relative-magnitudes restriction of Rambachan and Roth (2023)",
        "note": ("Point estimates only. The outer lines are the ends of the identified set given the estimated coefficients; they are not confidence "
                 "limits. Confidence sets that add sampling uncertainty are a planned addition."),
    }
    figs["medicaid_breakdown"] = {
        "type": "table",
        "title": "Later years tolerate less drift per year, because a violation has had longer to accumulate",
        "alt": ("Table of the six post-expansion years and their average: the event-study coefficient, the drift a "
                "violation could accumulate per unit of M-bar, and the breakdown value of M-bar, which falls from about "
                "6.7 in 2014 to about 2.0 in 2019."),
        "columns": [
            {"key": "year", "label": "Year", "align": "left"},
            {"key": "k", "label": "Years after 2013", "format": "int", "align": "right"},
            {"key": "coef", "label": "Coefficient (pts)", "format": "num1", "align": "right"},
            {"key": "drift", "label": "Drift allowed per unit of M̄ (pts)", "format": "num2", "align": "right"},
            {"key": "breakdown", "label": "Breakdown M̄", "format": "num2", "align": "right"},
        ],
        "rows": rows,
        "source": "IPUMS USA, ACS 1-year samples 2011–2019; PERWT-weighted event study from Chapter 6",
        "note": "Evaluated at the point estimates; sampling uncertainty would lower every breakdown value.",
    }
    return facts, figs


# ------------------------------------------------------------------ ledgers
def ledgers() -> dict:
    return {
        "turnout_bounds": {
            "title": "What the 2020 CPS identifies about turnout, and what it leaves to assumption",
            "target_population": "U.S. citizens 18 and older in the civilian noninstitutional population, not in the armed forces, November 2020; and the non-Hispanic White and non-Hispanic Black citizens among them",
            "estimand": "Share who reported voting; the White minus Black difference in that share",
            "identification": {
                "claim_type": "Descriptive, partially identified",
                "observed": "The weighted share who answered the voting question and the reported voting rate among them, by group",
                "assumption": "None for the bounds. The Census convention adds: no nonrespondent voted. The respondents-only convention adds: within each group, nonrespondents voted at the respondents' rate",
                "made_true_by": "Neither convention is made true by the design. The supplement weight does not adjust for people who skipped the voting questions",
                "without_assumption": "Turnout lies between the Census-convention rate and that rate plus the nonresponse share; the gap lies in an interval as wide as the two groups' nonresponse shares added together",
                "sensitivity": "The gap is zero only if Black nonrespondents voted at a much higher rate than White nonrespondents; no common rate erases it",
            },
            "estimator": "Identities in observed weighted components: lower bound r·v, upper bound r·v + (1 − r), where r is the share answering and v the rate among them",
            "explicit_weights": "VOSUPPWT (CPS Voting and Registration Supplement weight), equal to the basic monthly weight for every citizen adult it counts",
            "implicit_weights": "None",
            "randomness": "CPS sampling of households; not quantified here, because the extract carries no design information (Chapter 1)",
            "variance_estimator": "None attached. Bounds address missing answers; sampling intervals around each bound are a separate, planned addition",
            "assumptions": "Reported votes are taken at face value, although surveys overstate voting; people outside the CPS frame (institutions, active military) are outside every bound",
            "facts": [
                "ch1.turnout_census_2020", f"{KEY}.turnout_upper_2020",
                f"{KEY}.gap_lower_2020", f"{KEY}.gap_upper_2020", f"{KEY}.gap_common_all_voted_2020",
            ],
        },
        "medicaid_sensitivity": {
            "title": "Medicaid expansion and uninsurance: how much the conclusion leans on parallel trends",
            "target_population": "Civilian and military household population ages 19–64 with family income at or below 138% of the poverty threshold, in the 30 design states of Chapter 6, 2011–2019",
            "estimand": "Average effect of the January 2014 expansion on the uninsured share in the expansion cohort, 2014–2019",
            "identification": {
                "claim_type": "Causal by assumption, not by design",
                "observed": "State-year uninsured shares in the cohort and comparison states, before and after 2014",
                "assumption": "Parallel trends between cohort and comparison states; no anticipation; no spillovers across states",
                "made_true_by": "Argument. States chose expansion; nothing in the design makes the comparison states' trend the cohort's counterfactual",
                "without_assumption": "Unbounded. With the relative-magnitudes restriction, the identified set widens in proportion to M̄ and the years since 2013",
                "sensitivity": "At the point estimates the average effect's identified set reaches zero when each post-period step of the violation is about three times the largest pre-period step",
            },
            "estimator": "Year-by-year event-study coefficients from Chapter 6's PERWT-weighted regression with state and year fixed effects; identified sets formed as coefficient ± (years since 2013) × M̄ × (largest pre-period step)",
            "explicit_weights": "PERWT, as in Chapter 6",
            "implicit_weights": "As in Chapter 6; the average over years weights the six post-period coefficients equally",
            "randomness": "Not quantified in this calculation",
            "variance_estimator": "None. Evaluated at the point estimates; HonestDiD confidence sets that add state-clustered sampling uncertainty are planned",
            "assumptions": "The pre-period is informative about the size of post-period violations; only two pre-period steps are available, and both are estimated with error",
            "facts": [
                "ch6.beta", f"{KEY}.did_avg_post", f"{KEY}.did_maxpre",
                f"{KEY}.did_breakdown_avg", f"{KEY}.did_breakdown_2014", f"{KEY}.did_breakdown_2019",
            ],
        },
    }


# ------------------------------------------------------------------ main
def main() -> int:
    ch1 = load(CH1_FACTS)["facts"]
    ch6 = load(CH6_FACTS)["facts"]
    event = load(CH6_EVENT)
    validation: list = []

    f1, g1 = turnout(ch1, validation)
    f2, g2 = medicaid(ch6, event, validation)
    facts = {**f1, **f2}
    figs = {**g1, **g2}

    failed = [v for v in validation if not v["pass"]]
    if failed:
        raise SystemExit(f"validation failed: {failed}")

    dump(ART / "facts.json", {"key": KEY, "facts": facts})
    dump(ART / "ledger.json", {"key": KEY, "ledgers": ledgers()})
    if FIG.exists():
        for stale in FIG.glob("*.json"):
            if stale.stem not in figs:
                stale.unlink()
    for name, fig in figs.items():
        dump(FIG / f"{name}.json", fig)
    dump(ART / "manifest.json", {
        "key": KEY, "slug": SLUG, "code": "build.py",
        "inputs": [
            {"path": "book/chapters/ch01-estimands/artifacts/facts.json", "rows": None,
             "note": "2020 CPS turnout components by group (exported aggregates; no microdata read)"},
            {"path": "book/chapters/ch06-clustering/artifacts/facts.json", "rows": None,
             "note": "Expansion coefficient and event-study facts"},
            {"path": "book/chapters/ch06-clustering/artifacts/figures/event_study.json", "rows": None,
             "note": "Year-by-year event-study coefficients, 2011 to 2019"},
        ],
        "validation": validation,
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    print(f"{KEY}: {len(facts)} facts, {len(figs)} figures, {len(ledgers())} ledgers; "
          f"{len(validation)} validation checks passed")
    for k in sorted(facts):
        print(f"  {k:40s} {facts[k]['display']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
