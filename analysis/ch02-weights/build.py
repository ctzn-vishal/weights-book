#!/usr/bin/env python
"""Chapter 2 -- Where Survey Weights Come From (key ch2).

    python build.py      regenerates artifacts/ deterministically

Inputs (all read-only except _data/, which this chapter owns):
  _data/brfss2024_weights.parquet   the BRFSS 2024 weighting chain, pulled from the raw CDC
                                    file (BRFSS_2026/raw/2024.rds) by extract_brfss.R
  BRFSS_2026/cleaned/brfss_multi_rec.parquet   harmonized 2014-2024 file: coverage by year
                                    (its `iyear` is the survey-file year, not the interview year)
  BRFSS_2026/raw/codebooks/.../USCODE24_LLCP_082125.HTML   CDC's weighted percentages (benchmark)
  analysis/atus/atus_respondent.parquet                    ATUS 2023 (WT06)
  analysis/cps/cps_asec/part_2020_2025.parquet             CPS ASEC 2024 (ASECWT)
  analysis/cps/cps_voter.parquet                           CPS Voting 2020 (VOSUPPWT)
  analysis/cps/cps_foodsec.parquet                         CPS Food Security Dec 2023 (FSSUPPWTH)
  _scratch/r_check.json            written by verify.R (R `survey`); copied into the manifest

Conventions (CONTRACT section 5): proportions stored 0-1; `display` is exactly what the reader
sees; numeric work is done in numpy (deterministic summation order); JSON is written with
sort_keys=True, indent=2, ensure_ascii=False; only manifest.json carries a timestamp.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("NO_COLOR", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import polars as pl  # noqa: E402
import svy  # noqa: E402

HERE = Path(__file__).resolve().parent
IPUMS = HERE.parents[2]
BOX = HERE.parents[3]
ANALYSIS = IPUMS / "analysis"
ART = HERE / "artifacts"
FIG = ART / "figures"
SCRATCH = HERE / "_scratch"

EXTRACT = HERE / "_data" / "brfss2024_weights.parquet"
RAW_RDS = BOX / "BRFSS" / "BRFSS_2026" / "raw" / "2024.rds"
HARMONIZED = BOX / "BRFSS" / "BRFSS_2026" / "cleaned" / "brfss_multi_rec.parquet"
CODEBOOK = (BOX / "BRFSS" / "BRFSS_2026" / "raw" / "codebooks" / "codebook24_llcp-v2-508_extracted"
            / "USCODE24_LLCP_082125.HTML")
ATUS = ANALYSIS / "atus" / "atus_respondent.parquet"
ASEC = ANALYSIS / "cps" / "cps_asec" / "part_2020_2025.parquet"
VOTER = ANALYSIS / "cps" / "cps_voter.parquet"
FOODSEC = ANALYSIS / "cps" / "cps_foodsec.parquet"

SRC_BRFSS = "CDC BRFSS 2024 public file LLCP2024 (raw 2024.rds via extract_brfss.R)"
SRC_ATUS = "IPUMS ATUS 2023 (analysis/atus/atus_respondent.parquet)"
LONELY_RULE = "center"  # svy; = R survey.lonely.psu 'adjust', the rule in CDC's 2024 R example

FIPS = {1: "Alabama", 2: "Alaska", 4: "Arizona", 5: "Arkansas", 6: "California", 8: "Colorado",
        9: "Connecticut", 10: "Delaware", 11: "District of Columbia", 12: "Florida", 13: "Georgia",
        15: "Hawaii", 16: "Idaho", 17: "Illinois", 18: "Indiana", 19: "Iowa", 20: "Kansas",
        21: "Kentucky", 22: "Louisiana", 23: "Maine", 24: "Maryland", 25: "Massachusetts",
        26: "Michigan", 27: "Minnesota", 28: "Mississippi", 29: "Missouri", 30: "Montana",
        31: "Nebraska", 32: "Nevada", 33: "New Hampshire", 34: "New Jersey", 35: "New Mexico",
        36: "New York", 37: "North Carolina", 38: "North Dakota", 39: "Ohio", 40: "Oklahoma",
        41: "Oregon", 42: "Pennsylvania", 44: "Rhode Island", 45: "South Carolina",
        46: "South Dakota", 47: "Tennessee", 48: "Texas", 49: "Utah", 50: "Vermont",
        51: "Virginia", 53: "Washington", 54: "West Virginia", 55: "Wisconsin", 56: "Wyoming"}
TERRITORIES = {66: "Guam", 72: "Puerto Rico", 78: "US Virgin Islands"}

VALIDATION: list[dict] = []


# ------------------------------------------------------------------ formatting helpers
def rnd(x, sig: int = 10):
    """Round to `sig` significant digits so JSON is stable against last-bit noise."""
    if x is None:
        return None
    if isinstance(x, (int, np.integer)):
        return int(x)
    x = float(x)
    if x == 0 or not np.isfinite(x):
        return x
    return float(f"{x:.{sig}g}")


def pct(p: float, d: int = 1) -> str:
    return f"{100 * p:.{d}f}%"


def intc(n) -> str:
    return f"{int(round(float(n))):,}"


def num(x: float, d: int = 1) -> str:
    return f"{x:,.{d}f}"


def million(x: float, d: int = 1) -> str:
    return f"{x / 1e6:,.{d}f} million"


def ci_pct(lo: float, hi: float, d: int = 1) -> str:
    return f"{100 * lo:.{d}f}%–{100 * hi:.{d}f}%"


FACTS: dict[str, dict] = {}


def fact(key: str, value, display: str, estimand: str, source: str, *, unit=None, se=None,
         ci_low=None, ci_high=None, ci_display=None, df=None, n=None, weight=None,
         variance=None, benchmark=None, note: str = "") -> None:
    assert key not in FACTS, key
    FACTS[key] = {
        "value": rnd(value) if isinstance(value, (float, np.floating)) else value,
        "display": display, "unit": unit, "se": rnd(se), "ci_low": rnd(ci_low),
        "ci_high": rnd(ci_high), "ci_display": ci_display,
        "df": int(df) if df is not None else None,
        "n": int(n) if n is not None else None, "weight": weight, "variance": variance,
        "estimand": estimand, "source": source, "benchmark": benchmark, "note": note,
    }


def check(name: str, ok: bool, detail: str) -> None:
    VALIDATION.append({"check": name, "result": "pass" if ok else "FAIL", "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + " -- " + detail)
    if not ok:
        raise SystemExit(f"validation failed: {name}")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, sort_keys=True, indent=2, ensure_ascii=False)
        fh.write("\n")


# ------------------------------------------------------------------ weight statistics
def wmean(y: np.ndarray, w: np.ndarray) -> float:
    return float(np.dot(w, y) / w.sum())


def cv_w(w: np.ndarray) -> float:
    return float(w.std() / w.mean())  # population SD, as in Kish's formula


def n_kish(w: np.ndarray) -> float:
    return float(w.sum() ** 2 / np.dot(w, w))  # = n / (1 + CV^2)


def taylor_se_np(y, w, strata, lonely="adjust"):
    """Independent Taylor SE of a Hajek mean, stratified single-stage design with every
    respondent its own PSU (with-replacement approximation). Singleton strata: 'adjust'
    centres the lone PSU at the grand mean (0 here, since z sums to zero); 'remove' drops it."""
    W = w.sum()
    ybar = np.dot(w, y) / W
    z = w * (y - ybar) / W
    _, inv = np.unique(strata, return_inverse=True)
    nh = np.bincount(inv)
    zs = np.bincount(inv, weights=z)
    dev = z - (zs / nh)[inv]
    ss = np.bincount(inv, weights=dev * dev)
    multi = nh > 1
    var = float(np.sum(nh[multi] / (nh[multi] - 1) * ss[multi]))
    if lonely == "adjust":
        var += float(np.sum(zs[~multi] ** 2))
    return float(np.sqrt(var)), int((~multi).sum())


def svy_mean(frame: pl.DataFrame, wcol: str) -> dict:
    """FMD prevalence with svy's Taylor path: strata = _STSTR, PSU = (_STSTR, _PSU)."""
    s = svy.Sample(frame, design=svy.Design(stratum="str_key", psu="psu_key", wgt=wcol))
    n_single = len(s.singleton.detected())
    s = s.singleton.handle(LONELY_RULE)
    r = s.estimation.mean("fmd0", where=svy.col("valid") == 1, deff="wr")
    out = r.to_polars().to_dicts()[0]
    out["singletons"] = n_single
    return out


def rake(w0: np.ndarray, margins: list[np.ndarray], targets: list[np.ndarray],
         tol: float = 1e-9, max_iter: int = 5000) -> tuple[np.ndarray, int]:
    """Iterative proportional fitting. margins[m] holds an integer cell code per record;
    targets[m] the control total per code. Deterministic (numpy bincount)."""
    w = w0.astype(float).copy()
    for it in range(1, max_iter + 1):
        worst = 0.0
        for codes, tgt in zip(margins, targets):
            cur = np.bincount(codes, weights=w, minlength=len(tgt))
            f = np.divide(tgt, cur, out=np.ones_like(tgt), where=cur > 0)
            w *= f[codes]
            worst = max(worst, float(np.max(np.abs(f[cur > 0] - 1.0))))
        if worst < tol:
            return w, it
    raise RuntimeError("raking did not converge")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ================================================================== 1. BRFSS 2024
print("== BRFSS 2024")
raw = pl.read_parquet(EXTRACT)
check("brfss_rows", raw.height == 457670, f"{raw.height:,} records in LLCP2024")
N_FILE = raw.height

states_present = sorted(int(s) for s in raw["xstate"].unique().to_list())
missing_2024 = [f for f in FIPS if f not in states_present]
terr_present = [s for s in states_present if s in TERRITORIES]
check("brfss_coverage_2024", missing_2024 == [47] and terr_present == [66, 72, 78],
      "2024 public file: every state + DC except Tennessee (47); territories 66, 72, 78")

N_TERR = int(raw.filter(pl.col("xstate") > 56).height)
b = raw.filter(pl.col("xstate") <= 56)  # target: 49 states + DC
N_TARGET = b.height
check("brfss_target_jurisdictions", b["xstate"].n_unique() == 50,
      f"{b['xstate'].n_unique()} jurisdictions (49 states + DC), {N_TARGET:,} respondents")

b = b.with_columns(
    frame=pl.when(pl.col("qstver") < 20).then(pl.lit("landline")).otherwise(pl.lit("cell")),
    fmd=pl.when(pl.col("menthlth") == 88).then(0.0)
          .when((pl.col("menthlth") >= 1) & (pl.col("menthlth") <= 30))
          .then((pl.col("menthlth") >= 14).cast(pl.Float64))
          .otherwise(None),
    psu_key=pl.format("{}_{}", pl.col("xststr").cast(pl.Int64), pl.col("xpsu").cast(pl.Int64)),
    str_key=pl.col("xststr").cast(pl.Int64).cast(pl.Utf8),
)
b = b.with_columns(
    valid=pl.col("fmd").is_not_null().cast(pl.Int64),
    fmd0=pl.col("fmd").fill_null(0.0),
    fac=pl.when(pl.col("xdualuse") == 9).then(1.0).otherwise(pl.col("xdualcor")),
    phone=pl.when(pl.col("xdualuse") != 9).then(pl.lit("dual"))
            .when(pl.col("frame") == "landline").then(pl.lit("landline_only"))
            .otherwise(pl.lit("cell_only")),
)
b = b.with_columns(w_comp=pl.col("xwt2rake") * pl.col("fac"), w_one=pl.lit(1.0))

# frame consistency: landline-screener vs cell-screener variables
ll = b.filter(pl.col("frame") == "landline")
cp = b.filter(pl.col("frame") == "cell")
check("frame_screeners", (ll["ctelenm1"] == 1).all() and (cp["cellfon5"] == 1).all(),
      f"QSTVER<20 records answered the landline screener ({ll.height:,}); QSTVER>=20 the cell "
      f"screener ({cp.height:,})")

# outcome coding matches CDC's calculated _MENT14D
m14 = b.select(
    ok1=((pl.col("fmd") == 1) == (pl.col("xment14d") == 3)).all(),
    ok0=((pl.col("fmd") == 0) == pl.col("xment14d").is_in([1, 2])).all(),
    okn=(pl.col("fmd").is_null() == (pl.col("xment14d") == 9)).all(),
).row(0)
check("fmd_matches_ment14d", all(m14),
      "FMD (MENTHLTH>=14; 88=0; 77/99/blank missing) equals CDC's _MENT14D=3 on every record")

# ---- the chain: definitions verified against the data
# _RAWRAKE = min(NUMADULT,5) / min(phones,3) on the landline frame, 1 on the cell frame
cp_rr = bool((cp["xrawrake"] == 1.0).all())
llp = ll.with_columns(
    adults=pl.col("numadult").clip(upper_bound=5),
    phones=pl.when(pl.col("numhhol4") == 2).then(1.0)
             .when((pl.col("numhhol4") == 1) & (pl.col("numphon4") <= 6))
             .then(pl.col("numphon4").clip(upper_bound=3))
             .otherwise(None),
)
known = llp.filter(pl.col("phones").is_not_null())
unknown = llp.filter(pl.col("phones").is_null())
rr_known = float(((known["adults"] / known["phones"] - known["xrawrake"]).abs() < 1e-9).mean())
rr_unknown = float(((unknown["adults"] - unknown["xrawrake"]).abs() < 1e-9).mean())
check("rawrake_rebuilt", cp_rr and rr_known == 1.0 and rr_unknown == 1.0,
      f"_RAWRAKE = 1 for all {cp.height:,} cell-frame records; = min(NUMADULT,5)/min(phones,3) for "
      f"all {known.height:,} landline records with a phone count; unknown phone counts "
      f"({unknown.height:,}) are imputed as one phone")
N_LL_UNKNOWN_PHONES = unknown.height

rel = (b["xwt2rake"] / (b["xstrwt"] * b["xrawrake"]) - 1).abs()
bad = b.filter(rel > 1e-6)
check("wt2rake_identity",
      bad.height == 12 and bool((bad["xstate"] == 17).all()) and bool((bad["frame"] == "cell").all()),
      f"_WT2RAKE = _STRWT x _RAWRAKE on all but {bad.height} records (all Illinois cell-frame; their "
      "_WT2RAKE equals the _STRWT of a different Illinois stratum)")

dual = b.filter(pl.col("xdualuse") != 9)
dc = dual.group_by(["xstate", "frame"]).agg(pl.col("xdualcor").min().alias("mn"),
                                            pl.col("xdualcor").max().alias("mx"))
const_ok = bool(((dc["mx"] - dc["mn"]).abs() < 1e-12).all())
pairs = dc.pivot(index="xstate", on="frame", values="mn").with_columns(
    s=pl.col("landline") + pl.col("cell"))
pair_dev = float((pairs["s"] - 1).abs().max())
check("dualcor_compositing_pair", const_ok and pair_dev < 1e-9,
      f"_DUALCOR is one value per state and frame for dual users, and the landline and cell values "
      f"sum to 1 in every state (max |sum-1| = {pair_dev:.1e}): a compositing pair lambda, 1-lambda")

tot = b.group_by("xstate").agg(pl.col("xllcpwt2").sum().alias("l2"), pl.col("xllcpwt").sum().alias("f"))
ratio_l2 = (tot["l2"] / tot["f"]).to_numpy()
check("llcpwt2_population_scale", float(ratio_l2.min()) > 0.95 and float(ratio_l2.max()) < 1.05,
      f"state totals of _LLCPWT2 are {ratio_l2.min():.3f}-{ratio_l2.max():.3f} x those of _LLCPWT: the "
      "raking input is already on the population scale, a step the Overview does not describe")

# harmonized parquet agrees with the raw file for 2024
con = duckdb.connect()
h24 = con.execute(f"select count(*), sum(xllcpwt) from read_parquet('{HARMONIZED.as_posix()}') "
                  "where iyear = 2024").fetchone()
raw_sum = float(raw["xllcpwt"].to_numpy().sum())
check("harmonized_matches_raw", h24[0] == N_FILE and abs(h24[1] - raw_sum) / raw_sum < 1e-9,
      f"brfss_multi_rec.parquet iyear=2024: {h24[0]:,} rows, weight sum equal to the raw file; its "
      "iyear is the survey-file year (the raw IYEAR puts 19,553 of these interviews in 2025)")
n_iyear_2025 = int((raw["iyear"] == 2025).sum())

# ---- arrays for the analytic sample (valid FMD, 49 states + DC)
a = b.filter(pl.col("valid") == 1)
N_FMD = a.height
y = a["fmd"].to_numpy()
STAGES = [
    ("unweighted", "Unweighted", "none", "Each respondent counts once",
     "No weights", "w_one"),
    ("strwt", "Stratum weight", "_STRWT", "Inverse sampling fraction of telephone numbers in the stratum",
     "Rebuilt from public variables", "xstrwt"),
    ("wt2rake", "× adults ÷ phones", "_WT2RAKE", "Times adults in household (max 5) over landline numbers (max 3)",
     "Rebuilt from public variables", "xwt2rake"),
    ("composite", "× dual-frame factor", "_WT2RAKE × _DUALCOR", "Dual users split between the two frames",
     "Rebuilt from public variables", "w_comp"),
    ("llcpwt2", "Raking input", "_LLCPWT2", "Truncated within region; on the population scale",
     "Documented by CDC, not rebuildable", "xllcpwt2"),
    ("final", "Final weight", "_LLCPWT", "Raked to 8 or more state margins",
     "Documented by CDC, not rebuildable", "xllcpwt"),
]
stage = {}
for key, label, var, step, status, col in STAGES:
    w = a[col].to_numpy().astype(float)
    stage[key] = dict(label=label, var=var, step=step, status=status, col=col,
                      est=wmean(y, w), cv=cv_w(w), nk=n_kish(w), total=float(w.sum()))
    print(f"  stage {key:10s} FMD={stage[key]['est']:.5f} CV={stage[key]['cv']:.3f} "
          f"nKish={stage[key]['nk']:,.0f} total={stage[key]['total']:,.0f}")

# diagnostic: the same chain with every state's weights rescaled to its final-weight total, which
# separates within-state reweighting from the cross-state scale of the design-weight stages
st_a = np.unique(a["xstate"].to_numpy(), return_inverse=True)[1]
_fin_st = np.bincount(st_a, weights=a["xllcpwt"].to_numpy())
for key, *_r, col in STAGES:
    w = a[col].to_numpy().astype(float)
    w_sn = w * (_fin_st / np.bincount(st_a, weights=w))[st_a]
    stage[key]["est_sn"] = wmean(y, w_sn)
    print(f"  stage {key:10s} state-normalized FMD={stage[key]['est_sn']:.5f}")

# ---- design-based inference for the final estimate (svy) + two independent checks
t_final = svy_mean(b, "xllcpwt")
wf = a["xllcpwt"].to_numpy()
check("svy_point_vs_numpy", abs(t_final["est"] - stage["final"]["est"]) < 1e-9,
      f"svy Taylor point {t_final['est']:.10f} = numpy weighted mean {stage['final']['est']:.10f}")
se_np, n_single_np = taylor_se_np(y, wf, a["str_key"].to_numpy(), "adjust")
check("svy_se_vs_numpy", abs(se_np / t_final["se"] - 1) < 1e-4,
      f"svy SE {t_final['se']:.10f} vs independent numpy Taylor SE {se_np:.10f} (relative gap "
      f"{abs(se_np / t_final['se'] - 1):.1e}); svy detects {t_final['singletons']} singleton strata in the "
      f"declared design, numpy finds {n_single_np} among respondents with a valid answer")
se_np_rm, _ = taylor_se_np(y, wf, a["str_key"].to_numpy(), "remove")
N_STRATA = int(b["str_key"].n_unique())
N_SINGLE = int(t_final["singletons"])
DF = int(t_final["df"])

r_check_path = SCRATCH / "r_check.json"
if r_check_path.exists():
    rc = json.loads(r_check_path.read_text(encoding="utf-8"))
    rf = rc["fmd_final_adjust"]
    ok = (abs(rf["estimate"] - t_final["est"]) < 1e-9 and abs(rf["se"] / t_final["se"] - 1) < 1e-3
          and abs(rf["deff"] / t_final["deff"] - 1) < 1e-2)
    check("r_survey_final", ok,
          f"{rc['engine']}: estimate {rf['estimate']:.8f}, SE {rf['se']:.8f} (na.rm domain, 'adjust'), "
          f"DEFF {rf['deff']:.4f}, df {rf['df']:,}; svy: SE {t_final['se']:.8f}, DEFF "
          f"{t_final['deff']:.4f}, df {DF:,}. R with lonely.psu='fail' stopped: {rc['fail_rule_message'][:120]}")
else:
    rc = None
    VALIDATION.append({"check": "r_survey_final", "result": "not run",
                       "detail": "run verify.R, then build.py again"})

# codebook benchmark: CDC's own weighted percentage for _MENT14D = 3 (all records, missing included)
cb = html.unescape(re.sub(r"<[^>]+>", " ", CODEBOOK.read_text(encoding="latin-1")))
cb = re.sub(r"\s+", " ", cb.replace("\xa0", " "))
mcb = re.search(r"SAS Variable Name: _MENT14D\b.*?\b3 14\+ days when mental health not good "
                r"([\d,]+) ([\d.]+) ([\d.]+)", cb)
assert mcb, "could not parse _MENT14D from the codebook"
cb_pct = float(mcb.group(3)) / 100
wall = raw["xllcpwt"].to_numpy()
ours_all = float(np.dot(wall, (raw["xment14d"] == 3).to_numpy().astype(float)) / wall.sum())
check("codebook_ment14d", abs(ours_all - cb_pct) < 0.00005,
      f"weighted share with _MENT14D=3 over all {N_FILE:,} records = {100 * ours_all:.3f}% vs codebook "
      f"{100 * cb_pct:.2f}%")

# ---- facts: the headline
unw = stage["unweighted"]["est"]
fin = stage["final"]["est"]
fact("brfss_n_file", N_FILE, intc(N_FILE), "Records in the 2024 BRFSS public file (LLCP2024), all jurisdictions",
     SRC_BRFSS, unit="respondents", n=N_FILE)
fact("brfss_n_terr", N_TERR, intc(N_TERR),
     "Records from Guam, Puerto Rico, and the US Virgin Islands, excluded from the target", SRC_BRFSS,
     unit="respondents", n=N_TERR)
fact("brfss_n_target", N_TARGET, intc(N_TARGET),
     "Respondents in the 49 states and DC that released 2024 BRFSS data", SRC_BRFSS,
     unit="respondents", n=N_TARGET)
fact("brfss_n_fmd", N_FMD, intc(N_FMD),
     "Respondents in the target with a valid answer to MENTHLTH (0-30 days)", SRC_BRFSS,
     unit="respondents", n=N_FMD)
miss_share = 1 - N_FMD / N_TARGET
fact("brfss_fmd_missing_share", miss_share, pct(miss_share),
     "Share of target respondents answering don't know, refused, or blank to MENTHLTH (excluded)",
     SRC_BRFSS, n=N_TARGET, note="Codes 77, 99, and blank; the estimand is prevalence among adults who answered")
fact("brfss_fmd_unweighted", unw, pct(unw),
     "Unweighted share of respondents reporting 14+ poor mental health days in the past 30",
     SRC_BRFSS, n=N_FMD, weight="none", variance="none",
     note="Not an estimate of any population quantity; shown as the defensible-looking wrong answer")
fact("brfss_fmd_final", fin, pct(fin),
     "Frequent mental distress (MENTHLTH >= 14 of past 30 days) among adults 18+ in the 49 states and "
     "DC that released 2024 BRFSS data, among those who answered", SRC_BRFSS,
     se=t_final["se"], ci_low=t_final["lci"], ci_high=t_final["uci"],
     ci_display=ci_pct(t_final["lci"], t_final["uci"]), df=DF, n=N_FMD, weight="_LLCPWT",
     variance="taylor", benchmark=f"CDC codebook weighted percentage for _MENT14D=3 is {100 * cb_pct:.2f}% "
     "over all records with missing in the denominator; this file reproduces it (see manifest)",
     note=f"Strata _STSTR ({N_STRATA:,}); PSU = respondent; {N_SINGLE} singleton strata centred "
          f"('adjust'); df = n - strata")
fact("brfss_fmd_gap_pp", 100 * (fin - unw), num(100 * (fin - unw), 1),
     "Final-weighted minus unweighted FMD prevalence, percentage points", SRC_BRFSS,
     unit="percentage points", n=N_FMD)
fact("brfss_wt2rake_exceptions", int(bad.height), intc(bad.height),
     "Records whose _WT2RAKE differs from _STRWT x _RAWRAKE (all Illinois, cell frame)", SRC_BRFSS,
     unit="records")
fact("brfss_ment14d_codebook", ours_all, pct(ours_all, 2),
     "Weighted share with _MENT14D = 3 over all 2024 records (territories included, missing in the "
     "denominator), computed from the file", SRC_BRFSS, n=N_FILE, weight="_LLCPWT",
     benchmark=f"CDC 2024 codebook weighted percentage: {100 * cb_pct:.2f}% (external benchmark)")
fact("brfss_df", DF, intc(DF), "Design degrees of freedom for the FMD estimate (respondents minus strata)",
     SRC_BRFSS, n=N_FMD)
fact("brfss_strata", N_STRATA, intc(N_STRATA), "Sampling strata (_STSTR) in the 49 states and DC",
     SRC_BRFSS)
fact("brfss_singletons", N_SINGLE, intc(N_SINGLE),
     "Strata containing a single respondent (singleton PSU) in the 49 states and DC", SRC_BRFSS)
fact("brfss_iyear_2025", n_iyear_2025, intc(n_iyear_2025),
     "2024-file records whose interview date (IYEAR) falls in 2025", SRC_BRFSS)

# weights: how many adults a respondent stands for
wt = b["xllcpwt"].to_numpy()
fact("brfss_weight_total", float(wt.sum()), million(wt.sum()),
     "Sum of _LLCPWT over the target: adults 18+ represented in the 49 states and DC", SRC_BRFSS,
     unit="adults", n=N_TARGET, weight="_LLCPWT")
fact("brfss_weight_median", float(np.median(wt)), intc(np.median(wt)),
     "Median final weight: adults represented by the median respondent", SRC_BRFSS,
     unit="adults", n=N_TARGET, weight="_LLCPWT")
fact("brfss_weight_max", float(wt.max()), intc(wt.max()), "Largest final weight in the target",
     SRC_BRFSS, unit="adults", n=N_TARGET, weight="_LLCPWT")
sm = (b.group_by("xstate").agg(pl.col("xllcpwt").mean().alias("m"), pl.len().alias("n"))
      .sort("m"))
lo_state, hi_state = int(sm["xstate"][0]), int(sm["xstate"][-1])
check("state_mean_extremes", (lo_state, hi_state) == (50, 6),
      f"smallest mean weight: {FIPS[lo_state]}; largest: {FIPS[hi_state]} (prose names them)")
fact("brfss_mean_w_ca", float(sm["m"][-1]), intc(sm["m"][-1]),
     "Mean final weight among California respondents", SRC_BRFSS, unit="adults",
     n=int(sm["n"][-1]), weight="_LLCPWT")
fact("brfss_mean_w_vt", float(sm["m"][0]), intc(sm["m"][0]),
     "Mean final weight among Vermont respondents", SRC_BRFSS, unit="adults",
     n=int(sm["n"][0]), weight="_LLCPWT")
fact("brfss_n_ca", int(sm["n"][-1]), intc(sm["n"][-1]), "California respondents, 2024", SRC_BRFSS,
     unit="respondents")
fact("brfss_n_vt", int(sm["n"][0]), intc(sm["n"][0]), "Vermont respondents, 2024", SRC_BRFSS,
     unit="respondents")

# stage facts
for key in ["strwt", "wt2rake", "composite", "llcpwt2"]:
    fact(f"brfss_fmd_{key}", stage[key]["est"], pct(stage[key]["est"]),
         f"FMD prevalence weighted by the {stage[key]['label'].lower()} ({stage[key]['var']}); a "
         "diagnostic stage, not a published estimate", SRC_BRFSS, n=N_FMD, weight=stage[key]["var"],
         variance="none")
for key in ["strwt", "llcpwt2", "final"]:
    fact(f"brfss_cv_{key}", stage[key]["cv"], num(stage[key]["cv"], 2),
         f"Coefficient of variation of the {stage[key]['label'].lower()} weights, respondents with valid FMD",
         SRC_BRFSS, n=N_FMD, weight=stage[key]["var"])
fact("brfss_fmd_statenorm", stage["unweighted"]["est_sn"], pct(stage["unweighted"]["est_sn"]),
     "FMD prevalence with respondents weighted equally within state and each state held at its final "
     "weighted total (geography only)", SRC_BRFSS, n=N_FMD, weight="state totals of _LLCPWT", variance="none")
fact("brfss_nkish_final", stage["final"]["nk"], intc(stage["final"]["nk"]),
     "Kish effective sample size n/(1+CV^2) of _LLCPWT, respondents with valid FMD", SRC_BRFSS,
     n=N_FMD, weight="_LLCPWT")
fact("brfss_llcpwt2_total", stage["llcpwt2"]["total"], million(stage["llcpwt2"]["total"]),
     "Sum of the raking input weight _LLCPWT2 over respondents with valid FMD", SRC_BRFSS,
     n=N_FMD, weight="_LLCPWT2")
fact("brfss_strwt_total", stage["strwt"]["total"], million(stage["strwt"]["total"]),
     "Sum of the stratum weight _STRWT over respondents with valid FMD", SRC_BRFSS,
     n=N_FMD, weight="_STRWT")

# respondents by frame and phone status
n_ll, n_cp = ll.height, cp.height
fact("brfss_n_landline", n_ll, intc(n_ll), "Target respondents reached through the landline frame",
     SRC_BRFSS, unit="respondents")
fact("brfss_n_cell", n_cp, intc(n_cp), "Target respondents reached through the cell phone frame",
     SRC_BRFSS, unit="respondents")
n_dual = dual.height
fact("brfss_dual_share", n_dual / N_TARGET, pct(n_dual / N_TARGET),
     "Share of target respondents who are dual users (reachable through both frames)", SRC_BRFSS,
     n=N_TARGET)
lam = pairs.sort("xstate")
lam_lo, lam_hi = float(lam["landline"].min()), float(lam["landline"].max())
fact("brfss_lambda_min", lam_lo, num(lam_lo, 2),
     "Smallest state compositing factor applied to landline-frame dual users", SRC_BRFSS)
fact("brfss_lambda_max", lam_hi, num(lam_hi, 2),
     "Largest state compositing factor applied to landline-frame dual users", SRC_BRFSS)
fact("brfss_ll_unknown_phones", N_LL_UNKNOWN_PHONES, intc(N_LL_UNKNOWN_PHONES),
     "Landline respondents with an unknown number of landline numbers (imputed as one)", SRC_BRFSS,
     unit="respondents")
fact("brfss_l2_ratio_lo", float(ratio_l2.min()), num(ratio_l2.min(), 2),
     "Smallest state ratio of summed _LLCPWT2 to summed _LLCPWT", SRC_BRFSS)
fact("brfss_l2_ratio_hi", float(ratio_l2.max()), num(ratio_l2.max(), 2),
     "Largest state ratio of summed _LLCPWT2 to summed _LLCPWT", SRC_BRFSS)

# ---- who gains and loses weighted share, stage by stage (all target respondents)
GROUPS = [
    ("Age", "18–24", pl.col("xage_g") == 1), ("Age", "25–34", pl.col("xage_g") == 2),
    ("Age", "35–44", pl.col("xage_g") == 3), ("Age", "45–54", pl.col("xage_g") == 4),
    ("Age", "55–64", pl.col("xage_g") == 5), ("Age", "65 or older", pl.col("xage_g") == 6),
    ("Sex", "Male", pl.col("xsex") == 1), ("Sex", "Female", pl.col("xsex") == 2),
    ("Phone", "Landline only", pl.col("phone") == "landline_only"),
    ("Phone", "Both (dual user)", pl.col("phone") == "dual"),
    ("Phone", "Cell only", pl.col("phone") == "cell_only"),
    ("Education", "Less than high school", pl.col("xeducag") == 1),
    ("Education", "High school graduate", pl.col("xeducag") == 2),
    ("Education", "Some college", pl.col("xeducag") == 3),
    ("Education", "College graduate", pl.col("xeducag") == 4),
]
share_rows = []
shares = {}
for dim, lab, expr in GROUPS:
    ind = b.select(expr.cast(pl.Float64)).to_series().to_numpy()
    row = {"group": f"{dim}: {lab}"}
    for key, *_rest, col in STAGES:
        w = b[col].to_numpy().astype(float)
        row[key] = rnd(float(np.dot(w, ind) / w.sum()), 8)
    shares[(dim, lab)] = row
    share_rows.append(row)

def share_fact(k, dim, lab, stage_key, desc):
    v = shares[(dim, lab)][stage_key]
    fact(k, v, pct(v), desc, SRC_BRFSS, n=N_TARGET,
         weight="none" if stage_key == "unweighted" else dict((s[0], s[2]) for s in STAGES)[stage_key])

share_fact("share_age1824_unw", "Age", "18–24", "unweighted", "Share of target respondents aged 18-24")
share_fact("share_age1824_final", "Age", "18–24", "final", "Weighted share aged 18-24 under _LLCPWT")
share_fact("share_age65_unw", "Age", "65 or older", "unweighted", "Share of target respondents aged 65+")
share_fact("share_age65_final", "Age", "65 or older", "final", "Weighted share aged 65+ under _LLCPWT")
share_fact("share_cellonly_unw", "Phone", "Cell only", "unweighted", "Share of target respondents who are cell only")
share_fact("share_cellonly_final", "Phone", "Cell only", "final", "Weighted share cell only under _LLCPWT")
share_fact("share_dual_wt2rake", "Phone", "Both (dual user)", "wt2rake",
           "Weighted share of dual users under _WT2RAKE (before compositing)")
share_fact("share_dual_composite", "Phone", "Both (dual user)", "composite",
           "Weighted share of dual users after the compositing factor")
share_fact("share_dual_llcpwt2", "Phone", "Both (dual user)", "llcpwt2",
           "Weighted share of dual users under the raking input _LLCPWT2")
share_fact("share_college_unw", "Education", "College graduate", "unweighted",
           "Share of target respondents with a college or technical-school degree")
share_fact("share_college_final", "Education", "College graduate", "final",
           "Weighted share with a college or technical-school degree under _LLCPWT")
share_fact("share_lths_unw", "Education", "Less than high school", "unweighted",
           "Share of target respondents who did not graduate high school")
share_fact("share_lths_final", "Education", "Less than high school", "final",
           "Weighted share who did not graduate high school under _LLCPWT")

# FMD by the groups that move most (context for the waterfall)
def grp_fmd(expr):
    sub = a.filter(expr)
    return wmean(sub["fmd"].to_numpy(), sub["xllcpwt"].to_numpy()), sub.height
f1824, n1824 = grp_fmd(pl.col("xage_g") == 1)
f65, n65 = grp_fmd(pl.col("xage_g") == 6)
fact("brfss_fmd_age1824", f1824, pct(f1824), "Final-weighted FMD prevalence, adults 18-24", SRC_BRFSS,
     n=n1824, weight="_LLCPWT", variance="none", note="Point estimate only; not used for inference")
fact("brfss_fmd_age65", f65, pct(f65), "Final-weighted FMD prevalence, adults 65+", SRC_BRFSS,
     n=n65, weight="_LLCPWT", variance="none", note="Point estimate only; not used for inference")

# ---- illustrative raking reconstruction: rake _LLCPWT2 to _LLCPWT's own state margins
st_idx = np.unique(b["xstate"].to_numpy(), return_inverse=True)[1]
def codes_of(*cols):
    arrs = [np.unique((b[c].fill_null("NA") if b[c].dtype == pl.Utf8 else b[c].fill_null(-1)).to_numpy(),
                      return_inverse=True)[1] for c in cols]
    code = st_idx.copy()
    for arr in arrs:
        code = code * (arr.max() + 1) + arr
    return np.unique(code, return_inverse=True)[1]
MARGINS = [codes_of("xsex", "xage_g"), codes_of("ximprace"), codes_of("xeducag"), codes_of("marital"),
           codes_of("renthom1"), codes_of("xsex", "ximprace"), codes_of("xage_g", "ximprace"),
           codes_of("phone")]
MARGIN_NAMES = ["sex x age group", "race/ethnicity (imputed)", "education", "marital status", "tenure",
                "sex x race/ethnicity", "age group x race/ethnicity", "phone ownership"]
w_final_all = b["xllcpwt"].to_numpy().astype(float)
TARGETS = [np.bincount(c, weights=w_final_all) for c in MARGINS]
w_rec, it_rec = rake(b["xllcpwt2"].to_numpy(), MARGINS, TARGETS)
valid_mask = b["valid"].to_numpy() == 1
fmd_rec = wmean(y, w_rec[valid_mask])
rel_dev = np.abs(w_rec / w_final_all - 1)
corr_log = float(np.corrcoef(np.log(w_rec), np.log(w_final_all))[0, 1])
VALIDATION.append({
    "check": "illustrative_raking_reconstruction", "result": "info",
    "detail": (f"_LLCPWT2 raked (IPF, {it_rec} sweeps) to _LLCPWT's state totals on "
               f"{len(MARGINS)} margins ({'; '.join(MARGIN_NAMES)}): FMD {100 * fmd_rec:.3f}% vs final "
               f"{100 * fin:.3f}%; median |w_rec/w_final - 1| = {np.median(rel_dev):.3f}; "
               f"corr(log w) = {corr_log:.3f}. Region and county margins and CDC's own categories "
               "are not on the public file."),
})
fact("brfss_fmd_rerake_recon", fmd_rec, pct(fmd_rec, 2),
     "FMD prevalence after raking _LLCPWT2 to _LLCPWT's own state margins on eight public dimensions "
     "(illustrative reconstruction)", SRC_BRFSS, n=N_FMD, weight="reconstruction", variance="none")
fact("brfss_recon_median_dev", float(np.median(rel_dev)), pct(float(np.median(rel_dev)), 0),
     "Median absolute relative difference between the reconstructed and the published final weight",
     SRC_BRFSS, n=N_TARGET)

# ---- trimming (within-state percentile caps; state totals preserved), then re-raking
state_codes = st_idx
state_tot = np.bincount(state_codes, weights=w_final_all)
def cap_weights(q):
    caps = np.zeros(state_codes.max() + 1)
    for s in range(len(caps)):
        caps[s] = np.percentile(w_final_all[state_codes == s], q)  # linear = R type 7
    wt_ = np.minimum(w_final_all, caps[state_codes])
    return wt_ * (state_tot / np.bincount(state_codes, weights=wt_))[state_codes]
TRIMS = [("none", "No cap (published final weight)", w_final_all)]
for q in (99, 95):
    TRIMS.append((f"p{q}", f"Cap at each state's {q}th percentile", cap_weights(q)))
w_p95r, it_p95r = rake(TRIMS[-1][2], MARGINS, TARGETS)
TRIMS.append(("p95_rerake", "95th-percentile cap, then re-raked", w_p95r))
trim_rows = []
trim = {}
for key, label, wv in TRIMS:
    frame_w = b.with_columns(pl.Series("w_trim", wv))
    tt = svy_mean(frame_w, "w_trim")
    wv_valid = wv[valid_mask]
    row = {
        "label": label, "fmd": rnd(tt["est"], 8), "se_pp": rnd(100 * tt["se"], 6),
        "cv": rnd(cv_w(wv_valid), 6), "nkish": rnd(n_kish(wv_valid), 8),
        "age1824": rnd(float(np.dot(wv, (b["xage_g"] == 1).to_numpy()) / wv.sum()), 8),
        "cellonly": rnd(float(np.dot(wv, (b["phone"] == "cell_only").to_numpy()) / wv.sum()), 8),
        "lths": rnd(float(np.dot(wv, (b["xeducag"] == 1).to_numpy()) / wv.sum()), 8),
    }
    trim[key] = dict(row, se=tt["se"], lci=tt["lci"], uci=tt["uci"], df=tt["df"])
    trim_rows.append(row)
    print(f"  trim {key:11s} FMD={tt['est']:.5f} SE={tt['se']:.6f} CV={row['cv']:.3f} nK={row['nkish']:,.0f}")
if rc is not None:
    rp = rc["fmd_p95_adjust"]
    ok = abs(rp["estimate"] - trim["p95"]["fmd"]) < 1e-7 and abs(rp["se"] / trim["p95"]["se"] - 1) < 1e-3
    check("r_survey_p95", ok, f"R: {rp['estimate']:.8f} (SE {rp['se']:.8f}); svy: {trim['p95']['fmd']:.8f} "
          f"(SE {trim['p95']['se']:.8f}) under the within-state 95th-percentile cap")
for key in ("p99", "p95"):
    t = trim[key]
    fact(f"trim_{key}_fmd", t["fmd"], pct(t["fmd"], 2),
         f"FMD prevalence with final weights capped at each state's {key[1:]}th percentile and rescaled to "
         "state totals", SRC_BRFSS, se=t["se"], ci_low=t["lci"], ci_high=t["uci"],
         ci_display=ci_pct(t["lci"], t["uci"], 2), df=int(t["df"]), n=N_FMD,
         weight=f"_LLCPWT capped ({key})", variance="taylor",
         note="Taylor SE treats the trimmed weights as fixed")
    fact(f"trim_{key}_cv", t["cv"], num(t["cv"], 2), f"CV of weights capped at the {key[1:]}th percentile",
         SRC_BRFSS, n=N_FMD)
    fact(f"trim_{key}_nkish", t["nkish"], intc(t["nkish"]),
         f"Kish effective sample size, weights capped at the {key[1:]}th percentile", SRC_BRFSS, n=N_FMD)
t = trim["none"]
fact("trim_none_fmd", t["fmd"], pct(t["fmd"], 2), "FMD prevalence under the published final weight (two decimals)",
     SRC_BRFSS, se=t["se"], n=N_FMD, weight="_LLCPWT", variance="taylor", df=int(t["df"]))
fact("trim_p95_se_ratio", trim["p95"]["se"] / trim["none"]["se"], pct(trim["p95"]["se"] / trim["none"]["se"], 0),
     "Taylor SE under the 95th-percentile cap as a share of the SE under the final weight", SRC_BRFSS, n=N_FMD)
shift95 = trim["p95"]["fmd"] - trim["none"]["fmd"]
check("trim_p95_direction", shift95 < 0, f"the 95th-percentile cap lowers FMD by {-100 * shift95:.3f} pp (prose says 'falls')")
fact("trim_p95_shift_pp", abs(100 * shift95), num(abs(100 * shift95), 2),
     "Decrease in FMD prevalence from capping at the 95th percentile, percentage points", SRC_BRFSS,
     unit="percentage points", n=N_FMD)
fact("trim_p95_shift_se", abs(shift95) / trim["none"]["se"], num(abs(shift95) / trim["none"]["se"], 1),
     "Absolute shift from the 95th-percentile cap divided by the SE of the final estimate", SRC_BRFSS)
fact("trim_p95_age1824", trim["p95"]["age1824"], pct(trim["p95"]["age1824"]),
     "Weighted share aged 18-24 after the 95th-percentile cap (state totals preserved)", SRC_BRFSS, n=N_TARGET)
fact("trim_p95_cellonly", trim["p95"]["cellonly"], pct(trim["p95"]["cellonly"]),
     "Weighted share cell only after the 95th-percentile cap", SRC_BRFSS, n=N_TARGET)
t = trim["p95_rerake"]
fact("trim_p95r_fmd", t["fmd"], pct(t["fmd"], 2),
     "FMD prevalence after the 95th-percentile cap and re-raking to the final weight's state margins",
     SRC_BRFSS, se=t["se"], ci_low=t["lci"], ci_high=t["uci"], ci_display=ci_pct(t["lci"], t["uci"], 2),
     df=int(t["df"]), n=N_FMD, weight="capped then re-raked", variance="taylor")
fact("trim_p95r_cv", t["cv"], num(t["cv"], 2), "CV of the capped-then-re-raked weights", SRC_BRFSS, n=N_FMD)
fact("trim_p95r_nkish", t["nkish"], intc(t["nkish"]),
     "Kish effective sample size of the capped-then-re-raked weights", SRC_BRFSS, n=N_FMD)

# ---- one mean, three standard errors: frequency, analytic, sampling weights
Wsum = float(wf.sum())
p_hat = fin
se_f = float(np.sqrt(p_hat * (1 - p_hat) / (Wsum - 1)))
# analytic weights a_i (normalized to sum to n): Var = s_a^2 / sum(a), s_a^2 = sum a (y - ybar)^2 / (n - 1)
se_a = float(np.sqrt(np.dot(wf / wf.mean(), (y - p_hat) ** 2) / (N_FMD - 1) / N_FMD))
fact("se_as_frequency", 100 * se_f, num(100 * se_f, 4),
     "SE of the FMD mean if _LLCPWT were frequency weights (each respondent = w identical adults), pp",
     SRC_BRFSS, unit="percentage points", n=N_FMD, weight="_LLCPWT as f_i", variance="none",
     note="Wrong model for these data: treats the weighted total as the sample size")
fact("se_as_analytic", 100 * se_a, num(100 * se_a, 3),
     "SE of the FMD mean if _LLCPWT were precision (analytic) weights normalized to n, pp", SRC_BRFSS,
     unit="percentage points", n=N_FMD, weight="_LLCPWT as a_i", variance="none",
     note="Wrong model for these data: treats weights as inverse-variance factors")
fact("se_as_sampling", 100 * t_final["se"], num(100 * t_final["se"], 3),
     "SE of the FMD mean with _LLCPWT as sampling weights and the declared design (Taylor), pp",
     SRC_BRFSS, unit="percentage points", n=N_FMD, weight="_LLCPWT as w_i", variance="taylor", df=DF)

# ---- effective samples for BRFSS: Kish vs design
deff = float(t_final["deff"])
fact("brfss_deff_fmd", deff, num(deff, 2), "Design effect (with-replacement SRS reference) of the FMD estimate",
     SRC_BRFSS, n=N_FMD, weight="_LLCPWT", variance="taylor")
fact("brfss_ndesign_fmd", N_FMD / deff, intc(N_FMD / deff),
     "Design-effective sample size n/DEFF for the FMD estimate", SRC_BRFSS, n=N_FMD, weight="_LLCPWT")
b65 = b.with_columns(fmd0=(pl.col("xage_g") == 6).cast(pl.Float64), valid=pl.lit(1, dtype=pl.Int64))
t65 = svy_mean(b65, "xllcpwt")
fact("brfss_deff_age65", float(t65["deff"]), num(float(t65["deff"]), 2),
     "Design effect of the estimated share of adults aged 65+", SRC_BRFSS, n=N_TARGET, weight="_LLCPWT",
     variance="taylor")
fact("brfss_ndesign_age65", N_TARGET / float(t65["deff"]), intc(N_TARGET / float(t65["deff"])),
     "Design-effective sample size n/DEFF for the share aged 65+", SRC_BRFSS, n=N_TARGET, weight="_LLCPWT")
ks = []
for s in np.unique(st_idx):
    ws = w_final_all[st_idx == s]
    ks.append(n_kish(ws) / len(ws))
fact("brfss_kish_ratio_state_median", float(np.median(ks)), num(float(np.median(ks)), 2),
     "Median across the 50 jurisdictions of within-state n_Kish/n for _LLCPWT", SRC_BRFSS, n=N_TARGET)

# ================================================================== 2. coverage by year
print("== coverage")
cov = con.execute(
    f"select iyear, xstate, count(*) n, sum(xllcpwt) w from read_parquet('{HARMONIZED.as_posix()}') "
    "where iyear between 2014 and 2024 group by 1, 2 order by 1, 2").pl()
cov_rows = []
for yr in range(2014, 2025):
    present = set(int(s) for s in cov.filter(pl.col("iyear") == yr)["xstate"].to_list())
    miss = [FIPS[f] for f in FIPS if f not in present]
    terr = [TERRITORIES[t_] for t_ in sorted(present) if t_ in TERRITORIES]
    cov_rows.append({"year": str(yr), "released": 51 - len(miss),
                     "missing": ", ".join(miss) if miss else "none",
                     "territories": ", ".join(terr)})
cov_map = {r["year"]: r["missing"] for r in cov_rows}
check("coverage_gaps", cov_map["2024"] == "Tennessee" and cov_map["2023"] == "Kentucky, Pennsylvania"
      and cov_map["2021"] == "Florida" and cov_map["2022"] == "none" and cov_map["2019"] == "New Jersey",
      "missing jurisdictions: 2024 TN; 2023 KY, PA; 2022 none; 2021 FL; 2019 NJ (from the file itself)")
c22 = cov.filter(pl.col("iyear") == 2022)
tn22 = float(c22.filter(pl.col("xstate") == 47)["w"].sum())
tot22 = float(c22.filter(pl.col("xstate") <= 56)["w"].sum())
fact("tn_2022_adults", tn22, million(tn22), "Sum of _LLCPWT over Tennessee respondents, BRFSS 2022",
     "CDC BRFSS 2022 (BRFSS_2026/cleaned/brfss_multi_rec.parquet)", unit="adults", weight="_LLCPWT")
fact("tn_2022_share", tn22 / tot22, pct(tn22 / tot22),
     "Tennessee's share of the summed _LLCPWT over the 50 states and DC, BRFSS 2022",
     "CDC BRFSS 2022 (BRFSS_2026/cleaned/brfss_multi_rec.parquet)", weight="_LLCPWT")

# ================================================================== 3. ATUS 2023: d = 1/pi by day
print("== ATUS 2023")
at = pl.read_parquet(ATUS, columns=["YEAR", "DAY", "WT06", "BLS_WORK"]).filter(pl.col("YEAR") == 2023)
check("atus_rows", at.height == 8548 and at["BLS_WORK"].null_count() == 0 and bool((at["WT06"] > 0).all()),
      f"{at.height:,} ATUS 2023 respondents, all with positive WT06 and BLS_WORK")
wk = at.with_columns(weekend=pl.col("DAY").is_in([1, 7]))
wkend = wk["weekend"].to_numpy()
work = wk["BLS_WORK"].to_numpy().astype(float)
wt06 = wk["WT06"].to_numpy().astype(float)
d_day = np.where(wkend, 1 / 0.25, 1 / 0.10)  # User's Guide 3.5: 25% per weekend day, 10% per weekday
atus = {
    "n": at.height, "n_wkend": int(wkend.sum()),
    "unw": float(work.mean()), "d": wmean(work, d_day), "wt06": wmean(work, wt06),
    "sh_sample": float(wkend.mean()), "sh_d": float(d_day[wkend].sum() / d_day.sum()),
    "sh_wt06": float(wt06[wkend].sum() / wt06.sum()),
    "m_wd": float(work[~wkend].mean()), "m_we": float(work[wkend].mean()),
    "wt_ratio": float(wt06[~wkend].mean() / wt06[wkend].mean()),
}
check("atus_benchmark", abs(atus["wt06"] - 213.6) < 1.0,
      f"weighted work minutes {atus['wt06']:.1f} vs BLS ATUS 2023 published 3.56 h = 213.6 min (external benchmark)")
fact("atus_n", atus["n"], intc(atus["n"]), "ATUS 2023 respondents (one diary day each)", SRC_ATUS,
     unit="respondents")
fact("atus_weekend_sample_share", atus["sh_sample"], pct(atus["sh_sample"]),
     "Share of ATUS 2023 diaries that report a Saturday or Sunday", SRC_ATUS, n=atus["n"], weight="none")
fact("atus_weekend_share_d", atus["sh_d"], pct(atus["sh_d"]),
     "Weekend share of person-days under the day-of-week design weight alone (d = 1/0.25 or 1/0.10)",
     SRC_ATUS, n=atus["n"], weight="d_i = 1/pi (day)")
fact("atus_weekend_share_wt06", atus["sh_wt06"], pct(atus["sh_wt06"]),
     "Weekend share of weighted person-days under WT06", SRC_ATUS, n=atus["n"], weight="WT06")
fact("atus_work_unweighted", atus["unw"], num(atus["unw"], 1),
     "Unweighted mean minutes working per diary day, ATUS 2023", SRC_ATUS, unit="minutes per day",
     n=atus["n"], weight="none", variance="none")
fact("atus_work_design", atus["d"], num(atus["d"], 1),
     "Mean minutes working per day weighted only by the day-of-week design weight", SRC_ATUS,
     unit="minutes per day", n=atus["n"], weight="d_i = 1/pi (day)", variance="weights_only_understated")
fact("atus_work_weighted", atus["wt06"], num(atus["wt06"], 1),
     "Mean minutes per day spent working, all 2023 person-days, civilian noninstitutional population 15+",
     SRC_ATUS, unit="minutes per day", n=atus["n"], weight="WT06", variance="weights_only_understated",
     benchmark="BLS ATUS 2023 published 3.56 hours/day (213.6 minutes)")
fact("atus_work_weekday", atus["m_wd"], num(atus["m_wd"], 1),
     "Unweighted mean work minutes on weekday diary days", SRC_ATUS, unit="minutes per day",
     n=int((~wkend).sum()), weight="none")
fact("atus_work_weekend", atus["m_we"], num(atus["m_we"], 1),
     "Unweighted mean work minutes on weekend diary days", SRC_ATUS, unit="minutes per day",
     n=atus["n_wkend"], weight="none")
fact("atus_wt_ratio", atus["wt_ratio"], num(atus["wt_ratio"], 1),
     "Mean WT06 of weekday diaries divided by mean WT06 of weekend diaries", SRC_ATUS, n=atus["n"], weight="WT06")

# ================================================================== 4. Kish across surveys
print("== Kish")
def kish_row(label, unit, weight, wv):
    wv = np.asarray(wv, dtype=float)
    return {"survey": label, "unit": unit, "weight": weight, "n": int(len(wv)),
            "cv": rnd(cv_w(wv), 6), "nkish": rnd(n_kish(wv), 8), "ratio": rnd(n_kish(wv) / len(wv), 6)}
asec = con.execute(f"select ASECWT from read_parquet('{ASEC.as_posix()}') where YEAR = 2024 and ASECWT > 0").fetchnumpy()["ASECWT"]
voter = con.execute(f"select VOSUPPWT from read_parquet('{VOTER.as_posix()}') where YEAR = 2020 and VOSUPPWT > 0").fetchnumpy()["VOSUPPWT"]
fsm = con.execute(f"select distinct MONTH from read_parquet('{FOODSEC.as_posix()}') where YEAR = 2023").fetchall()
check("foodsec_month", [int(m[0]) for m in fsm] == [12], f"CPS Food Security 2023 rows are all MONTH = {fsm}")
foods = con.execute(f"select FSSUPPWTH from read_parquet('{FOODSEC.as_posix()}') where YEAR = 2023 and PERNUM = 1 "
                    "and FSSUPPWTH > 0").fetchnumpy()["FSSUPPWTH"]
kish_rows = [
    kish_row("BRFSS 2024 (49 states + DC)", "adults", "_LLCPWT", w_final_all),
    kish_row("ATUS 2023", "person-days", "WT06", wt06),
    kish_row("CPS ASEC 2024", "persons", "ASECWT", asec),
    kish_row("CPS Food Security, Dec 2023", "households", "FSSUPPWTH", foods),
    kish_row("CPS Voting and Registration 2020", "persons", "VOSUPPWT", voter),
]
kish_rows.sort(key=lambda r: r["ratio"])
for r in kish_rows:
    print(f"  {r['survey']:36s} n={r['n']:>8,} CV={r['cv']:.3f} nK={r['nkish']:>10,.0f} ratio={r['ratio']:.3f}")
brow = kish_rows[0]
check("kish_brfss_is_lowest", brow["survey"].startswith("BRFSS"), "BRFSS has the lowest n_Kish/n of the five")
fact("kish_brfss_cv", brow["cv"], num(brow["cv"], 2), "CV of _LLCPWT, all respondents in the 49 states and DC",
     SRC_BRFSS, n=brow["n"], weight="_LLCPWT")
fact("kish_brfss_ratio", brow["ratio"], num(brow["ratio"], 2), "n_Kish/n for _LLCPWT, 49 states and DC",
     SRC_BRFSS, n=brow["n"], weight="_LLCPWT")
arow = [r for r in kish_rows if r["survey"].startswith("ATUS")][0]
fact("kish_atus_ratio", arow["ratio"], num(arow["ratio"], 2), "n_Kish/n for WT06, ATUS 2023", SRC_ATUS,
     n=arow["n"], weight="WT06")
crow = [r for r in kish_rows if r["survey"].startswith("CPS ASEC")][0]
fact("kish_asec_ratio", crow["ratio"], num(crow["ratio"], 2), "n_Kish/n for ASECWT, CPS ASEC 2024",
     "IPUMS CPS ASEC 2024 (analysis/cps/cps_asec)", n=crow["n"], weight="ASECWT")

# ================================================================== 5. figures
print("== figures")
role = {"unweighted": "unweighted", "strwt": "design", "wt2rake": "design", "composite": "design",
        "llcpwt2": "muted", "final": "weighted"}
write_json(FIG / "waterfall.json", {
    "type": "dot",
    "title": "Frequent mental distress, one weight at a time",
    "subtitle": "BRFSS 2024, adults in the 49 states and DC that released data; share reporting 14+ poor mental health days",
    "alt": ("Dot plot of frequent mental distress prevalence under six weights, from unweighted through "
            "stratum, household, and dual-frame design weights to the raking input and the final raked weight."),
    "format": "pct1",
    "x_label": "Share of adults with frequent mental distress",
    "reference": {"value": rnd(fin, 8), "label": "Final weight"},
    "rows": [{"label": f"{stage[k]['label']} ({stage[k]['var']})" if k != "unweighted" else "Unweighted",
              "estimate": rnd(stage[k]["est"], 8), "group": stage[k]["status"], "role": role[k],
              "n": N_FMD} for k, *_ in STAGES],
    "source": "CDC BRFSS 2024 public file; weights _STRWT, _WT2RAKE, _DUALCOR, _LLCPWT2, _LLCPWT",
    "note": ("Stages 1-3 are rebuilt from public variables; the raking input and final weight are shipped "
             "on the file and documented by CDC, but cannot be rebuilt record by record. Intermediate stages "
             "are diagnostics, not estimates: their totals are not population counts."),
})
write_json(FIG / "waterfall_table.json", {
    "type": "table",
    "title": "The BRFSS 2024 weighting chain",
    "alt": ("Table of the six weighting stages with the variable, what each step multiplies in, whether it "
            "can be rebuilt, the FMD estimate, the weight CV, the Kish effective sample, and the sum of weights."),
    "columns": [
        {"key": "stage", "label": "Stage", "align": "left"},
        {"key": "var", "label": "Variable", "align": "left"},
        {"key": "step", "label": "What it adds", "align": "left"},
        {"key": "status", "label": "Rebuildable?", "align": "left"},
        {"key": "fmd", "label": "FMD", "format": "pct1", "align": "right"},
        {"key": "cv", "label": "CV(w)", "format": "num2", "align": "right"},
        {"key": "nkish", "label": "n Kish", "format": "int", "align": "right"},
        {"key": "total", "label": "Sum of weights (millions)", "format": "num1", "align": "right"},
    ],
    "rows": [{"stage": stage[k]["label"], "var": stage[k]["var"], "step": stage[k]["step"],
              "status": stage[k]["status"], "fmd": rnd(stage[k]["est"], 8), "cv": rnd(stage[k]["cv"], 6),
              "nkish": rnd(stage[k]["nk"], 8), "total": rnd(stage[k]["total"] / 1e6, 6)} for k, *_ in STAGES],
    "highlight_key": "fmd",
    "source": "CDC BRFSS 2024 public file; respondents with a valid MENTHLTH answer in the 49 states and DC",
    "note": (f"n = {N_FMD:,}. _STRWT = NRECSTR/NRECSEL; _RAWRAKE = min(NUMADULT,5)/min(phones,3) on the landline "
             "frame and 1 on the cell frame; _DUALCOR is lambda for landline-frame dual users and 1 - lambda "
             "for cell-frame dual users."),
})
write_json(FIG / "waterfall_shares.json", {
    "type": "table",
    "title": "Who gains and loses weighted share along the chain",
    "alt": ("Table of the weighted share of age, sex, phone-status, and education groups under each of the six "
            "weighting stages, from unweighted to the final weight."),
    "columns": [{"key": "group", "label": "Group", "align": "left"}]
               + [{"key": k, "label": stage[k]["label"], "format": "pct1", "align": "right"} for k, *_ in STAGES],
    "rows": share_rows,
    "highlight_key": "final",
    "source": "CDC BRFSS 2024 public file; all respondents in the 49 states and DC",
    "note": (f"n = {N_TARGET:,}. Phone status: landline-frame respondents without a cell phone are landline only; "
             "cell-frame respondents without a landline are cell only; everyone else is a dual user (_DUALUSE). "
             "Education shares exclude the 0.5% with missing education."),
})
write_json(FIG / "coverage.json", {
    "type": "table",
    "title": "Which jurisdictions are in the BRFSS public file",
    "alt": "Table listing, for each year 2014 to 2024, how many of the 50 states and DC released BRFSS data, which did not, and which territories did.",
    "columns": [{"key": "year", "label": "Year", "align": "left"},
                {"key": "released", "label": "States + DC released (of 51)", "format": "int", "align": "right"},
                {"key": "missing", "label": "Not in the public file", "align": "left"},
                {"key": "territories", "label": "Territories", "align": "left"}],
    "rows": cov_rows,
    "source": "CDC BRFSS 2014-2024 public files (harmonized: BRFSS_2026/cleaned/brfss_multi_rec.parquet)",
    "note": "Read from the files themselves (distinct _STATE by survey year). CDC's 2024 Overview: Tennessee was unable to collect enough data to meet the minimum requirements for the public file.",
})
write_json(FIG / "atus_day_weights.json", {
    "type": "table",
    "title": "Weekend diaries are half the sample and two-sevenths of the days",
    "alt": ("Table comparing weekday and weekend ATUS 2023 diaries: respondents, share of the sample, assignment "
            "probability, design weight, weighted share of person-days, and unweighted work minutes."),
    "columns": [{"key": "day", "label": "Diary day", "align": "left"},
                {"key": "n", "label": "Respondents", "format": "int", "align": "right"},
                {"key": "sh_sample", "label": "Share of sample", "format": "pct1", "align": "right"},
                {"key": "pi", "label": "Assignment probability, each day", "format": "pct0", "align": "right"},
                {"key": "d", "label": "d = 1/π", "format": "num0", "align": "right"},
                {"key": "sh_d", "label": "Share of days under d", "format": "pct1", "align": "right"},
                {"key": "sh_wt06", "label": "Share of days under WT06", "format": "pct1", "align": "right"},
                {"key": "work", "label": "Work minutes (unweighted)", "format": "min1", "align": "right"}],
    "rows": [
        {"day": "Weekday (Mon–Fri)", "n": int((~wkend).sum()), "sh_sample": rnd(1 - atus["sh_sample"], 8),
         "pi": 0.10, "d": 10, "sh_d": rnd(1 - atus["sh_d"], 8), "sh_wt06": rnd(1 - atus["sh_wt06"], 8),
         "work": rnd(atus["m_wd"], 8)},
        {"day": "Weekend (Sat–Sun)", "n": atus["n_wkend"], "sh_sample": rnd(atus["sh_sample"], 8),
         "pi": 0.25, "d": 4, "sh_d": rnd(atus["sh_d"], 8), "sh_wt06": rnd(atus["sh_wt06"], 8),
         "work": rnd(atus["m_we"], 8)},
    ],
    "source": "IPUMS ATUS 2023; allocation from the BLS ATUS User's Guide, section 3.5",
    "note": f"n = {atus['n']:,}. Weights-only extract: standard errors from these weights would not be design-based.",
})
write_json(FIG / "kish_table.json", {
    "type": "table",
    "title": "Kish effective sample sizes in five federal surveys",
    "alt": "Table of sample size, weight CV, Kish effective sample size, and their ratio for BRFSS 2024, ATUS 2023, CPS ASEC 2024, CPS Food Security December 2023 households, and CPS Voting 2020.",
    "columns": [{"key": "survey", "label": "Survey", "align": "left"},
                {"key": "unit", "label": "Unit", "align": "left"},
                {"key": "weight", "label": "Weight", "align": "left"},
                {"key": "n", "label": "n", "format": "int", "align": "right"},
                {"key": "cv", "label": "CV(w)", "format": "num2", "align": "right"},
                {"key": "nkish", "label": "n Kish", "format": "int", "align": "right"},
                {"key": "ratio", "label": "n Kish / n", "format": "num2", "align": "right"}],
    "rows": kish_rows,
    "highlight_key": "ratio",
    "source": "BRFSS 2024 (CDC); IPUMS ATUS 2023; IPUMS CPS ASEC 2024, Food Security Dec 2023, Voting 2020 (analysis/)",
    "note": "All records with a positive weight; Food Security counts households (PERNUM = 1). Kish's formula ignores the outcome and the strata; it prices only weight dispersion.",
})
write_json(FIG / "trimming.json", {
    "type": "table",
    "title": "Trimming buys little precision and moves the margins",
    "alt": ("Table of FMD prevalence, standard error, weight CV, Kish effective sample, and three weighted "
            "margins under the final weight, caps at each state's 99th and 95th percentiles, and a capped-then-re-raked weight."),
    "columns": [{"key": "label", "label": "Weight", "align": "left"},
                {"key": "fmd", "label": "FMD", "format": "pct2", "align": "right"},
                {"key": "se_pp", "label": "SE (pp)", "format": "num3", "align": "right"},
                {"key": "cv", "label": "CV(w)", "format": "num2", "align": "right"},
                {"key": "nkish", "label": "n Kish", "format": "int", "align": "right"},
                {"key": "age1824", "label": "Aged 18–24", "format": "pct1", "align": "right"},
                {"key": "cellonly", "label": "Cell only", "format": "pct1", "align": "right"},
                {"key": "lths", "label": "Less than high school", "format": "pct1", "align": "right"}],
    "rows": trim_rows,
    "source": "CDC BRFSS 2024 public file; 49 states and DC",
    "note": ("Caps are within-state percentiles of _LLCPWT; trimmed weight is redistributed within the state so state "
             "totals are unchanged. Re-raking targets the final weight's own state margins (sex x age, race/ethnicity, "
             "education, marital status, tenure, sex x race, age x race, phone status). Taylor SEs treat weights as fixed."),
})

# ================================================================== 6. ledgers
ledgers = {
    "brfss_fmd": {
        "title": "Frequent mental distress, adults in 49 states and DC (BRFSS 2024)",
        "target_population": ("Noninstitutionalized adults 18+ living in private residences or college housing in the 49 "
                              "states and DC that released 2024 BRFSS data (every state except Tennessee). Guam, Puerto "
                              "Rico, and the US Virgin Islands are excluded by choice."),
        "estimand": ("Share of adults reporting 14 or more of the past 30 days when their mental health was not good "
                     "(MENTHLTH >= 14; 88 = none), among adults who would answer the question."),
        "estimator": "Hajek weighted mean, sum(w_i y_i)/sum(w_i), over respondents with a valid answer.",
        "explicit_weights": ("_LLCPWT: stratum weight x adults/phones (landline) x dual-frame compositing factor, "
                             "truncated within region, then raked to 8 or more state margins."),
        "implicit_weights": ("None from a model. The weights themselves move leverage toward young, cell-only, and "
                             "less-educated respondents and toward large states, where one respondent stands for thousands of adults."),
        "randomness": ("Selection of telephone numbers within strata in two frames, selection of one adult in "
                       "landline households, and response; the weights are themselves estimated."),
        "variance_estimator": (f"Taylor linearization; strata _STSTR; PSU = respondent (_PSU); {N_SINGLE} singleton "
                               f"strata centred ('adjust'); df = {DF:,}. Weights treated as fixed."),
        "assumptions": ("Nonresponse and coverage bias in FMD run through the raking margins; the small telephone "
                        "noncoverage is ignorable; self-report measures the construct; Taylor with fixed weights "
                        "ignores the variability added by estimating the weights."),
        "facts": ["ch2.brfss_fmd_final", "ch2.brfss_fmd_unweighted", "ch2.brfss_deff_fmd", "ch2.brfss_nkish_final"],
    },
    "atus_design_weight": {
        "title": "The day-of-week design weight (ATUS 2023)",
        "target_population": "All person-days in 2023, civilian noninstitutional population 15+.",
        "estimand": "Mean minutes per day spent working, averaged over every person-day of 2023.",
        "estimator": "Hajek weighted mean of BLS_WORK: first with d_i = 1/pi_i for the diary day alone, then with WT06.",
        "explicit_weights": ("d_i = 1/0.10 for a weekday diary and 1/0.25 for a weekend diary (the designated-day "
                             "allocation); WT06 adds the rest of the design weight plus nonresponse and population controls."),
        "implicit_weights": "None.",
        "randomness": "CPS-based household selection, random assignment of one designated day, and response.",
        "variance_estimator": "Not computed: weights-only file; an SE from these weights alone would not be design-based.",
        "assumptions": "The designated-day assignment follows the documented allocation; response on the designated day is ignorable after WT06.",
        "facts": ["ch2.atus_work_unweighted", "ch2.atus_work_design", "ch2.atus_work_weighted"],
    },
}

# ================================================================== 7. write
write_json(ART / "facts.json", {"key": "ch2", "facts": FACTS})
write_json(ART / "ledger.json", {"key": "ch2", "ledgers": ledgers})
manifest = {
    "key": "ch2", "slug": "ch02-weights", "status": "draft", "code": "build.py",
    "inputs": [
        {"path": str(EXTRACT.relative_to(BOX)).replace("\\", "/"), "rows": N_FILE,
         "note": f"extract_brfss.R from BRFSS_2026/raw/2024.rds (sha256 {sha256(RAW_RDS)[:16]}...); 52 columns"},
        {"path": "BRFSS/BRFSS_2026/cleaned/brfss_multi_rec.parquet", "rows": None,
         "note": "coverage by survey-file year 2014-2024; Tennessee 2022 weight"},
        {"path": "BRFSS/BRFSS_2026/raw/codebooks/codebook24_llcp-v2-508_extracted/USCODE24_LLCP_082125.HTML",
         "rows": None, "note": "CDC weighted percentage for _MENT14D (benchmark)"},
        {"path": "ipums/analysis/atus/atus_respondent.parquet", "rows": atus["n"], "note": "YEAR = 2023"},
        {"path": "ipums/analysis/cps/cps_asec/part_2020_2025.parquet", "rows": int(len(asec)),
         "note": "YEAR = 2024, ASECWT > 0"},
        {"path": "ipums/analysis/cps/cps_foodsec.parquet", "rows": int(len(foods)),
         "note": "YEAR = 2023 (December), PERNUM = 1, FSSUPPWTH > 0"},
        {"path": "ipums/analysis/cps/cps_voter.parquet", "rows": int(len(voter)), "note": "YEAR = 2020, VOSUPPWT > 0"},
    ],
    "validation": VALIDATION,
    "settings": {"lonely_psu": f"svy '{LONELY_RULE}' (R 'adjust'); sensitivity 'remove' SE = {se_np_rm:.8f}",
                 "deff": "with-replacement SRS reference ('wr')", "confidence": 0.95,
                 "missing_outcome": "MENTHLTH 77/99/blank excluded as a domain",
                 "target": "49 states + DC (Tennessee absent from the 2024 file; territories excluded)"},
    "generated_at": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat(),
}
write_json(ART / "manifest.json", manifest)
print(f"wrote {len(FACTS)} facts, {len(ledgers)} ledgers, {len(list(FIG.glob('*.json')))} figures")
