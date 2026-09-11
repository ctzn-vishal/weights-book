#!/usr/bin/env python
"""ch3lab -- "Lab: Which State Differences Are Real?" (attached to Chapter 3).

    python build.py            regenerate artifacts/ from the IPUMS parquet (one read)
    python build.py --cache    reuse _scratch/cells_2024.parquet and _scratch/svy_check.json

Run order for a full validation: build.py -> verify.R -> build.py (the second run records
the R comparison in artifacts/manifest.json and adds the fact that cites it).

Data: IPUMS USA, ACS 2024 1-year (SAMPLE 202401). The person file
analysis/usa/acs/part_2020_2024.parquet is joined 1:1 on SAMPLE+SERIAL+PERNUM to the
person replicate weights REPWTP1-REPWTP80 in analysis/usa/acs_repwt/part_2020_2024.parquet.

Estimand: for each state (50 + DC), the share of civilian noninstitutionalized adults
aged 19-64 with no health insurance coverage at interview (uninsured = HCOVANY == 1).
IPUMS approximation of the Census universe: drop institutional group quarters (GQ = 3)
and people in the Armed Forces (EMPSTATD 13-15).

Variance: successive difference replication (SDR), Var = (4/80) * sum_r (theta_r - theta)^2,
df = 79, computed by hand with the constants of aggregate/_shared/build_rep.py. A difference
between two states gets the same formula applied to the difference, which carries the
replicate covariance.

One read of the two files builds an in-memory join; from it come (i) one aggregated cell
table (sums of PERWT, PERWT^2 and REPWTP1-80 by state x sex x age band x GQ x armed forces x
uninsured), which serves both the lab and the PUMS verification check, and (ii) one state's
microdata for the svy check. Validation: R `survey` (verify.R -> _scratch/verify_R.json),
svy 0.28's replication path, and the Census PUMS verification estimates for 2024.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("NO_COLOR", "1")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

import duckdb
import numpy as np
import polars as pl
from scipy import stats

# ---------------------------------------------------------------- paths and constants
HERE = Path(__file__).resolve().parent
IPUMS = HERE.parents[2]
DATA_REL = "analysis/usa/acs/part_2020_2024.parquet"
REPWT_REL = "analysis/usa/acs_repwt/part_2020_2024.parquet"
DATA = (IPUMS / DATA_REL).as_posix()
REPWT = (IPUMS / REPWT_REL).as_posix()
ART = HERE / "artifacts"
FIG = ART / "figures"
SCR = HERE / "_scratch"
CELLS_CACHE = SCR / "cells_2024.parquet"
SVY_CACHE = SCR / "svy_check.json"
TARGETS = SCR / "verify_targets.json"
R_RESULTS = SCR / "verify_R.json"

KEY, SLUG = "ch3lab", "ch03-lab-replicates"
SAMPLE = 202401
R = 80                          # person replicate weights REPWTP1-80
C = 4.0 / R                     # SDR constant, 0.05
DF = R - 1                      # 79
Z90 = 1.645                     # ACS published 90% margin of error multiplier
T95 = float(stats.t.ppf(0.975, DF))
T90 = float(stats.t.ppf(0.95, DF))
AGE_MIN, AGE_MAX = 19, 64
TOP_K = 10
GAP_MAX = 12
ALPHA_FAMILY = 0.10
RESCALE = math.sqrt(C * R)      # = 2: one SDR replicate deviation carries Var/4

# State names the prose uses. The build fails if the data stop supporting them.
PROSE = {"rank1": "Texas", "rank2": "Georgia", "rank3": "Oklahoma", "rank9": "Wyoming",
         "rank10": "Arizona", "rank11": "Tennessee", "rank51": "Massachusetts",
         "median": "Indiana", "ratio_min": "Oklahoma", "ratio_max": "Minnesota",
         "largest": "California", "n_min": "Wyoming", "n_max": "California"}

SOURCE = ("IPUMS USA, ACS 2024 1-year sample (analysis/usa/acs + acs_repwt, "
          "part_2020_2024.parquet; PERWT and REPWTP1-80)")
UNIVERSE_TXT = ("civilian noninstitutionalized adults aged 19-64 in the 50 states and DC, 2024 "
                "(IPUMS approximation: excludes institutional group quarters and the Armed Forces)")
PUMS_URL = "https://www2.census.gov/programs-surveys/acs/tech_docs/pums/estimates/pums_estimates_24.csv"

STATES = {  # FIPS: (name, USPS)
    1: ("Alabama", "AL"), 2: ("Alaska", "AK"), 4: ("Arizona", "AZ"), 5: ("Arkansas", "AR"),
    6: ("California", "CA"), 8: ("Colorado", "CO"), 9: ("Connecticut", "CT"),
    10: ("Delaware", "DE"), 11: ("District of Columbia", "DC"), 12: ("Florida", "FL"),
    13: ("Georgia", "GA"), 15: ("Hawaii", "HI"), 16: ("Idaho", "ID"), 17: ("Illinois", "IL"),
    18: ("Indiana", "IN"), 19: ("Iowa", "IA"), 20: ("Kansas", "KS"), 21: ("Kentucky", "KY"),
    22: ("Louisiana", "LA"), 23: ("Maine", "ME"), 24: ("Maryland", "MD"),
    25: ("Massachusetts", "MA"), 26: ("Michigan", "MI"), 27: ("Minnesota", "MN"),
    28: ("Mississippi", "MS"), 29: ("Missouri", "MO"), 30: ("Montana", "MT"),
    31: ("Nebraska", "NE"), 32: ("Nevada", "NV"), 33: ("New Hampshire", "NH"),
    34: ("New Jersey", "NJ"), 35: ("New Mexico", "NM"), 36: ("New York", "NY"),
    37: ("North Carolina", "NC"), 38: ("North Dakota", "ND"), 39: ("Ohio", "OH"),
    40: ("Oklahoma", "OK"), 41: ("Oregon", "OR"), 42: ("Pennsylvania", "PA"),
    44: ("Rhode Island", "RI"), 45: ("South Carolina", "SC"), 46: ("South Dakota", "SD"),
    47: ("Tennessee", "TN"), 48: ("Texas", "TX"), 49: ("Utah", "UT"), 50: ("Vermont", "VT"),
    51: ("Virginia", "VA"), 53: ("Washington", "WA"), 54: ("West Virginia", "WV"),
    55: ("Wisconsin", "WI"), 56: ("Wyoming", "WY"),
}

# Age bands nest both the lab universe (19-64) and the PUMS verification age groups.
AGE_BANDS = [0, 5, 10, 15, 19, 20, 25, 35, 45, 55, 60, 65, 75, 85]
UNIVERSE = (pl.col("age_lo").is_between(19, 60) & (pl.col("gq") != 3) & ~pl.col("armed"))
UNIVERSE_SQL = f"age BETWEEN {AGE_MIN} AND {AGE_MAX} AND gq <> 3 AND NOT armed"

# ---------------------------------------------------------------- PUMS verification targets
# Transcribed from PUMS_URL (read 2026-09-10). Texas, Wyoming, and the US were read twice,
# independently, and agreed digit for digit; every geography passes the additive checks in
# check_pums_transcription(). (estimate, SE) in CHAR_ORDER.
CHAR_ORDER = [
    "Total population", "Housing unit population (RELSHIPP=20-36)",
    "GQ population (RELSHIPP=37-38)", "GQ institutional population (RELSHIPP=37)",
    "GQ noninstitutional population (RELSHIPP=38)", "Total males (SEX=1)",
    "Total females (SEX=2)", "Age 0-4", "Age 5-9", "Age 10-14", "Age 15-19", "Age 20-24",
    "Age 25-34", "Age 35-44", "Age 45-54", "Age 55-59", "Age 60-64", "Age 65-74",
    "Age 75-84", "Age 85 and over",
]
PUMS_FULL = {
    "US": [(340110990, 4), (331722429, 4), (8388561, 0), (3636168, 722), (4752393, 722),
           (168251655, 28762), (171859335, 28762), (18305390, 19304), (19810778, 46983),
           (21381552, 46278), (22401238, 28090), (22277920, 32772), (46117271, 33769),
           (46107741, 27990), (40812983, 31617), (19944714, 43180), (21705766, 45792),
           (35599841, 20527), (19312755, 30050), (6333041, 27210)],
    48: [(31290831, 0), (30665006, 0), (625825, 0), (371535, 265), (254290, 265),
         (15604358, 7659), (15686473, 7659), (1951852, 4384), (2103124, 13566),
         (2217796, 13587), (2267401, 8084), (2167378, 8423), (4523429, 9914),
         (4495194, 8653), (3825273, 7613), (1657802, 12397), (1711673, 11550),
         (2631843, 5190), (1332955, 7186), (405111, 6558)],
    56: [(587618, 0), (573820, 0), (13798, 0), (6504, 3), (7294, 3), (301673, 1948),
         (285945, 1948), (29232, 1160), (30661, 1548), (40636, 1692), (39840, 1453),
         (37613, 1678), (75561, 1827), (79245, 1339), (67498, 1339), (33165, 2520),
         (36659, 1828), (71021, 1204), (35462, 1249), (11025, 1175)],
    50: [(648493, 0), (623524, 0), (24969, 0), (5048, 5), (19921, 5), (318137, 1413),
         (330356, 1413), (26513, 917), (28443, 1669), (35454, 1827), (42467, 1945),
         (41747, 1908), (75200, 1149), (83657, 1272), (76556, 1062), (38699, 2064),
         (51284, 2137), (87964, 818), (46258, 1133), (14251, 1143)],
    11: [(702250, 0), (664748, 0), (37502, 0), (5802, 3), (31700, 3), (332481, 1128),
         (369769, 1128), (39054, 524), (40783, 2333), (32365, 2293), (36921, 1328),
         (52711, 1456), (150703, 966), (120818, 858), (74833, 642), (33118, 1770),
         (30205, 1693), (50285, 736), (31388, 947), (9066, 742)],
}
PUMS_PART = {
    6: {"Total population": (39431263, 0), "Total males (SEX=1)": (19674357, 7055),
        "Age 20-24": (2580829, 7300), "Age 25-34": (5693257, 8106),
        "Age 35-44": (5619566, 6588), "Age 45-54": (4861624, 6135),
        "Age 55-59": (2325221, 14019), "Age 60-64": (2354828, 14540)},
    25: {"Total population": (7136171, 0), "Total males (SEX=1)": (3480184, 2655),
         "Age 20-24": (496403, 3328), "Age 25-34": (1000140, 3014),
         "Age 35-44": (964290, 2823), "Age 45-54": (840736, 2491),
         "Age 55-59": (456119, 5416), "Age 60-64": (478642, 5460)},
}
PUMS_AGE = {"Age 0-4": [0], "Age 5-9": [5], "Age 10-14": [10], "Age 15-19": [15, 19],
            "Age 20-24": [20], "Age 25-34": [25], "Age 35-44": [35], "Age 45-54": [45],
            "Age 55-59": [55], "Age 60-64": [60], "Age 65-74": [65], "Age 75-84": [75],
            "Age 85 and over": [85]}
CHAR_EXPR = {
    "Total population": pl.lit(True),
    "Housing unit population (RELSHIPP=20-36)": pl.col("gq").is_in([1, 2, 5]),
    "GQ population (RELSHIPP=37-38)": pl.col("gq").is_in([3, 4]),
    "GQ institutional population (RELSHIPP=37)": pl.col("gq") == 3,
    "GQ noninstitutional population (RELSHIPP=38)": pl.col("gq") == 4,
    "Total males (SEX=1)": pl.col("sex") == 1,
    "Total females (SEX=2)": pl.col("sex") == 2,
    **{k: pl.col("age_lo").is_in(v) for k, v in PUMS_AGE.items()},
}


# ---------------------------------------------------------------- formatting helpers
def sig(x, k=6):
    """Round a float to k significant digits (compact, deterministic JSON)."""
    if x is None:
        return None
    x = float(x)
    if x == 0 or not math.isfinite(x):
        return x
    return float(f"{x:.{k}g}")


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def pp(x, d=1):
    return f"{100 * x:.{d}f}"


def fint(n):
    return f"{int(round(n)):,}"


def ratio(x, d=2):
    return f"{x:.{d}f}×"


SUP = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def pow10_bound(x: float) -> tuple[int, str]:
    """Smallest power of ten strictly above x, as (exponent, '10⁻ⁿ')."""
    e = -15 if x <= 0 else math.floor(math.log10(x)) + 1
    return e, "10" + str(e).translate(SUP)


def dump(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, sort_keys=True, indent=2, ensure_ascii=False)
        f.write("\n")


# ---------------------------------------------------------------- 1. one read
def read_source():
    """Join the 2024 person file to REPWTP1-80 once, in memory. Returns (con, checks)."""
    t0 = time.time()
    con = duckdb.connect()
    rep = ", ".join(f"REPWTP{i}" for i in range(1, R + 1))
    band = " ".join(f"WHEN AGE < {hi} THEN {lo}" for lo, hi in zip(AGE_BANDS[:-1], AGE_BANDS[1:]))
    con.execute(f"""
CREATE TEMP TABLE j AS
SELECT p.SERIAL AS serial, p.PERNUM::INTEGER AS pernum, p.STATEFIP::INTEGER AS statefip,
       p.SEX::INTEGER AS sex, p.AGE::INTEGER AS age,
       (CASE {band} ELSE {AGE_BANDS[-1]} END)::INTEGER AS age_lo,
       p.GQ::INTEGER AS gq, COALESCE(p.EMPSTATD IN (13, 14, 15), FALSE) AS armed,
       p.uninsured::INTEGER AS y, p.PERWT AS perwt, (r.SERIAL IS NOT NULL) AS matched,
       {rep}
FROM (SELECT SAMPLE, SERIAL, PERNUM, STATEFIP, SEX, AGE, GQ, EMPSTATD, PERWT, uninsured
      FROM read_parquet('{DATA}') WHERE SAMPLE = {SAMPLE}) p
LEFT JOIN (SELECT SAMPLE, SERIAL, PERNUM, {rep}
           FROM read_parquet('{REPWT}') WHERE SAMPLE = {SAMPLE}) r
USING (SAMPLE, SERIAL, PERNUM)""")
    t_read = time.time() - t0
    n_r, n_r_keys = con.sql(
        f"SELECT COUNT(*), COUNT(DISTINCT (SERIAL, PERNUM)) FROM read_parquet('{REPWT}') "
        f"WHERE SAMPLE = {SAMPLE}").fetchone()
    n_j, n_matched, n_null_y = con.sql(
        "SELECT COUNT(*), SUM(matched::INTEGER), SUM((y IS NULL)::INTEGER) FROM j").fetchone()
    neg_rows = con.sql(f"SELECT SUM((LEAST({rep}) < 0)::INTEGER) FROM j").fetchone()[0]
    n_armed_1964 = con.sql(
        f"SELECT SUM(armed::INTEGER) FROM j WHERE age BETWEEN {AGE_MIN} AND {AGE_MAX}").fetchone()[0]
    n_inst_1964 = con.sql(
        f"SELECT SUM((gq = 3)::INTEGER) FROM j WHERE age BETWEEN {AGE_MIN} AND {AGE_MAX}").fetchone()[0]
    assert n_j == n_r == n_r_keys == n_matched, (n_j, n_r, n_r_keys, n_matched)
    assert n_null_y == 0, n_null_y
    checks = {
        "persons_2024": int(n_j), "repwt_rows_2024": int(n_r), "repwt_distinct_keys": int(n_r_keys),
        "matched": int(n_matched), "join": "1:1 on SAMPLE+SERIAL+PERNUM (every 2024 person matched once)",
        "null_uninsured": int(n_null_y), "rows_with_any_negative_replicate_weight": int(neg_rows),
        "excluded_armed_forces_19_64": int(n_armed_1964), "excluded_institutional_gq_19_64": int(n_inst_1964),
        "seconds_read_join": round(t_read, 1),
    }
    return con, checks


def cell_table(con) -> pl.DataFrame:
    rsum = ", ".join(f"SUM(REPWTP{i}) AS sw{i}" for i in range(1, R + 1))
    return con.sql(f"""
SELECT statefip, sex, age_lo, gq, armed, y, COUNT(*) AS n,
       SUM(perwt) AS sw0, SUM(perwt * perwt) AS sww0, {rsum}
FROM j GROUP BY statefip, sex, age_lo, gq, armed, y
ORDER BY statefip, sex, age_lo, gq, armed, y""").pl()


def microdata(con, fips: int) -> pl.DataFrame:
    rep = ", ".join(f"REPWTP{i}" for i in range(1, R + 1))
    return con.sql(f"""
SELECT y::DOUBLE AS uninsured, perwt AS PERWT, {rep}
FROM j WHERE statefip = {fips} AND {UNIVERSE_SQL}
ORDER BY serial, pernum""").pl()


# ---------------------------------------------------------------- 2. estimates
def domain(cells: pl.DataFrame, mask: pl.Expr):
    wcols = [f"sw{k}" for k in range(R + 1)]
    agg = (cells.filter(mask).group_by("statefip").agg(
        [pl.col("n").sum(), pl.col("sww0").sum(),
         (pl.col("sww0") * pl.col("y")).sum().alias("swwy0")]
        + [pl.col(c).sum() for c in wcols]
        + [(pl.col(c) * pl.col("y")).sum().alias("y" + c) for c in wcols])
        .sort("statefip"))
    return {"fips": agg["statefip"].to_numpy(), "n": agg["n"].to_numpy().astype(np.int64),
            "sww": agg["sww0"].to_numpy(), "swwy": agg["swwy0"].to_numpy(),
            "SW": agg.select(wcols).to_numpy(), "SWY": agg.select(["y" + c for c in wcols]).to_numpy()}


def estimates(dm):
    TH = dm["SWY"] / dm["SW"]
    th0 = TH[:, 0]
    dev = TH[:, 1:] - th0[:, None]
    n = dm["n"].astype(float)
    sw0 = dm["SW"][:, 0]
    se_sdr = np.sqrt(C * (dev ** 2).sum(axis=1))
    se_iid = np.sqrt(th0 * (1 - th0) / n)
    se_wo = np.sqrt(n / (n - 1) * (dm["swwy"] * (1 - 2 * th0) + th0 ** 2 * dm["sww"]) / sw0 ** 2)
    kish = n * dm["sww"] / sw0 ** 2
    return {"th0": th0, "reps": TH[:, 1:], "dev": dev, "se_sdr": se_sdr, "se_iid": se_iid,
            "se_wo": se_wo, "kish": kish, "n": dm["n"], "sw0": sw0}


def national(dm):
    SW, SWY = dm["SW"].sum(axis=0), dm["SWY"].sum(axis=0)
    th = SWY / SW
    dev = th[1:] - th[0]
    n = int(dm["n"].sum())
    p = th[0]
    sww, swwy = dm["sww"].sum(), dm["swwy"].sum()
    return {"th0": p, "dev": dev, "se_sdr": float(np.sqrt(C * (dev ** 2).sum())),
            "se_iid": float(np.sqrt(p * (1 - p) / n)),
            "se_wo": float(np.sqrt(n / (n - 1) * (swwy * (1 - 2 * p) + p ** 2 * sww) / SW[0] ** 2)),
            "n": n, "sw0": float(SW[0])}


# ---------------------------------------------------------------- 3. PUMS verification
def check_pums_transcription():
    ix = {c: i for i, c in enumerate(CHAR_ORDER)}
    ages = [c for c in CHAR_ORDER if c.startswith("Age")]
    for geo, rows in PUMS_FULL.items():
        e = [r[0] for r in rows]
        s = [r[1] for r in rows]
        tot = e[ix["Total population"]]
        assert sum(e[ix[a]] for a in ages) == tot, geo
        assert e[ix["Total males (SEX=1)"]] + e[ix["Total females (SEX=2)"]] == tot, geo
        assert e[ix["Housing unit population (RELSHIPP=20-36)"]] + e[ix["GQ population (RELSHIPP=37-38)"]] == tot, geo
        assert (e[ix["GQ institutional population (RELSHIPP=37)"]]
                + e[ix["GQ noninstitutional population (RELSHIPP=38)"]]
                == e[ix["GQ population (RELSHIPP=37-38)"]]), geo
        assert s[ix["Total males (SEX=1)"]] == s[ix["Total females (SEX=2)"]], geo


def pums_check(cells: pl.DataFrame):
    check_pums_transcription()
    targets = []
    for geo, rows in PUMS_FULL.items():
        targets += [(geo, c, e, s) for c, (e, s) in zip(CHAR_ORDER, rows)]
    for geo, d in PUMS_PART.items():
        targets += [(geo, c, e, s) for c, (e, s) in d.items()]
    wcols = [f"sw{k}" for k in range(R + 1)]
    out = []
    for geo, char, pub_e, pub_s in targets:
        sub = cells if geo == "US" else cells.filter(pl.col("statefip") == geo)
        T = sub.filter(CHAR_EXPR[char]).select([pl.col(c).sum() for c in wcols]).to_numpy()[0]
        est = float(T[0])
        se = float(np.sqrt(C * ((T[1:] - T[0]) ** 2).sum()))
        out.append({"geo": "US" if geo == "US" else STATES[geo][1], "characteristic": char,
                    "published_estimate": pub_e, "published_se": pub_s,
                    "ipums_estimate": int(round(est)), "ipums_se": round(se, 2),
                    "estimate_exact": abs(est - pub_e) < 0.5,
                    "se_within_rounding": abs(se - pub_s) <= 0.5 + 1e-9,
                    "se_abs_diff": round(abs(se - pub_s), 3)})
    return out


# ---------------------------------------------------------------- 4. svy check
def run_svy(micro: pl.DataFrame) -> dict:
    import svy
    design = svy.Design(wgt="PERWT", rep_wgts=svy.SdrWgts(prefix="REPWTP", n_reps=R))
    s = svy.Sample(micro, design=design)
    e_def = s.estimation.mean("uninsured")
    e_rep = s.estimation.mean("uninsured", method="replication", variance_center="estimate")
    d = e_def.to_polars().row(0, named=True)
    r = e_rep.to_polars().row(0, named=True)
    out = {"n": micro.height,
           "default": {"est": d["est"], "se": d["se"], "df": int(d["df"]), "method": str(e_def.method)},
           "replication": {"est": r["est"], "se": r["se"], "df": int(r["df"]), "method": str(e_rep.method)},
           "call_default": 'Sample(df, Design(wgt="PERWT", rep_wgts=SdrWgts(prefix="REPWTP", n_reps=80))).estimation.mean("uninsured")',
           "call_replication": '... .estimation.mean("uninsured", method="replication", variance_center="estimate")',
           "svy_version": svy.__version__}
    assert out["replication"]["df"] == DF, out
    return out


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", action="store_true", help="reuse _scratch cell table and svy results")
    args = ap.parse_args()
    t0 = time.time()
    SCR.mkdir(exist_ok=True)

    con = None
    if args.cache and CELLS_CACHE.exists() and SVY_CACHE.exists():
        cells = pl.read_parquet(CELLS_CACHE)
        read_checks = json.loads(SVY_CACHE.read_text(encoding="utf-8"))["read_checks"]
        print(f"cache: {CELLS_CACHE.name} ({cells.height} cells)")
    else:
        con, read_checks = read_source()
        cells = cell_table(con)
        cells.write_parquet(CELLS_CACHE)
        print(f"read+join {read_checks['seconds_read_join']}s; {cells.height} cells")

    # ---- the lab: per-state estimates
    dm = domain(cells, UNIVERSE)
    E = estimates(dm)
    fips = [int(f) for f in dm["fips"]]
    S = len(fips)
    assert S == 51 and set(fips) == set(STATES), fips
    names = [STATES[f][0] for f in fips]
    usps = [STATES[f][1] for f in fips]
    th0, dev, se_sdr, se_iid, se_wo = E["th0"], E["dev"], E["se_sdr"], E["se_iid"], E["se_wo"]
    n = E["n"]
    US = national(dm)
    cv = se_sdr / th0
    assert n.min() >= 100, "suppression rule would bite"
    assert cv.max() <= 0.30, "CV flag would bite"

    order = sorted(range(S), key=lambda i: (-th0[i], names[i]))
    rank = np.empty(S, dtype=int)
    for pos, i in enumerate(order):
        rank[i] = pos + 1
    ratio_sdr_iid = se_sdr / se_iid
    ratio_sdr_wo = se_sdr / se_wo

    # ---- pairwise differences, replicate covariance
    D = th0[:, None] - th0[None, :]
    DD = dev[:, None, :] - dev[None, :, :]
    se_D = np.sqrt(C * (DD ** 2).sum(axis=2))
    se_D_indep = np.sqrt(se_sdr[:, None] ** 2 + se_sdr[None, :] ** 2)
    se_D_naive = np.sqrt(se_iid[:, None] ** 2 + se_iid[None, :] ** 2)
    for m_ in (se_D, se_D_indep, se_D_naive):
        np.fill_diagonal(m_, np.inf)
    z_sdr, z_indep, z_naive = np.abs(D) / se_D, np.abs(D) / se_D_indep, np.abs(D) / se_D_naive
    M = S * (S - 1) // 2
    z_bonf = float(stats.norm.ppf(1 - ALPHA_FAMILY / (2 * M)))
    iu = np.triu_indices(S, 1)
    sig_sdr, sig_naive, sig_indep = z_sdr > Z90, z_naive > Z90, z_indep > Z90
    counts = {"pairs": M,
              "sdr": int(sig_sdr[iu].sum()), "naive": int(sig_naive[iu].sum()),
              "sdr_indep": int(sig_indep[iu].sum()), "sdr_t79": int((z_sdr > T90)[iu].sum()),
              "sdr_bonferroni": int((z_sdr > z_bonf)[iu].sum())}
    indep_flips = int((sig_sdr != sig_indep)[iu].sum())
    cov_ratio = se_D[iu] / se_D_indep[iu]

    # rank ranges from pairwise tests (per comparison, 90%)
    def rank_bounds(sigm):
        hi_ = np.array([sum(1 for j in range(S) if th0[j] > th0[i] and sigm[i, j]) for i in range(S)])
        lo_ = np.array([sum(1 for j in range(S) if th0[j] < th0[i] and sigm[i, j]) for i in range(S)])
        return 1 + hi_, S - lo_, hi_ + lo_
    L, U, distinct = rank_bounds(sig_sdr)
    _, _, distinct_naive = rank_bounds(sig_naive)

    adj = [(order[k], order[k + 1]) for k in range(S - 1)]
    adj_sdr = sum(bool(sig_sdr[a, b]) for a, b in adj)
    adj_naive = sum(bool(sig_naive[a, b]) for a, b in adj)
    adj_overlap = sum(bool(th0[a] - Z90 * se_sdr[a] <= th0[b] + Z90 * se_sdr[b]) for a, b in adj)
    gap = []
    for g in range(1, S):
        prs = [(order[k], order[k + g]) for k in range(S - g)]
        gap.append({"g": g, "sdr": float(np.mean([sig_sdr[a, b] for a, b in prs])),
                    "naive": float(np.mean([sig_naive[a, b] for a, b in prs])), "pairs": len(prs)})

    def gap_all(key):
        return next(x["g"] for x in gap if all(y[key] == 1.0 for y in gap if y["g"] >= x["g"]))
    gap_all_sdr, gap_all_naive = gap_all("sdr"), gap_all("naive")

    # ---- replicate re-ranking (what the widget's top-k view does)
    draws = th0[:, None] + RESCALE * dev
    rank_draws = np.empty((S, R), dtype=int)
    for r in range(R):
        o = sorted(range(S), key=lambda i: (-draws[i, r], names[i]))
        for pos, i in enumerate(o):
            rank_draws[i, r] = pos + 1
    top_freq = (rank_draws <= TOP_K).mean(axis=1)
    sure_top = {i for i in range(S) if U[i] <= TOP_K}
    maybe_top = {i for i in range(S) if L[i] <= TOP_K}
    rep_top_any = {i for i in range(S) if top_freq[i] > 0}
    rep_top_all = {i for i in range(S) if top_freq[i] == 1.0}

    # ---- state vs nation: the covariance matters when one domain contains the other
    big = max(range(S), key=lambda i: E["sw0"][i])
    d_us = dev[big] - US["dev"]
    se_state_us_rep = float(np.sqrt(C * (d_us ** 2).sum()))
    se_state_us_ind = float(np.sqrt(se_sdr[big] ** 2 + US["se_sdr"] ** 2))

    # ---- named units and the claims the prose makes about them
    top, top2, top3, bot = order[0], order[1], order[2], order[-1]
    r9, r10, r11 = order[TOP_K - 2], order[TOP_K - 1], order[TOP_K]
    med = order[S // 2]
    rmin, rmax = int(np.argmin(ratio_sdr_iid)), int(np.argmax(ratio_sdr_iid))
    wmin, wmax = int(np.argmin(ratio_sdr_wo)), int(np.argmax(ratio_sdr_wo))
    small, large_n = int(np.argmin(n)), int(np.argmax(n))
    got = {"rank1": names[top], "rank2": names[top2], "rank3": names[top3], "rank9": names[r9],
           "rank10": names[r10], "rank11": names[r11], "rank51": names[bot], "median": names[med],
           "ratio_min": names[rmin], "ratio_max": names[rmax], "largest": names[big],
           "n_min": names[small], "n_max": names[large_n]}
    assert got == PROSE, {k: (PROSE[k], got[k]) for k in PROSE if PROSE[k] != got[k]}
    assert (L[top], U[top]) == (1, 1) and (L[bot], U[bot]) == (S, S)           # "first and last under every test"
    assert th0[top] - Z90 * se_sdr[top] > th0[top2] + Z90 * se_sdr[top2]         # Figure 3L.1 caption
    assert th0[bot] + Z90 * se_sdr[bot] < th0[order[-2]] - Z90 * se_sdr[order[-2]]
    assert adj_overlap >= 40                                                     # "through most of the ranking"
    assert sure_top == rep_top_all and maybe_top == rep_top_any                  # "the same states"
    assert top_freq[r10] > top_freq[r9]                                          # predict-first answer
    assert 0.8 < np.median(ratio_sdr_wo) < 1.25 and ratio_sdr_wo.min() < 1 < ratio_sdr_wo.max()  # "misses in both directions"
    assert se_state_us_rep < se_state_us_ind

    # ---- svy check (third implementation) on the top-ranked state
    if con is not None:
        micro = microdata(con, fips[top])
        assert micro.height == int(n[top]), (micro.height, n[top])
        t_svy = time.time()
        svy_res = run_svy(micro)
        svy_res["seconds"] = round(time.time() - t_svy, 1)
        svy_res["state"] = usps[top]
        svy_res["read_checks"] = read_checks
        dump(svy_res, SVY_CACHE)
    else:
        svy_res = json.loads(SVY_CACHE.read_text(encoding="utf-8"))
    assert svy_res["state"] == usps[top], "svy cache is for another state; rerun without --cache"
    svy_rep_diff = abs(svy_res["replication"]["se"] - se_sdr[top])
    svy_def_vs_wo = abs(svy_res["default"]["se"] - se_wo[top]) / se_wo[top]
    assert svy_rep_diff < 1e-9 and svy_def_vs_wo < 1e-6
    assert svy_res["default"]["df"] == svy_res["n"] - 1

    # ---- PUMS verification
    pums = pums_check(cells)
    pums_est_ok = sum(r["estimate_exact"] for r in pums)
    pums_se_ok = sum(r["se_within_rounding"] for r in pums)
    pums_nonzero = [r for r in pums if r["published_se"] > 0]
    pums_bad = [r for r in pums if not (r["estimate_exact"] and r["se_within_rounding"])]
    us_total = float(cells["sw0"].sum())

    # ---- targets for verify.R, and its results if present
    tstates = sorted({fips[order[0]], fips[order[1]], fips[order[9]], fips[order[10]], fips[med],
                      fips[order[S // 2 + 1]], fips[order[-1]], fips[small]})
    tpairs = [[fips[order[0]], fips[order[1]]], [fips[order[9]], fips[order[10]]],
              [fips[med], fips[order[S // 2 + 1]]]]
    dump({"sample": SAMPLE, "age_min": AGE_MIN, "age_max": AGE_MAX, "n_reps": R,
          "states": tstates, "pairs": tpairs}, TARGETS)
    fidx = {f: i for i, f in enumerate(fips)}
    r_val = None
    if R_RESULTS.exists():
        rr = json.loads(R_RESULTS.read_text(encoding="utf-8"))
        st = {int(x["fips"]): x for x in rr["states"]}
        if sorted(st) == tstates and [[p["a"], p["b"]] for p in rr["pairs"]] == tpairs:
            def num(x):  # jsonlite writes 1 x 1 matrices as nested arrays
                return float(np.asarray(x, dtype=float).ravel()[0])
            d_est = max(abs(num(st[f]["estimate"]) - th0[fidx[f]]) for f in tstates)
            d_se = max(abs(num(st[f]["se_successive_difference"]) - se_sdr[fidx[f]]) for f in tstates)
            d_se_oth = max(abs(num(st[f]["se_other_scale_4_80"]) - se_sdr[fidx[f]]) for f in tstates)
            d_n = max(abs(int(num(st[f]["n"])) - int(n[fidx[f]])) for f in tstates)
            d_pair = max(abs(num(p["se_diff"]) - se_D[fidx[p["a"]], fidx[p["b"]]]) for p in rr["pairs"])
            d_pdiff = max(abs(num(p["diff"]) - D[fidx[p["a"]], fidx[p["b"]]]) for p in rr["pairs"])
            d_all = max(d_est, d_se, d_se_oth, d_pair, d_pdiff)
            r_val = {"check": "hand-coded SDR vs R survey",
                     "oracle": rr["engine"], "call": rr["call"],
                     "states": [STATES[f][1] for f in tstates],
                     "pairs": [f"{STATES[a][1]}-{STATES[b][1]}" for a, b in tpairs],
                     "rows": rr["rows"], "degf": rr["degf"], "scale": rr["scale"],
                     "rscales": rr["rscales_unique"], "mse": rr["mse"],
                     "max_abs_diff_estimate": float(f"{d_est:.3g}"),
                     "max_abs_diff_se": float(f"{d_se:.3g}"),
                     "max_abs_diff_se_type_other": float(f"{d_se_oth:.3g}"),
                     "max_abs_diff_pair_estimate": float(f"{d_pdiff:.3g}"),
                     "max_abs_diff_pair_se": float(f"{d_pair:.3g}"),
                     "max_abs_diff_all": float(f"{d_all:.3g}"),
                     "max_abs_diff_n": int(d_n),
                     "tolerance": 1e-9,
                     "pass": bool(d_all < 1e-9 and d_n == 0 and rr["degf"] == DF)}
            assert r_val["pass"], r_val
        else:
            print("verify_R.json is stale (targets changed): rerun verify.R")

    # ================================================================ artifacts
    FIG.mkdir(parents=True, exist_ok=True)

    def base(value, display, estimand, unit, variance="replicate_sdr(80)", se=None, dfv=None,
             nn=None, note="", weight="PERWT", benchmark=None):
        return {"value": value, "display": display, "unit": unit, "se": se, "ci_low": None,
                "ci_high": None, "ci_display": None, "df": dfv, "n": nn, "weight": weight,
                "variance": variance, "estimand": estimand, "source": SOURCE,
                "benchmark": benchmark, "note": note}

    def est_fact(i=None, est=None, se=None, nn=None, estimand=""):
        if i is not None:
            est, se, nn = th0[i], se_sdr[i], int(n[i])
        lo, hi = est - T95 * se, est + T95 * se
        f = base(sig(est), pct(est), estimand, "proportion", se=sig(se), dfv=DF, nn=nn,
                 note="95% CI uses t with 79 df; the rank table uses the ACS 90% MOE (1.645 x SE).")
        f.update({"ci_low": sig(lo), "ci_high": sig(hi), "ci_display": f"{pct(lo)}–{pct(hi)}"})
        return f

    def count_fact(v, estimand, variance="replicate_sdr(80)", note="", unit="count", disp=None):
        return base(v, disp if disp is not None else fint(v), estimand, unit, variance=variance, note=note)

    def share_fact(v, estimand, variance="replicate_sdr(80)", unit="share", note=""):
        return base(sig(v), f"{100 * v:.0f}%", estimand, unit, variance=variance, note=note)

    def ratio_fact(v, estimand, note=""):
        return base(sig(v), ratio(v), estimand, "ratio of standard errors", note=note)

    def se_fact(v, estimand, variance, nn, dfv, note=""):
        return base(sig(v), pp(v, 2), estimand, "percentage points (standard error)",
                    variance=variance, se=None, dfv=dfv, nn=nn, note=note)

    U_ = f"Uninsured rate among {UNIVERSE_TXT}"
    PAIRS = f"Number of the {M:,} pairs of states (50 + DC)"
    TEST = "distinguishable at the 90% level (|difference| / SE of the difference > 1.645, per comparison)"
    WO = ("weights-only SE: with-replacement linearization treating each person as a PSU, n/(n-1) "
          "factor; identical to svy's default call.")
    F = {}
    F["us_rate"] = est_fact(est=US["th0"], se=US["se_sdr"], nn=US["n"], estimand=U_ + "; all states pooled.")
    F["us_n"] = count_fact(US["n"], f"Unweighted sample size: {UNIVERSE_TXT}.", variance="none")
    F["n_min"] = count_fact(int(n[small]), f"Unweighted sample size in the smallest state sample ({names[small]}).", variance="none")
    F["n_max"] = count_fact(int(n[large_n]), f"Unweighted sample size in the largest state sample ({names[large_n]}).", variance="none")
    F["top_rate"] = est_fact(top, estimand=f"{U_}: {names[top]} (rank 1).")
    F["bottom_rate"] = est_fact(bot, estimand=f"{U_}: {names[bot]} (rank 51).")
    F["top_se_sdr"] = se_fact(se_sdr[top], f"{U_}: {names[top]}, hand-coded SDR standard error.", "replicate_sdr(80)", int(n[top]), DF)
    F["top_se_iid"] = se_fact(se_iid[top], f"{U_}: {names[top]}, naive iid standard error sqrt(p(1-p)/n).", "none", int(n[top]), None,
                              note="The naive analysis: treats the ACS as a simple random sample of independent people.")
    F["ratio_median"] = ratio_fact(float(np.median(ratio_sdr_iid)), "Median across the 51 states of SE(SDR) / SE(naive iid).",
                                   note="naive iid SE = sqrt(p(1-p)/n).")
    F["ratio_min"] = ratio_fact(ratio_sdr_iid[rmin], f"SE(SDR) / SE(naive iid), smallest across states: {names[rmin]}.")
    F["ratio_max"] = ratio_fact(ratio_sdr_iid[rmax], f"SE(SDR) / SE(naive iid), largest across states: {names[rmax]}.")
    F["ratio_us"] = ratio_fact(US["se_sdr"] / US["se_iid"], "SE(SDR) / SE(naive iid) for the pooled national rate.")
    # Why the national ratio exceeds every state's (integrator addition). Linearized with the
    # full-sample state shares, the national variance is a'Va, V = replicate covariance of the
    # state estimates. Each pair covaries only slightly, but there are 51 x 50 cross terms.
    shares = E["sw0"] / E["sw0"].sum()
    cov_st = C * dev @ dev.T
    var_own = float((shares ** 2 * np.diag(cov_st)).sum())
    var_all = float(shares @ cov_st @ shares)
    assert abs(var_all - US["se_sdr"] ** 2) / US["se_sdr"] ** 2 < 0.05, "linearization no longer matches the national replicate variance"
    assert US["se_sdr"] / US["se_iid"] > float(ratio_sdr_iid.max())  # prose: "larger than for any state"
    corr_st = cov_st / np.sqrt(np.outer(np.diag(cov_st), np.diag(cov_st)))
    cross_corr = float(corr_st[~np.eye(S, dtype=bool)].mean())
    F["us_cov_share"] = share_fact(1 - var_own / var_all,
                                   "Share of the national rate's replicate variance contributed by covariances between different "
                                   "states' estimates (linearized with full-sample state population shares).")
    F["us_se_over_indep"] = ratio_fact(US["se_sdr"] / np.sqrt(var_own),
                                       "SE(SDR) of the national rate divided by the SE it would have if the 51 state estimates were independent.")
    F["cross_corr_mean"] = base(sig(cross_corr), f"{cross_corr:.2f}",
                                "Mean correlation between two different states' replicate deviations, over all pairs of states.",
                                "correlation")
    F["ratio_wo_min"] = ratio_fact(ratio_sdr_wo[wmin], f"SE(SDR) / weights-only SE, smallest across states: {names[wmin]}.", note=WO)
    F["ratio_wo_max"] = ratio_fact(ratio_sdr_wo[wmax], f"SE(SDR) / weights-only SE, largest across states: {names[wmax]}.", note=WO)
    F["pairs_total"] = count_fact(M, "Number of distinct pairs among 51 units (50 states + DC).", variance="none")
    F["pairs_sig_naive"] = count_fact(counts["naive"], f"{PAIRS} {TEST}, using naive iid SEs and assuming independence.",
                                      variance="none", note="The defensible-looking wrong answer.")
    F["pairs_sig_sdr"] = count_fact(counts["sdr"], f"{PAIRS} {TEST}, SE of each difference from the replicates (covariance included).")
    F["pairs_sig_bonf"] = count_fact(counts["sdr_bonferroni"], f"{PAIRS} distinguishable with a Bonferroni family-wise 10% level, SDR SE of each difference.",
                                     note=f"Bonferroni critical value {z_bonf:.2f} for {M} comparisons.")
    F["indep_flips"] = count_fact(indep_flips, f"{PAIRS} whose 90% verdict changes when the SE of the difference uses sqrt(SE_a^2 + SE_b^2) instead of the replicate covariance.")
    F["state_us_se_rep"] = se_fact(se_state_us_rep, f"SE of {names[big]}'s rate minus the national rate, from the replicates (covariance included).", "replicate_sdr(80)", None, DF)
    F["state_us_se_ind"] = se_fact(se_state_us_ind, f"SE of {names[big]}'s rate minus the national rate, wrongly assuming independence.", "replicate_sdr(80)", None, DF,
                                   note="The nation contains the state, so the two estimates are positively correlated.")
    F["adj_sig_naive"] = count_fact(adj_naive, "Of the 50 pairs adjacent in the ranking, the number distinguishable at the 90% level with naive iid SEs.", variance="none")
    F["adj_sig_sdr"] = count_fact(adj_sdr, "Of the 50 pairs adjacent in the ranking, the number distinguishable at the 90% level with SDR SEs of the difference.")
    F["gap1_sdr"] = share_fact(gap[0]["sdr"], "Share of the 50 pairs one place apart in the ranking that are distinguishable (SDR, 90%).", unit="share of pairs")
    F["gap1_naive"] = share_fact(gap[0]["naive"], "Share of the 50 pairs one place apart in the ranking that are distinguishable (naive iid, 90%).", variance="none", unit="share of pairs")
    F["gap_all_sdr"] = count_fact(gap_all_sdr, "Smallest distance in rank from which every pair of states that far apart or farther is distinguishable (SDR, 90%).", unit="ranks")
    F["gap_all_naive"] = count_fact(gap_all_naive, "Same, naive iid SEs.", variance="none", unit="ranks")
    F["median_rank_range"] = count_fact(f"{L[med]}-{U[med]}", f"Ranks consistent with every pairwise 90% test for {names[med]}, the median (26th) state.",
                                        unit="rank range", disp=f"{L[med]}–{U[med]}")
    F["median_distinct"] = count_fact(int(distinct[med]), f"Number of the other 50 units that {names[med]} is distinguishable from at the 90% level (SDR).")
    F["median_distinct_naive"] = count_fact(int(distinct_naive[med]), f"Number of the other 50 units that {names[med]} is distinguishable from at the 90% level (naive iid).", variance="none")
    F["sure_top"] = count_fact(len(sure_top), f"States in the top {TOP_K} under every ranking consistent with the pairwise 90% tests (SDR).")
    F["maybe_top"] = count_fact(len(maybe_top), f"States that could be in the top {TOP_K} under the pairwise 90% tests (SDR).")
    F["rep_top_all"] = count_fact(len(rep_top_all), f"States in the top {TOP_K} on all 80 rescaled SDR replicates.")
    F["rep_top_any"] = count_fact(len(rep_top_any), f"States in the top {TOP_K} on at least one of the 80 rescaled SDR replicates.")
    for key_, i_, rk in (("r9", r9, TOP_K - 1), ("r10", r10, TOP_K), ("r11", r11, TOP_K + 1)):
        F[f"{key_}_top_freq"] = share_fact(top_freq[i_], f"Share of the 80 rescaled SDR replicates (deviations x 2) in which {names[i_]} (rank {rk}) is in the top {TOP_K}.",
                                           unit="share of replicates",
                                           note="Frequencies move in steps of 1/80. Replicates approximate sampling spread; they are not posterior draws.")
    F["r9_n"] = count_fact(int(n[r9]), f"Unweighted sample size, {names[r9]} (rank 9).", variance="none")
    F["r10_n"] = count_fact(int(n[r10]), f"Unweighted sample size, {names[r10]} (rank 10).", variance="none")
    F["svy_default_se"] = se_fact(svy_res["default"]["se"], f"{U_}: {names[top]}, SE from svy 0.28's default mean() call with replicate weights declared.",
                                  "taylor", svy_res["n"], svy_res["default"]["df"],
                                  note="svy silently ignores the declared replicate weights and linearizes with each person as a PSU.")
    F["svy_default_df"] = count_fact(svy_res["default"]["df"], f"Degrees of freedom reported by the same default svy call ({names[top]}): n - 1.", variance="taylor")
    F["svy_rep_se"] = se_fact(svy_res["replication"]["se"], f"{U_}: {names[top]}, SE from svy with method='replication', variance_center='estimate'.",
                              "replicate_sdr(80)", svy_res["n"], svy_res["replication"]["df"])
    F["pums_rows"] = count_fact(len(pums), "Published PUMS verification rows checked (person totals for the US and six states).")
    F["pums_est_exact"] = count_fact(pums_est_ok, "Of those rows, the number whose IPUMS weighted total equals the published PUMS estimate exactly.")
    F["pums_se_ok"] = count_fact(pums_se_ok, "Of those rows, the number whose hand-coded SDR SE matches the published PUMS SE to the published integer rounding.")
    F["pums_us_total"] = count_fact(int(round(us_total)), "Sum of PERWT over all 2024 ACS persons (US resident population).")
    F["pums_us_total"]["benchmark"] = f"External benchmark: Census PUMS verification file, US total population 340,110,990 ({PUMS_URL})"
    if r_val:
        _, disp10 = pow10_bound(r_val["max_abs_diff_all"])
        F["r_max_diff"] = count_fact(r_val["max_abs_diff_all"],
                                     "Upper bound on the largest absolute difference between hand-coded and R survey results "
                                     "(estimates, SEs, pairwise differences and their SEs; proportion scale).",
                                     unit="absolute difference (bound)", disp=disp10,
                                     note=f"Largest observed difference {r_val['max_abs_diff_all']:.2g}.")
    # Displays that read better than the helpers' defaults: replicate frequencies as exact
    # counts out of 80 (they move in steps of 1/80), and the state-vs-nation SEs with a third
    # decimal so the contrast is visible.
    for key_, i_ in (("r9", r9), ("r10", r10), ("r11", r11)):
        F[f"{key_}_top_freq"]["display"] = f"{int(round(top_freq[i_] * R))} of {R}"
    for key_, v_ in (("state_us_se_rep", se_state_us_rep), ("state_us_se_ind", se_state_us_ind)):
        F[key_]["display"] = pp(v_, 3)
    assert pct(th0[r9]) == pct(th0[r10])        # prose: "equal to one decimal place"
    facts = {"key": KEY, "facts": dict(sorted(F.items()))}

    # ---- ledger
    ledger = {"key": KEY, "ledgers": {"state_uninsured": {
        "title": "Which state differences in the uninsured rate are real? (ACS 2024)",
        "target_population": ("Civilian noninstitutionalized adults aged 19 to 64 in each of the 50 states and DC in 2024. "
                              "IPUMS approximation: residents of institutional group quarters and members of the Armed Forces "
                              "are dropped; noninstitutional group quarters (college dorms, shelters) stay in."),
        "estimand": ("For each state, the share of that population with no health insurance coverage at the time of "
                     "interview; for every pair of states, the difference between their shares."),
        "estimator": "Weighted share within each state (Hajek ratio): sum of PERWT x uninsured over sum of PERWT; pairwise differences of those shares.",
        "explicit_weights": ("PERWT, the ACS final person weight: the inverse of the selection probability, adjusted for "
                             "nonresponse and calibrated to population controls by the Census Bureau."),
        "implicit_weights": "None beyond PERWT: each estimate is a weighted mean, so a respondent's leverage is his or her share of the state's total weight.",
        "randomness": ("Repeated sampling of addresses and group-quarters residents under the ACS design, with the Census "
                       "Bureau's weighting repeated on each hypothetical sample."),
        "variance_estimator": ("Successive difference replication with the 80 person replicate weights REPWTP1-80: "
                               "Var = (4/80) x sum over r of (theta_r - theta)^2, df = 79. Differences use the replicate "
                               "covariance. 90% margin of error = 1.645 x SE (ACS convention); pairwise tests at the 90% level."),
        "assumptions": ("The replicates reproduce the sampling and weighting variability of the design. PUMS is a subsample "
                        "of the full ACS, so these SEs are larger than those on data.census.gov. Coverage is point-in-time "
                        "and self-reported. Pairwise tests are per comparison; with 1,275 of them some false positives are "
                        "expected, and a Bonferroni family-wise version is stricter."),
        "facts": [f"{KEY}.us_rate", f"{KEY}.top_rate", f"{KEY}.bottom_rate", f"{KEY}.ratio_median",
                  f"{KEY}.pairs_sig_sdr", f"{KEY}.pairs_sig_naive", f"{KEY}.adj_sig_sdr"],
    }}}

    # ---- figures
    src_fig = "IPUMS USA, ACS 2024 1-year; PERWT and REPWTP1-80; SDR variance (4/80, df 79)."
    rows_tab = []
    for i in order:
        rows_tab.append({"rank": int(rank[i]), "state": names[i], "estimate": sig(th0[i]),
                         "moe90": sig(Z90 * se_sdr[i]), "se_iid": sig(se_iid[i]), "se_sdr": sig(se_sdr[i]),
                         "ratio": sig(ratio_sdr_iid[i]), "distinct": int(distinct[i]),
                         "rank_range": f"{L[i]}–{U[i]}" if L[i] != U[i] else f"{L[i]}", "n": int(n[i])})
    rank_table = {
        "type": "table",
        "title": "Uninsured rate among adults 19–64 by state, 2024, with replicate-based uncertainty",
        "subtitle": ("Rank 1 = highest rate. MOE is the ACS 90% margin of error (1.645 × SDR SE). "
                     "“Ranks” are the positions consistent with every pairwise 90% test."),
        "alt": ("Table of 51 states ranked by uninsured rate among adults 19 to 64, with 90% margins of error, "
                "naive and replicate standard errors, their ratio, the number of other states each is statistically "
                "distinguishable from, and the range of ranks consistent with the pairwise tests."),
        "columns": [
            {"key": "rank", "label": "Rank", "format": "int", "align": "right"},
            {"key": "state", "label": "State", "align": "left"},
            {"key": "estimate", "label": "Uninsured", "format": "pct1", "align": "right"},
            {"key": "moe90", "label": "90% MOE (±)", "format": "pct1", "align": "right"},
            {"key": "se_iid", "label": "SE, naive iid", "format": "pct2", "align": "right"},
            {"key": "se_sdr", "label": "SE, SDR", "format": "pct2", "align": "right"},
            {"key": "ratio", "label": "SDR ÷ iid", "format": "ratio2", "align": "right"},
            {"key": "distinct", "label": "Distinguishable from (of 50)", "format": "int", "align": "right"},
            {"key": "rank_range", "label": "Ranks", "align": "center"},
            {"key": "n", "label": "n", "format": "int", "align": "right"},
        ],
        "rows": rows_tab,
        "source": src_fig,
        "note": ("Civilian noninstitutionalized adults 19–64 (IPUMS approximation). Pairwise tests use the SDR "
                 "standard error of each difference (replicate covariance), |difference|/SE > 1.645, per comparison."),
    }
    hi_max = max(th0[i] + Z90 * se_sdr[i] for i in range(S))
    state_forest = {
        "type": "dot",
        "title": "State uninsured rates with 90% margins of error",
        "subtitle": "Adults 19–64, 2024. Bars are ±1.645 SDR standard errors, the ACS convention.",
        "alt": ("Dot plot of the 51 state uninsured rates for adults 19 to 64, sorted from highest to lowest, each with "
                "a 90% margin-of-error bar; neighboring states' bars overlap through most of the ranking, while Texas "
                "at the top and Massachusetts at the bottom stand clear."),
        "format": "pct0",
        "x_label": "Uninsured rate, adults 19–64",
        "reference": {"value": sig(US["th0"]), "label": "United States"},
        "domain": [0, math.ceil(hi_max * 20) / 20],
        "rows": [{"label": names[i], "estimate": sig(th0[i]), "ci_low": sig(th0[i] - Z90 * se_sdr[i]),
                  "ci_high": sig(th0[i] + Z90 * se_sdr[i]), "role": "design", "n": int(n[i])} for i in order],
        "source": src_fig,
    }
    rank_gap = {
        "type": "line",
        "title": "How far apart must two states be in the ranking to be distinguishable?",
        "subtitle": "Share of state pairs a given number of places apart whose difference is significant at the 90% level.",
        "alt": (f"Line chart: for state pairs 1 to {GAP_MAX} places apart in the ranking, the share whose difference is "
                "statistically distinguishable, under replicate (SDR) standard errors and under naive iid standard "
                "errors; the naive line sits above the replicate line at short distances and both reach 100% by "
                "about ten places."),
        "format": "pct0",
        "x_label": "Distance in rank between the two states",
        "y_label": "Pairs distinguishable",
        "y_domain": [0, 1],
        "series": [
            {"name": "Replicate SE of the difference (SDR)", "role": "design",
             "segments": [[{"x": x["g"], "y": sig(x["sdr"])} for x in gap if x["g"] <= GAP_MAX]]},
            {"name": "Naive iid SEs, independence assumed", "role": "naive",
             "segments": [[{"x": x["g"], "y": sig(x["naive"])} for x in gap if x["g"] <= GAP_MAX]]},
        ],
        "source": src_fig,
    }
    state_replicates = {
        "type": "replicates",
        "title": "Re-rank the states on each replicate",
        "alt": ("Interactive ranking of the 51 state uninsured rates for adults 19 to 64 in 2024, with the 80 SDR "
                "replicate estimates for each state, used to show margins of error and how often each state lands "
                "in the top ten when the ranking is recomputed on each rescaled replicate."),
        "measure_label": "Uninsured rate, civilian noninstitutionalized adults 19–64, 2024",
        "format": "pct1",
        "method": "SDR",
        "n_reps": R,
        "scale": C,
        "top_k": TOP_K,
        "units": [{"id": usps[i], "label": names[i], "estimate": sig(th0[i]),
                   "reps": [sig(v) for v in E["reps"][i]], "naive_se": sig(se_iid[i])} for i in order],
        "source": src_fig,
        "note": ("Rank 1 = highest uninsured rate. Replicate estimates recompute the state rate with each of "
                 "REPWTP1-80; Var = 0.05 x sum of squared deviations, so a draw-like view rescales each deviation "
                 "by sqrt(0.05 x 80) = 2. Replicates approximate sampling spread; they are not posterior draws."),
    }
    for name, obj in [("rank_table", rank_table), ("state_forest", state_forest),
                      ("rank_gap", rank_gap), ("state_replicates", state_replicates)]:
        dump(obj, FIG / f"{name}.json")

    # ---- manifest
    validation = []
    if r_val:
        validation.append(r_val)
    else:
        validation.append({"check": "hand-coded SDR vs R survey", "pass": None,
                           "status": "pending: run verify.R, then build.py again"})
    validation.append({
        "check": "hand-coded SDR vs svy 0.28 replication path (third implementation)",
        "state": usps[top], "n": svy_res["n"],
        "svy_replication": {"se": sig(svy_res["replication"]["se"], 10), "df": svy_res["replication"]["df"],
                            "method": svy_res["replication"]["method"]},
        "hand_se": sig(se_sdr[top], 10), "abs_diff": float(f"{svy_rep_diff:.3g}"),
        "pass": bool(svy_rep_diff < 1e-9 and svy_res["replication"]["df"] == DF)})
    validation.append({
        "check": "svy default call with replicate weights declared (CONTRACT pitfall reproduced)",
        "state": usps[top],
        "svy_default": {"se": sig(svy_res["default"]["se"], 10), "df": svy_res["default"]["df"],
                        "method": svy_res["default"]["method"]},
        "equals_weights_only_linearized_se": bool(svy_def_vs_wo < 1e-6),
        "relative_diff_vs_weights_only_formula": float(f"{svy_def_vs_wo:.3g}"),
        "default_over_replication_se": sig(svy_res["default"]["se"] / svy_res["replication"]["se"], 4),
        "df_is_n_minus_1": svy_res["default"]["df"] == svy_res["n"] - 1,
        "note": "The default ignores the 80 replicates; the SE is a with-replacement linearization treating each person as a PSU."})
    validation.append({
        "check": "Census PUMS verification estimates, 2024 (external benchmark)",
        "source": PUMS_URL,
        "geographies": ["US", "TX", "WY", "VT", "DC", "CA", "MA"],
        "rows": len(pums), "rows_with_nonzero_published_se": len(pums_nonzero),
        "estimates_exact": pums_est_ok, "se_within_integer_rounding": pums_se_ok,
        "max_se_abs_diff": max(r["se_abs_diff"] for r in pums),
        "discrepancies": pums_bad,
        "pass": bool(pums_est_ok == len(pums) and pums_se_ok == len(pums)),
        "note": ("IPUMS PERWT = PWGTP and REPWTP1-80 = PWGTP1-80 in the 2024 PUMS; RELSHIPP 37/38 mapped to IPUMS GQ 3/4. "
                 "Benchmark values transcribed from the published CSV (TX, WY, US read twice). PUMS SEs are for the PUMS "
                 "subsample, not the full-sample ACS MOEs on data.census.gov.")})
    validation.append({"check": "1:1 replicate join and universe", **read_checks,
                       "universe_n": int(n.sum()), "min_state_n": int(n.min()),
                       "max_cv": sig(float(cv.max()), 4), "suppressed": 0,
                       "pass": True})
    manifest = {
        "key": KEY, "slug": SLUG, "status": "draft", "code": "build.py",
        "inputs": [
            {"path": DATA_REL, "rows": read_checks["persons_2024"],
             "note": "SAMPLE 202401 (ACS 2024 1-year); SERIAL, PERNUM, STATEFIP, SEX, AGE, GQ, EMPSTATD, PERWT, uninsured"},
            {"path": REPWT_REL, "rows": read_checks["repwt_rows_2024"],
             "note": "REPWTP1-REPWTP80 for SAMPLE 202401, joined 1:1 on SAMPLE+SERIAL+PERNUM"},
            {"path": PUMS_URL, "rows": len(pums), "note": "published PUMS estimates and SEs used as an external benchmark"},
        ],
        "method": {"estimator": "weighted share (Hajek)", "variance": "SDR, Var = (4/80) sum_r (theta_r - theta)^2",
                   "df": DF, "moe": "1.645 x SE (ACS 90%)", "ci_facts": f"95%, t({DF}) = {T95:.4f}",
                   "tests": "pairwise, 90% per comparison, SE of the difference from the replicates",
                   "universe": UNIVERSE_TXT,
                   "pair_counts": counts, "pairs_verdict_changed_by_independence_formula": indep_flips,
                   "adjacent_pairs_with_overlapping_90pct_intervals": adj_overlap,
                   "se_diff_rep_over_indep": {"min": sig(float(cov_ratio.min()), 4), "median": sig(float(np.median(cov_ratio)), 4),
                                               "max": sig(float(cov_ratio.max()), 4)},
                   "sdr_over_weights_only": {"min": sig(float(ratio_sdr_wo.min()), 4), "median": sig(float(np.median(ratio_sdr_wo)), 4),
                                             "max": sig(float(ratio_sdr_wo.max()), 4)},
                   "kish_deff_weighting": {"min": sig(float(E["kish"].min()), 4), "median": sig(float(np.median(E["kish"])), 4),
                                           "max": sig(float(E["kish"].max()), 4)},
                   "national": {"estimate": sig(US["th0"]), "se_sdr": sig(US["se_sdr"]), "se_iid": sig(US["se_iid"]),
                                "se_weights_only": sig(US["se_wo"]), "n": US["n"]}},
        "validation": validation,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    dump(facts, ART / "facts.json")
    dump(ledger, ART / "ledger.json")
    dump(manifest, ART / "manifest.json")

    # ================================================================ console summary
    print(f"\nUS: {pct(US['th0'], 2)} se_sdr {pp(US['se_sdr'], 3)} se_iid {pp(US['se_iid'], 3)} "
          f"se_wo {pp(US['se_wo'], 3)} n {US['n']:,} ratio {US['se_sdr'] / US['se_iid']:.3f}")
    print(f"pairs: {counts}  flips(indep) {indep_flips}  z_bonf {z_bonf:.3f}  T90 {T90:.4f}")
    print(f"adjacent sig: sdr {adj_sdr} naive {adj_naive}; overlapping 90% intervals {adj_overlap}/50; "
          f"gap_all sdr {gap_all_sdr} naive {gap_all_naive}")
    print(f"median ratio sdr/iid {np.median(ratio_sdr_iid):.3f}; sdr/wo {ratio_sdr_wo.min():.3f}-{ratio_sdr_wo.max():.3f} "
          f"({names[wmin]}, {names[wmax]}); se_D rep/indep median {np.median(cov_ratio):.4f}")
    print(f"top10: sure {len(sure_top)} maybe {len(maybe_top)}; freq r9 {top_freq[r9]:.4f} r10 {top_freq[r10]:.4f} r11 {top_freq[r11]:.4f}")
    print(f"state-vs-US ({usps[big]}): se rep {pp(se_state_us_rep, 3)} vs indep {pp(se_state_us_ind, 3)}")
    print(f"svy [{usps[top]}] default se {svy_res['default']['se']:.8f} df {svy_res['default']['df']}; "
          f"replication se {svy_res['replication']['se']:.8f} df {svy_res['replication']['df']}; |diff| {svy_rep_diff:.2e}")
    print(f"PUMS: {len(pums)} rows; est exact {pums_est_ok}; se ok {pums_se_ok}; max se diff {max(r['se_abs_diff'] for r in pums)}")
    print("R check:", r_val if r_val else "pending")
    print(f"facts {len(F)}; done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
