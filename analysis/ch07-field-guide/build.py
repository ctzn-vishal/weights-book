"""Chapter 7 build: Field Guide - Six Surveys, Declared.

Generates the six release guides (table figures) from the design manifests plus
producer documentation, computes design facts from the data (reading only the
columns needed), executes the Python declaration snippets against the book's
store, and runs verify.R (R `survey` sentinel checks, which source the R snippets).

    python build.py          full build
    python build.py --no-r   skip verify.R (its checks are recorded as skipped)

Outputs: artifacts/{manifest,facts,ledger}.json, artifacts/figures/*.json and
snippets/*.{py,R,do}. Deterministic except manifest.generated_at. The ACS 2024
record count is cached in cache/ keyed on the parquet file's size and mtime.

Provenance labels used in the guides:
  design.json            a machine-readable field of the dataset's design manifest
  design.json notes      the manifest's free-text notes
  producer: ...          producer documentation read on VERIFIED (see DOCS)
  computed from data     counted by this script from the store
  verified in this build a behavior this script checked by running code
  book guidance          an editorial recommendation, not a producer rule
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path

os.environ.setdefault("NO_COLOR", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import numpy as np
import polars as pl
import svy

HERE = Path(__file__).resolve().parent
ART, SNIP, CACHE = HERE / "artifacts", HERE / "snippets", HERE / "cache"
FIG = ART / "figures"
KEY, SLUG = "ch7", "ch07-field-guide"
VERIFIED = "2026-09-10"  # date the producer documents in DOCS were last re-read
BOX = Path(r"C:\Users\Vishal Singh\Box")
AN = BOX / "ipums" / "analysis"
RSCRIPT = Path(r"C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe")
NO_R = "--no-r" in sys.argv

P = {
    "acs_meta": AN / "usa" / "metadata" / "acs.design.json",
    "acs_repwt_meta": AN / "usa" / "metadata" / "acs_repwt.design.json",
    "asec_meta": AN / "cps" / "metadata" / "cps_asec.design.json",
    "asec_repwt_meta": AN / "cps" / "metadata" / "cps_asec_repwt.design.json",
    "nhis_meta": AN / "nhis" / "metadata" / "nhis_core.design.json",
    "atus_meta": AN / "atus" / "metadata" / "atus_respondent.design.json",
    "nhanes_meta": BOX / "NHANES" / "data" / "processed" / "design.json",
    "acs_data": AN / "usa" / "acs" / "part_2020_2024.parquet",
    "asec_data": AN / "cps" / "cps_asec" / "part_2020_2025.parquet",
    "nhis_data": AN / "nhis" / "nhis_core" / "part_2015_2024.parquet",
    "atus_data": AN / "atus" / "atus_respondent.parquet",
    "nhanes_data": BOX / "NHANES" / "data" / "processed" / "nhanes_analysis.parquet",
    "brfss_data": BOX / "BRFSS" / "BRFSS_2026" / "cleaned" / "brfss_multi_rec.parquet",
}
DOCS = {
    "IPUMS USA repwt FAQ": "https://usa.ipums.org/usa/repwt.shtml",
    "IPUMS CPS repwt FAQ": "https://cps.ipums.org/cps/repwt.shtml",
    "Census ASEC documentation": "https://www.census.gov/programs-surveys/sahie/technical-documentation/model-input-data/cpsasec.html",
    "BLS CPS sample redesign": "https://www.bls.gov/cps/methods/sample_redesign_2025.htm",
    "NCHS 2024 NHIS survey description": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Dataset_Documentation/NHIS/2024/srvydesc-508.pdf",
    "IPUMS NHIS variance note": "https://nhis.ipums.org/nhis/userNotes_variance.shtml",
    "BLS ATUS user's guide (June 2026)": "https://www.bls.gov/tus/atususersguide.pdf",
    "IPUMS ATUS RWT06": "https://www.atusdata.org/atus-action/variables/RWT06",
    "NCHS DEMO_L documentation": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles/DEMO_L.htm",
    "NCHS NHANES 2021-2023 overview brief": "https://wwwn.cdc.gov/nchs/nhanes/continuousnhanes/overviewbrief.aspx?Cycle=2021-2023",
    "NHANES tutorial: variance estimation": "https://wwwn.cdc.gov/nchs/nhanes/tutorials/varianceestimation.aspx",
    "CDC BRFSS 2024 overview": "https://www.cdc.gov/brfss/annual_data/2024/pdf/Overview_2024-508.pdf",
    "CDC BRFSS 2024 weighting description": "https://www.cdc.gov/brfss/annual_data/2024/pdf/2024-Weightning-Description-508.pdf",
    "CDC BRFSS 2024 complex sampling weights": "https://www.cdc.gov/brfss/annual_data/2024/pdf/Complex-Sampling-Weights-and-Preparing-Module-Data-for-Analysis-2024-508.pdf",
}
validation: list[dict] = []


# ------------------------------------------------------------------ helpers
def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, sort_keys=True, indent=2, ensure_ascii=False)
        f.write("\n")


def fact(value, display, estimand, source, **kw) -> dict:
    out = {"value": value, "display": display, "unit": None, "se": None, "ci_low": None,
           "ci_high": None, "ci_display": None, "df": None, "n": None, "weight": None,
           "variance": "none", "estimand": estimand, "source": source, "benchmark": None, "note": ""}
    out.update(kw)
    return out


def pct(x: float, d: int = 1) -> str:
    return f"{100 * x:.{d}f}%"


def r6(x) -> float:
    return round(float(x), 6)


def check(name: str, ok: bool, **detail) -> None:
    validation.append({"check": name, "pass": bool(ok),
                       **{k: (round(v, 10) if isinstance(v, float) else v) for k, v in detail.items()}})
    print(f"  [{'ok' if ok else 'FAIL'}] {name}")


def row(item: str, value: str, source: str) -> dict:
    return {"item": item, "value": value, "source": source}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


GUIDE_COLUMNS = [
    {"key": "item", "label": "Item", "align": "left"},
    {"key": "value", "label": "Declaration", "align": "left"},
    {"key": "source", "label": "Provenance", "align": "left"},
]

# ------------------------------------------------------------------ 1. design manifests
print("1. manifests")
M = {k: load(P[k]) for k in ("acs_meta", "acs_repwt_meta", "asec_meta", "asec_repwt_meta",
                             "nhis_meta", "atus_meta", "nhanes_meta")}
check("companion manifests point to their parents",
      M["acs_repwt_meta"].get("see_parent") == "acs" and M["asec_repwt_meta"].get("see_parent") == "cps_asec")


def rep_info(meta: dict) -> dict:
    rw = meta["replicate_weights"]
    n = rw["person"]["n_reps"]
    num, den = map(int, re.search(r"\((\d+)/(\d+)\)", rw["variance_formula"]).groups())
    assert rw["household"]["n_reps"] == n and den == n and rw["df"] == n - 1
    return {"n_reps": n, "df": rw["df"], "scale_txt": f"{num}/{den}", "scale": num / den,
            "p_prefix": rw["person"]["prefix"], "h_prefix": rw["household"]["prefix"],
            "method": rw["method"], "join": rw["join_keys"], "companion": rw["companion_path"],
            "neg": rw.get("negative_values"), "verified": rw.get("verified", {}),
            "coverage": rw.get("coverage"), "df_note": rw.get("df_note")}


ACS_R, ASEC_R = rep_info(M["acs_meta"]), rep_info(M["asec_meta"])

# ------------------------------------------------------------------ 2. design facts from the data
print("2. data")
inputs: list[dict] = []

nh = pl.read_parquet(P["nhis_data"], columns=["YEAR", "STRATA", "PSU", "SAMPWEIGHT", "PERWEIGHT",
                                              "ASTATFLG", "AGE", "current_smoker"])
n24, n23 = nh.filter(pl.col("YEAR") == 2024), nh.filter(pl.col("YEAR") == 2023)
pairs24 = set(n24.select("STRATA", "PSU").unique().rows())
pairs23 = set(n23.select("STRATA", "PSU").unique().rows())
nhis = {
    "rows": n24.height,
    "adults": n24.filter(pl.col("ASTATFLG") == 1).height,
    "children": n24.filter(pl.col("ASTATFLG").is_null()).height,
    "strata": n24["STRATA"].n_unique(),
    "psus": len(pairs24),
    "psu_codes": n24["PSU"].n_unique(),
    "min_psus": int(n24.group_by("STRATA").agg(pl.col("PSU").n_unique().alias("k"))["k"].min()),
    "shared": len(pairs23 & pairs24),
    "perweight_nonnull": int(n24["PERWEIGHT"].is_not_null().sum()),
}
nhis["df"] = nhis["psus"] - nhis["strata"]
ad_age = n24.filter(pl.col("ASTATFLG") == 1)["AGE"]
ch_age = n24.filter(pl.col("ASTATFLG").is_null())["AGE"]
check("NHIS 2024: ASTATFLG = 1 rows are adults and the remaining rows are children",
      bool((ad_age.drop_nulls() >= 18).all()) and bool((ch_age.drop_nulls() < 18).all()),
      adults=nhis["adults"], children=nhis["children"])
check("NHIS 2024: every record carries a positive SAMPWEIGHT and PERWEIGHT is not released",
      bool((n24["SAMPWEIGHT"] > 0).all()) and nhis["perweight_nonnull"] == 0)
inputs.append({"path": "ipums/analysis/nhis/nhis_core/part_2015_2024.parquet", "rows": nh.height,
               "note": "YEAR, STRATA, PSU, SAMPWEIGHT, PERWEIGHT, ASTATFLG, AGE, current_smoker; 2023 and 2024 used"})

na = pl.read_parquet(P["nhanes_data"], columns=["CYCLE_YEAR", "SDMVSTRA", "SDMVPSU", "WTMEC2YR",
                                                "WTINT2YR", "RIDAGEYR", "htn_measured"])
l21 = na.filter(pl.col("CYCLE_YEAR") == 2021)
nhanes = {
    "rows": l21.height,
    "interviewed": int((l21["WTINT2YR"] > 0).sum()),
    "examined": int((l21["WTMEC2YR"] > 0).sum()),
    "strata": l21["SDMVSTRA"].n_unique(),
    "psus": l21.select("SDMVSTRA", "SDMVPSU").unique().height,
    "smin": int(l21["SDMVSTRA"].min()), "smax": int(l21["SDMVSTRA"].max()),
}
nhanes["df"] = nhanes["psus"] - nhanes["strata"]
check("NHANES 2021-2023 counts equal NCHS's DEMO_L documentation (11,933 interviewed; 8,860 examined; "
      "15 pseudo-strata, 30 pseudo-PSUs)",
      (nhanes["interviewed"], nhanes["examined"], nhanes["strata"], nhanes["psus"]) == (11933, 8860, 15, 30),
      **{k: nhanes[k] for k in ("interviewed", "examined", "strata", "psus")})
inputs.append({"path": "NHANES/data/processed/nhanes_analysis.parquet", "rows": na.height,
               "note": "design and weight columns plus RIDAGEYR, htn_measured; CYCLE_YEAR = 2021 used"})

bf = pl.read_parquet(P["brfss_data"], columns=["iyear", "xststr", "xpsu", "xllcpwt", "xstate", "State", "Health"])
b24 = bf.filter(pl.col("iyear") == 2024)
per_stratum = b24.group_by("xststr").agg(pl.col("xpsu").n_unique().alias("k"))
brfss = {
    "n": b24.height,
    "strata": b24["xststr"].n_unique(),
    "psus": b24.select("xststr", "xpsu").unique().height,
    "psu_codes": b24["xpsu"].n_unique(),
    "singletons": int((per_stratum["k"] == 1).sum()),
    "jurisdictions": b24["xstate"].n_unique(),
    "tn_rows": int((b24["State"] == "Tennessee").sum()),
    "states": sorted(b24["State"].drop_nulls().unique().to_list()),
}
brfss["df"] = brfss["psus"] - brfss["strata"]
check("BRFSS 2024: Tennessee absent, every respondent its own PSU",
      brfss["tn_rows"] == 0 and brfss["psus"] == brfss["n"], jurisdictions=brfss["jurisdictions"])
inputs.append({"path": "BRFSS/BRFSS_2026/cleaned/brfss_multi_rec.parquet", "rows": bf.height,
               "note": "iyear, xststr, xpsu, xllcpwt, xstate, State, Health; iyear = 2024 used"})
del bf

at = pl.read_parquet(P["atus_data"], columns=["YEAR", "WT06", "STRATA", "BLS_WORK"])
a24 = at.filter(pl.col("YEAR") == 2024)
atus = {"n": a24.height, "wt_pos": int((a24["WT06"] > 0).sum()),
        "strata_nonnull": int(a24["STRATA"].is_not_null().sum())}
check("ATUS 2024: positive WT06 on every respondent, no design variables in the extract",
      atus["wt_pos"] == atus["n"] and atus["strata_nonnull"] == 0, n=atus["n"])
inputs.append({"path": "ipums/analysis/atus/atus_respondent.parquet", "rows": at.height,
               "note": "YEAR, WT06, STRATA, BLS_WORK; YEAR = 2024 used"})

am = pl.read_parquet(P["asec_data"], columns=["YEAR", "ASECWT", "ASECFLAG", "uninsured_ly"])
a25 = am.filter(pl.col("YEAR") == 2025)
asec = {"rows": a25.height, "wt_pos": int((a25["ASECWT"] > 0).sum()),
        "wt_null": int(a25["ASECWT"].is_null().sum()),
        "flags": [list(r) for r in a25.group_by("ASECFLAG").len().sort("ASECFLAG").rows()]}
check("CPS ASEC 2025: record and weight counts", asec["wt_null"] == 0,
      rows=asec["rows"], positive_weight=asec["wt_pos"], asecflag_counts=str(asec["flags"]))
inputs.append({"path": "ipums/analysis/cps/cps_asec/part_2020_2025.parquet", "rows": am.height,
               "note": "YEAR, ASECWT, ASECFLAG, uninsured_ly; YEAR = 2025 used"})


def acs_counts() -> dict:
    path = P["acs_data"]
    st = path.stat()
    sig = f"{st.st_size}:{st.st_mtime_ns}"
    cf = CACHE / "acs2024_counts.json"
    if cf.exists():
        c = json.loads(cf.read_text(encoding="utf-8"))
        if c.get("sig") == sig:
            return c
    df = pl.scan_parquet(path).filter(pl.col("YEAR") == 2024).select(["SAMPLE", "PERWT"]).collect()
    c = {"sig": sig, "n": df.height, "samples": sorted(int(s) for s in df["SAMPLE"].unique().to_list()),
         "perwt_sum_millions": round(float(df["PERWT"].sum()) / 1e6, 1)}
    CACHE.mkdir(exist_ok=True)
    cf.write_text(json.dumps(c, indent=2), encoding="utf-8")
    return c


acs = acs_counts()
assert len(acs["samples"]) == 1, acs["samples"]
ACS_SAMPLE = acs["samples"][0]
check("ACS 2024: one IPUMS sample code; sum of PERWT matches the store benchmark (340.1 million)",
      acs["perwt_sum_millions"] == 340.1, sample=ACS_SAMPLE, perwt_sum_millions=acs["perwt_sum_millions"])
inputs.append({"path": "ipums/analysis/usa/acs/part_2020_2024.parquet", "rows": acs["n"],
               "note": "YEAR, SAMPLE, PERWT for 2024 (rows = 2024 person records; cached count)"})

# ------------------------------------------------------------------ 3. declaration snippets
print("3. snippets")
HEADER_PY = "# Paths point at the book's store; adapt them to your own extract.\n"
SNIPPETS: dict[tuple[str, str], str] = {}

SNIPPETS[("acs", "py")] = HEADER_PY + """import polars as pl
import svy

keys = ["SAMPLE", "SERIAL", "PERNUM"]
acs2024 = pl.col("SAMPLE") == @SAMPLE@  # IPUMS sample code of the 2024 1-year file
p = (
    pl.scan_parquet("ipums/analysis/usa/acs/part_2020_2024.parquet")
    .filter(acs2024)
    .select(keys + ["PERWT", "uninsured"])
)
reps = [f"REPWTP{i}" for i in range(1, 81)]  # by name, never a REPWTP* wildcard
r = (
    pl.scan_parquet("ipums/analysis/usa/acs_repwt/part_2020_2024.parquet")
    .filter(acs2024)
    .select(keys + reps)
)
d = p.join(r, on=keys, how="inner").collect()

rep = svy.SdrWgts(prefix="REPWTP", n_reps=80)
s = svy.Sample(d, design=svy.Design(wgt="PERWT", rep_wgts=rep))
est = s.estimation.mean("uninsured", method="replication", variance_center="estimate", drop_nulls=True)
assert est.to_dicts()[0]["df"] == 79  # the default call would silently report n - 1
""".replace("@SAMPLE@", str(ACS_SAMPLE))

SNIPPETS[("acs", "R")] = """# Paths point at the book's store; adapt them to your own extract.
library(arrow)
library(dplyr)
library(survey)

keys <- c("SAMPLE", "SERIAL", "PERNUM")
p <- open_dataset("ipums/analysis/usa/acs/part_2020_2024.parquet") |>
  filter(SAMPLE == @SAMPLE@) |>
  select(all_of(c(keys, "PERWT", "uninsured"))) |>
  collect()
r <- open_dataset("ipums/analysis/usa/acs_repwt/part_2020_2024.parquet") |>
  filter(SAMPLE == @SAMPLE@) |>
  select(all_of(c(keys, paste0("REPWTP", 1:80)))) |>
  collect()
d <- inner_join(p, r, by = keys)

des <- svrepdesign(data = d, weights = ~PERWT, repweights = "^REPWTP[0-9]+$",
                   type = "successive-difference", mse = TRUE)  # scale 4/80, df 79
svymean(~uninsured, des, na.rm = TRUE)
""".replace("@SAMPLE@", str(ACS_SAMPLE))

SNIPPETS[("acs", "do")] = """* IPUMS USA's documented declaration (Stata 12+); list replicate weights by range.
svyset [pweight=perwt], vce(sdr) sdrweight(repwtp1-repwtp80) dof(79) mse
svy: mean uninsured
"""

SNIPPETS[("asec", "py")] = HEADER_PY + """import polars as pl
import svy

keys = ["YEAR", "SERIAL", "PERNUM"]
p = (
    pl.scan_parquet("ipums/analysis/cps/cps_asec/part_2020_2025.parquet")
    .filter(pl.col("YEAR") == 2025)
    .select(keys + ["ASECWT", "uninsured_ly"])
)
reps = [f"REPWTP{i}" for i in range(1, 161)]  # by name, never a REPWTP* wildcard
r = (
    pl.scan_parquet("ipums/analysis/cps/cps_asec_repwt/part_2020_2025.parquet")
    .filter(pl.col("YEAR") == 2025)
    .select(keys + reps)
)
d = p.join(r, on=keys, how="inner").collect()

rep = svy.SdrWgts(prefix="REPWTP", n_reps=160)
s = svy.Sample(d, design=svy.Design(wgt="ASECWT", rep_wgts=rep))
est = s.estimation.mean("uninsured_ly", method="replication", variance_center="estimate", drop_nulls=True)
assert est.to_dicts()[0]["df"] == 159  # the default call would silently report n - 1
"""

SNIPPETS[("asec", "R")] = """# Paths point at the book's store; adapt them to your own extract.
library(arrow)
library(dplyr)
library(survey)

keys <- c("YEAR", "SERIAL", "PERNUM")
p <- open_dataset("ipums/analysis/cps/cps_asec/part_2020_2025.parquet") |>
  filter(YEAR == 2025) |>
  select(all_of(c(keys, "ASECWT", "uninsured_ly"))) |>
  collect()
r <- open_dataset("ipums/analysis/cps/cps_asec_repwt/part_2020_2025.parquet") |>
  filter(YEAR == 2025) |>
  select(all_of(c(keys, paste0("REPWTP", 1:160)))) |>
  collect()
d <- inner_join(p, r, by = keys)

des <- svrepdesign(data = d, weights = ~ASECWT, repweights = "^REPWTP[0-9]+$",
                   type = "successive-difference", mse = TRUE)  # scale 4/160, df 159
svymean(~uninsured_ly, des, na.rm = TRUE)
"""

SNIPPETS[("asec", "do")] = """* Some CPS replicate weights are negative, so IPUMS declares iweights.
svyset [iweight=asecwt], sdrweight(repwtp1-repwtp160) vce(sdr) dof(159) mse
svy: mean uninsured_ly
"""

SNIPPETS[("nhis", "py")] = HEADER_PY + """import polars as pl
import svy

d = pl.read_parquet(
    "ipums/analysis/nhis/nhis_core/part_2015_2024.parquet",
    columns=["YEAR", "STRATA", "PSU", "SAMPWEIGHT", "ASTATFLG", "current_smoker"],
).filter(pl.col("YEAR") == 2024)  # one annual file is one design
d = d.with_columns(pl.col("ASTATFLG").cast(pl.Int64))  # svy 0.28: where= rejects 8- and 16-bit integers

# svy nests PSU codes within strata; hand-rolled code must key on (STRATA, PSU).
s = svy.Sample(d, design=svy.Design(stratum="STRATA", psu="PSU", wgt="SAMPWEIGHT"))

# Sample adults are a domain: declare on the whole file, then estimate with where=.
est = s.estimation.mean("current_smoker", where=svy.col("ASTATFLG") == 1, drop_nulls=True)
print(est.to_dicts()[0])  # df = PSUs - strata
"""

SNIPPETS[("nhis", "R")] = """# Paths point at the book's store; adapt them to your own extract.
library(arrow)
library(survey)

d <- read_parquet("ipums/analysis/nhis/nhis_core/part_2015_2024.parquet",
                  col_select = c("YEAR", "STRATA", "PSU", "SAMPWEIGHT", "ASTATFLG", "current_smoker"))
d <- d[d$YEAR == 2024, ]

# PSU codes repeat across strata: nest = TRUE is required (svydesign stops without it).
des <- svydesign(ids = ~PSU, strata = ~STRATA, weights = ~SAMPWEIGHT, nest = TRUE, data = d)
svymean(~current_smoker, subset(des, ASTATFLG == 1), na.rm = TRUE)
"""

SNIPPETS[("nhis", "do")] = """* NCHS files name these pstrat, ppsu, and wtfa_a; the IPUMS names are shown.
svyset psu [pweight=sampweight], strata(strata) vce(linearized) singleunit(centered)
svy, subpop(if astatflg==1): mean current_smoker
"""

SNIPPETS[("atus", "py")] = HEADER_PY + """import polars as pl
import svy

d = pl.read_parquet(
    "ipums/analysis/atus/atus_respondent.parquet",
    columns=["YEAR", "WT06", "BLS_WORK"],
).filter(pl.col("YEAR") == 2024)

# No design variables in this extract: the SE treats diary days as a weighted
# with-replacement sample and understates the design-based SE.
s = svy.Sample(d, design=svy.Design(wgt="WT06"))
est = s.estimation.mean("BLS_WORK")

# With IPUMS RWT06_1-RWT06_160 added to the extract:
# rep = svy.SdrWgts(prefix="RWT06_", n_reps=160)
# s = svy.Sample(d, design=svy.Design(wgt="WT06", rep_wgts=rep))
# est = s.estimation.mean("BLS_WORK", method="replication", variance_center="estimate")
"""

SNIPPETS[("atus", "R")] = """# Paths point at the book's store; adapt them to your own extract.
library(arrow)
library(survey)

d <- read_parquet("ipums/analysis/atus/atus_respondent.parquet",
                  col_select = c("YEAR", "WT06", "BLS_WORK"))
d <- d[d$YEAR == 2024, ]

des <- svydesign(ids = ~1, weights = ~WT06, data = d)  # weights only: SE understated
# With RWT06_1-RWT06_160 in the extract:
# des <- svrepdesign(data = d, weights = ~WT06, repweights = "^RWT06_[0-9]+$",
#                    type = "successive-difference", mse = TRUE)
svymean(~BLS_WORK, des)
"""

SNIPPETS[("atus", "do")] = """* Weights only, as in the book's store: the SE understates design variance.
svyset [pweight=wt06]
* With rwt06_1-rwt06_160 in the extract:
* svyset [pweight=wt06], sdrweight(rwt06_1-rwt06_160) vce(sdr) mse
svy: mean bls_work
"""

SNIPPETS[("nhanes", "py")] = HEADER_PY + """import polars as pl
import svy

d = pl.read_parquet(
    "NHANES/data/processed/nhanes_analysis.parquet",
    columns=["CYCLE_YEAR", "SDMVSTRA", "SDMVPSU", "WTMEC2YR", "RIDAGEYR", "htn_measured"],
).filter(pl.col("CYCLE_YEAR") == 2021)  # August 2021-August 2023 only

s = svy.Sample(d, design=svy.Design(stratum="SDMVSTRA", psu="SDMVPSU", wgt="WTMEC2YR"))

# Examined adults are a domain; interviewed-only participants carry WTMEC2YR = 0.
adults = (svy.col("RIDAGEYR") >= 18) & (svy.col("WTMEC2YR") > 0)
est = s.estimation.mean("htn_measured", where=adults, drop_nulls=True)
print(est.to_dicts()[0])  # df = PSUs - strata
"""

SNIPPETS[("nhanes", "R")] = """# Paths point at the book's store; adapt them to your own extract.
library(arrow)
library(survey)

d <- read_parquet("NHANES/data/processed/nhanes_analysis.parquet",
                  col_select = c("CYCLE_YEAR", "SDMVSTRA", "SDMVPSU", "WTMEC2YR", "RIDAGEYR", "htn_measured"))
d <- d[d$CYCLE_YEAR == 2021, ]

des <- svydesign(ids = ~SDMVPSU, strata = ~SDMVSTRA, weights = ~WTMEC2YR, nest = TRUE, data = d)
svymean(~htn_measured, subset(des, RIDAGEYR >= 18 & WTMEC2YR > 0), na.rm = TRUE)
"""

SNIPPETS[("nhanes", "do")] = """svyset sdmvpsu [pweight=wtmec2yr], strata(sdmvstra) vce(linearized)
svy, subpop(if ridageyr>=18 & wtmec2yr>0): mean htn_measured
"""

SNIPPETS[("brfss", "py")] = HEADER_PY + """import polars as pl
import svy

d = (
    pl.read_parquet(
        "BRFSS/BRFSS_2026/cleaned/brfss_multi_rec.parquet",
        columns=["iyear", "xststr", "xpsu", "xllcpwt", "Health"],
    )
    .filter(pl.col("iyear") == 2024)
    .with_columns((pl.col("Health") == "Poor").cast(pl.Float64).alias("fairpoor"))
)

# CDC names: _STSTR, _PSU, _LLCPWT. Every 2024 respondent is its own PSU.
s = svy.Sample(d, design=svy.Design(stratum="xststr", psu="xpsu", wgt="xllcpwt"))
s = s.singleton.handle("center")  # single-respondent strata exist even in the full file
est = s.estimation.mean("fairpoor", drop_nulls=True)
print(est.to_dicts()[0])
"""

SNIPPETS[("brfss", "R")] = """# Paths point at the book's store; adapt them to your own extract.
library(arrow)
library(survey)

d <- read_parquet("BRFSS/BRFSS_2026/cleaned/brfss_multi_rec.parquet",
                  col_select = c("iyear", "xststr", "xpsu", "xllcpwt", "Health"))
d <- d[d$iyear == 2024, ]
d$fairpoor <- as.numeric(d$Health == "Poor")

options(survey.lonely.psu = "adjust")  # CDC's own R example sets this
des <- svydesign(ids = ~xpsu, strata = ~xststr, weights = ~xllcpwt, nest = TRUE, data = d)
svymean(~fairpoor, des, na.rm = TRUE)
"""

SNIPPETS[("brfss", "do")] = """* CDC names after import sasxport5; the book's store calls them xststr, xpsu, xllcpwt.
svyset _psu [pweight=_llcpwt], strata(_ststr) vce(linearized) singleunit(centered)
svy: mean fairpoor
"""

SNIP.mkdir(parents=True, exist_ok=True)
for (survey_key, ext), code in SNIPPETS.items():
    with open(SNIP / f"{survey_key}.{ext}", "w", encoding="utf-8", newline="\n") as f:
        f.write(code)


def exec_snippet(survey_key: str) -> dict:
    """Run a Python snippet verbatim from the Box root; return its namespace."""
    ns: dict = {}
    cwd = os.getcwd()
    os.chdir(BOX)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(SNIPPETS[(survey_key, "py")], f"<snippet {survey_key}.py>", "exec"), ns)
    except Exception:
        traceback.print_exc()
        raise
    finally:
        os.chdir(cwd)
    return ns


PY = {}
for sk in ("nhis", "nhanes", "brfss", "atus", "asec"):
    ns = exec_snippet(sk)
    e = ns["est"]
    PY[sk] = {"est": e.to_dicts()[0], "n_psus": getattr(e, "n_psus", None), "ns": ns}
    print(f"  {sk}: {PY[sk]['est']}")
check("Python snippets ran verbatim against the store (NHIS, NHANES, BRFSS, ATUS, CPS ASEC)", True,
      not_executed="ACS (3.2 GB replicate part): API checked on a synthetic frame instead")

# ------------------------------------------------------------------ 4. svy replicate behavior
print("4. svy replicate checks")
rng = np.random.default_rng(20260910)
SYN = {}
for R, wname, prefix in ((80, "PERWT", "REPWTP"), (160, "ASECWT", "REPWTP"), (160, "WT06", "RWT06_")):
    n = 600
    yv = rng.binomial(1, 0.3, n).astype(float)
    wv = rng.uniform(50, 150, n)
    cols = {"y": yv, wname: wv}
    for r in range(1, R + 1):
        cols[f"{prefix}{r}"] = wv * rng.choice([0.3, 1.7, 1.0], n)
    frame = pl.DataFrame(cols)
    th = (wv * yv).sum() / wv.sum()
    thr = np.array([(cols[f"{prefix}{r}"] * yv).sum() / cols[f"{prefix}{r}"].sum() for r in range(1, R + 1)])
    hand = float(np.sqrt(4 / R * ((thr - th) ** 2).sum()))
    s = svy.Sample(frame, design=svy.Design(wgt=wname, rep_wgts=svy.SdrWgts(prefix=prefix, n_reps=R)))
    e0 = s.estimation.mean("y").to_dicts()[0]
    e1 = s.estimation.mean("y", method="replication").to_dicts()[0]
    e2 = s.estimation.mean("y", method="replication", variance_center="estimate").to_dicts()[0]
    SYN[(R, prefix)] = (e0, e1, e2, hand)
    check(f"svy SdrWgts(prefix={prefix!r}, n_reps={R}): default call ignores replicates (df = n - 1)",
          e0["df"] == n - 1, default_df=int(e0["df"]), default_se=float(e0["se"]))
    check(f"svy SdrWgts(prefix={prefix!r}, n_reps={R}): method='replication', variance_center='estimate' "
          f"equals (4/{R}) x sum of squared deviations from the full-sample estimate, df = {R - 1}",
          abs(e2["se"] - hand) / hand < 1e-9 and e2["df"] == R - 1,
          se=float(e2["se"]), hand=hand, rep_mean_centered_se=float(e1["se"]))
# scale= and df= on SdrWgts (CONTRACT section 6 says they are ignored; check on the replication path)
frame80 = pl.DataFrame({"y": rng.binomial(1, 0.3, 600).astype(float), "w": rng.uniform(50, 150, 600)})
frame80 = frame80.with_columns([(pl.col("w") * pl.Series(rng.choice([0.3, 1.7, 1.0], 600))).alias(f"rw{r}")
                                for r in range(1, 81)])
base = svy.Sample(frame80, design=svy.Design(wgt="w", rep_wgts=svy.SdrWgts(prefix="rw", n_reps=80)))
alt = svy.Sample(frame80, design=svy.Design(wgt="w", rep_wgts=svy.SdrWgts(prefix="rw", n_reps=80, scale=0.5, df=10)))
eb = base.estimation.mean("y", method="replication", variance_center="estimate").to_dicts()[0]
ea = alt.estimation.mean("y", method="replication", variance_center="estimate").to_dicts()[0]
ea0 = alt.estimation.mean("y").to_dicts()[0]
honored = abs(ea["se"] / eb["se"] - np.sqrt(0.5 / 0.05)) < 1e-9 and ea["df"] == 10
check("svy SdrWgts scale= and df= are honored on the replication path (contrary to CONTRACT section 6); "
      "the default call ignores the whole replicate specification",
      honored and ea0["df"] == 599, se_ratio=float(ea["se"] / eb["se"]), df=int(ea["df"]), default_df=int(ea0["df"]))

# ------------------------------------------------------------------ 5. real-data traps
print("5. real-data traps")
# CPS ASEC 2025: the default call on the real replicate design
d_asec = PY["asec"]["ns"]["d"]
s_asec = svy.Sample(d_asec, design=svy.Design(wgt="ASECWT", rep_wgts=svy.SdrWgts(prefix="REPWTP", n_reps=160)))
asec_def = s_asec.estimation.mean("uninsured_ly", drop_nulls=True).to_dicts()[0]
asec_rm = s_asec.estimation.mean("uninsured_ly", method="replication", drop_nulls=True).to_dicts()[0]
asec_rep = PY["asec"]["est"]
reps160 = [f"REPWTP{i}" for i in range(1, 161)]
dd = d_asec.filter(pl.col("uninsured_ly").is_not_null())
yy = dd["uninsured_ly"].cast(pl.Float64).to_numpy()
th0 = float((dd["ASECWT"].to_numpy() * yy).sum() / dd["ASECWT"].sum())
thr = np.array([float((dd[c].to_numpy() * yy).sum() / dd[c].sum()) for c in reps160])
asec_hand = float(np.sqrt(4 / 160 * ((thr - th0) ** 2).sum()))
neg_values = int(sum(int((dd[c] < 0).sum()) for c in reps160))
check("CPS ASEC 2025 real data: replicate SE equals the hand SDR formula; default call reports df = n - 1",
      abs(asec_rep["se"] - asec_hand) / asec_hand < 1e-9 and asec_def["df"] == dd.height - 1
      and asec_rep["df"] == 159,
      replicate_se=float(asec_rep["se"]), hand_se=asec_hand, default_se=float(asec_def["se"]),
      default_df=int(asec_def["df"]), rep_mean_centered_se=float(asec_rm["se"]), n=dd.height,
      negative_replicate_values=neg_values)

# NHIS 2024: PSU codes, composite keys, and cluster-robust shortcuts
import pyfixest as pf  # noqa: E402

ad = (n24.filter(pl.col("current_smoker").is_not_null())
      .with_columns(pl.concat_str([pl.col("STRATA").cast(pl.Utf8), pl.lit("_"),
                                   pl.col("PSU").cast(pl.Utf8)]).alias("psu_key"),
                    pl.col("current_smoker").cast(pl.Float64)))
e_domain = PY["nhis"]["est"]
e_rows = (svy.Sample(ad, design=svy.Design(stratum="STRATA", psu="PSU", wgt="SAMPWEIGHT"))
          .estimation.mean("current_smoker").to_dicts()[0])
e_key = (svy.Sample(ad, design=svy.Design(stratum="STRATA", psu="psu_key", wgt="SAMPWEIGHT"))
         .estimation.mean("current_smoker").to_dicts()[0])
e_nostrata = (svy.Sample(ad, design=svy.Design(psu="psu_key", wgt="SAMPWEIGHT"))
              .estimation.mean("current_smoker").to_dicts()[0])
pdf = ad.select(["current_smoker", "SAMPWEIGHT", "PSU", "psu_key"]).to_pandas()
fit_key = pf.feols("current_smoker ~ 1", data=pdf, weights="SAMPWEIGHT", vcov={"CRV1": "psu_key"})
fit_lab = pf.feols("current_smoker ~ 1", data=pdf, weights="SAMPWEIGHT", vcov={"CRV1": "PSU"})
se_key, se_lab = float(fit_key.se().iloc[0]), float(fit_lab.se().iloc[0])
check("NHIS 2024: svy gives identical results with the PSU label or the (STRATA, PSU) key",
      abs(e_rows["se"] - e_key["se"]) < 1e-15 and abs(e_rows["est"] - e_key["est"]) < 1e-15)
check("NHIS 2024: domain estimate on the full file equals the estimate on the adult rows (all PSUs retained)",
      abs(e_domain["se"] - e_rows["se"]) / e_rows["se"] < 1e-10 and abs(e_domain["est"] - e_rows["est"]) < 1e-12,
      domain_se=float(e_domain["se"]), rows_se=float(e_rows["se"]))
check("NHIS 2024: CRV1 on the composite key equals Taylor with strata ignored (Appendix B.2)",
      abs(se_key - e_nostrata["se"]) / se_key < 1e-8, crv1=se_key, taylor_no_strata=float(e_nostrata["se"]))
check("NHIS 2024: current smoking reproduces the store benchmark (NCHS published 9.9%)",
      round(100 * e_domain["est"], 1) == 9.9, estimate=float(e_domain["est"]))
nhis_ratio_key = se_key / e_domain["se"]
nhis_ratio_lab = se_lab / e_domain["se"]

narrow_errs = {}
for dtype in (pl.Int8, pl.Int16):
    try:
        svy.Sample(n24.select(["STRATA", "PSU", "SAMPWEIGHT", "ASTATFLG", "current_smoker"])
                   .with_columns(pl.col("ASTATFLG").cast(dtype)),
                   design=svy.Design(stratum="STRATA", psu="PSU", wgt="SAMPWEIGHT")) \
            .estimation.mean("current_smoker", where=svy.col("ASTATFLG") == 1, drop_nulls=True)
        narrow_errs[str(dtype)] = "no error"
    except Exception as exc:  # noqa: BLE001
        narrow_errs[str(dtype)] = f"{type(exc).__name__}: {str(exc).strip().splitlines()[0][:100]}"
check("svy 0.28: a where= expression on an 8- or 16-bit integer column raises ComputeError; Int32 or wider "
      "works (narrow integer outcomes are fine)",
      all("ComputeError" in v for v in narrow_errs.values()), **narrow_errs)

# BRFSS 2024: the default (error) and the rule
b_err = ""
try:
    svy.Sample(PY["brfss"]["ns"]["d"], design=svy.Design(stratum="xststr", psu="xpsu", wgt="xllcpwt")) \
        .estimation.mean("fairpoor", drop_nulls=True)
except Exception as exc:  # noqa: BLE001
    b_err = f"{type(exc).__name__}: {str(exc).strip().splitlines()[0][:160]}"
check("BRFSS 2024: svy refuses the full-file design without a lonely-PSU rule",
      b_err.startswith("SingletonError") and str(brfss["singletons"]) in b_err, message=b_err)

# ------------------------------------------------------------------ 6. R sentinel checks
print("6. R")
RES: dict[str, dict[str, str]] = {}
if NO_R or not RSCRIPT.exists():
    validation.append({"check": "R survey sentinel checks", "pass": None, "status": "skipped"})
else:
    proc = subprocess.run([str(RSCRIPT), str(HERE / "verify.R"), str(BOX), str(SNIP)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
    for line in proc.stdout.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            RES.setdefault(parts[0], {})[parts[1]] = parts[2]
    if proc.returncode != 0 or "done" not in RES:
        print(proc.stdout[-3000:])
        print(proc.stderr[-3000:])
    check("verify.R completed", "done" in RES, returncode=proc.returncode,
          r=RES.get("env", {}).get("R", ""), survey=RES.get("env", {}).get("survey", ""))

    def cmp(tag: str, py: dict, tol_se: float = 1e-6) -> None:
        r = RES.get(tag, {})
        if "error" in r or "est" not in r:
            check(f"R snippet {tag}", False, error=r.get("error", "no output"))
            return
        est_r, se_r = float(r["est"]), float(r["se"])
        check(f"R snippet {tag} vs svy: same estimate and SE",
              abs(est_r - py["est"]) < 1e-9 and abs(se_r - py["se"]) / py["se"] < tol_se,
              r_est=est_r, svy_est=float(py["est"]), r_se=se_r, svy_se=float(py["se"]),
              rel_se_diff=abs(se_r - py["se"]) / py["se"], r_degf=r.get("degf"), svy_df=py.get("df"),
              seconds=r.get("seconds"))

    for tag in ("nhis", "nhanes", "brfss", "atus", "asec"):
        cmp(tag, PY[tag]["est"], tol_se=1e-4 if tag == "brfss" else 1e-6)
    nest_msg = RES.get("nhis_nest", {}).get("message", "")
    check("R svydesign stops on NHIS 2024 without nest = TRUE", "nest" in nest_msg.lower(), message=nest_msg)
    fail_msg = RES.get("brfss_fail", {}).get("message", "")
    check("R survey (lonely.psu = 'fail') stops on the full BRFSS 2024 design",
          fail_msg != "no error" and "psu" in fail_msg.lower(), message=fail_msg[:200])
    for R in (80, 160):
        r = RES.get(f"sdr{R}", {})
        ok = bool(r) and abs(float(r["se_survey"]) - float(r["se_hand"])) < 1e-12 \
            and abs(float(r["scale"]) - 4 / R) < 1e-12 and int(float(r["degf"])) == R - 1
        check(f"R survey type='successive-difference': scale 4/{R}, df {R - 1}, equals the hand formula", ok,
              **{k: r.get(k) for k in ("se_survey", "se_hand", "scale", "degf")})

# ------------------------------------------------------------------ 7. facts
print("7. facts")
SRC = {
    "acs_meta": "design.json: ipums/analysis/usa/metadata/acs.design.json",
    "asec_meta": "design.json: ipums/analysis/cps/metadata/cps_asec.design.json",
    "nhis": "IPUMS NHIS 2024 (ipums/analysis/nhis/nhis_core/part_2015_2024.parquet)",
    "nhanes": "NHANES August 2021-August 2023 (NHANES/data/processed/nhanes_analysis.parquet)",
    "brfss": "BRFSS 2024 (BRFSS/BRFSS_2026/cleaned/brfss_multi_rec.parquet)",
    "atus": "IPUMS ATUS 2024 (ipums/analysis/atus/atus_respondent.parquet)",
    "asec": "IPUMS CPS ASEC 2025 (ipums/analysis/cps/cps_asec and cps_asec_repwt, part_2020_2025)",
    "acs": "IPUMS USA ACS 2024 1-year (ipums/analysis/usa/acs/part_2020_2024.parquet)",
}
F: dict[str, dict] = {}


def count_fact(key, value, estimand, src, unit=None, note=""):
    F[key] = fact(int(value), f"{int(value):,}", estimand, src, unit=unit, n=None, note=note)


count_fact("acs_n_reps", ACS_R["n_reps"], "Number of person (and household) SDR replicate weights in the ACS 1-year PUMS",
           SRC["acs_meta"], unit="replicate weights")
count_fact("acs_df", ACS_R["df"], "Design degrees of freedom for ACS replicate-weight inference (replicates minus 1)",
           SRC["acs_meta"], unit="degrees of freedom", note=ACS_R["df_note"])
F["acs_scale"] = fact(ACS_R["scale"], ACS_R["scale_txt"], "SDR variance constant multiplying the sum of squared "
                      "replicate deviations (ACS)", SRC["acs_meta"])
count_fact("acs_n_persons", acs["n"], "Person records in the ACS 2024 1-year sample (IPUMS USA)", SRC["acs"],
           unit="person records")
count_fact("asec_n_reps", ASEC_R["n_reps"], "Number of person (and household) replicate weights in the CPS ASEC",
           SRC["asec_meta"], unit="replicate weights")
count_fact("asec_df", ASEC_R["df"], "Design degrees of freedom for CPS ASEC replicate-weight inference", SRC["asec_meta"],
           unit="degrees of freedom", note=ASEC_R["df_note"])
F["asec_scale"] = fact(ASEC_R["scale"], ASEC_R["scale_txt"], "Replicate variance constant (CPS ASEC)", SRC["asec_meta"])
count_fact("asec_n_persons", asec["wt_pos"], "Person records with a positive ASECWT, CPS ASEC 2025", SRC["asec"],
           unit="person records")

n_asec = dd.height
F["asec_uninsured"] = fact(
    r6(asec_rep["est"]), pct(asec_rep["est"]),
    "Share of persons uninsured for all of calendar year 2024 (store flag uninsured_ly), CPS ASEC 2025",
    SRC["asec"], se=r6(asec_rep["se"]), ci_low=r6(asec_rep["lci"]), ci_high=r6(asec_rep["uci"]),
    ci_display=f"{100 * asec_rep['lci']:.1f}%–{100 * asec_rep['uci']:.1f}%", df=int(asec_rep["df"]), n=n_asec,
    weight="ASECWT", variance="replicate_sdr(160)",
    benchmark="Store benchmark log reproduces Census's published all-year uninsured rates for CY2022 and CY2023",
    note="svy, method='replication', variance_center='estimate'; equals the hand formula (4/160) x sum of "
         "squared deviations")
F["asec_se_rep"] = fact(r6(100 * asec_rep["se"]), f"{100 * asec_rep['se']:.2f}",
                        "Replicate-weight SE of the CPS ASEC 2025 all-year uninsured share", SRC["asec"],
                        unit="percentage points", variance="replicate_sdr(160)", n=n_asec, df=int(asec_rep["df"]))
F["asec_se_default"] = fact(r6(100 * asec_def["se"]), f"{100 * asec_def['se']:.2f}",
                            "SE that svy's default estimation call reports for the same estimate, silently ignoring "
                            "the declared replicate weights", SRC["asec"], unit="percentage points",
                            variance="weights_only_understated", n=n_asec, df=int(asec_def["df"]),
                            note="Default call: Taylor linearization treating each person as a PSU, df = n - 1.")
F["asec_df_default"] = fact(int(asec_def["df"]), f"{int(asec_def['df']):,}",
                            "Degrees of freedom reported by svy's default call on the CPS ASEC replicate design (n - 1)",
                            SRC["asec"], unit="degrees of freedom")
F["asec_se_ratio"] = fact(round(asec_rep["se"] / asec_def["se"], 4), f"{asec_rep['se'] / asec_def['se']:.2f}×",
                          "Replicate SE divided by the default-call SE, CPS ASEC 2025 uninsured share", SRC["asec"])

count_fact("nhis_n_adults", nhis["adults"], "Sample adult records, NHIS 2024", SRC["nhis"], unit="records")
count_fact("nhis_n_children", nhis["children"], "Sample child records, NHIS 2024", SRC["nhis"], unit="records")
count_fact("nhis_strata", nhis["strata"], "Variance strata in the NHIS 2024 public file", SRC["nhis"], unit="strata")
count_fact("nhis_psus", nhis["psus"], "Distinct (STRATA, PSU) pairs in the NHIS 2024 public file", SRC["nhis"], unit="PSUs")
count_fact("nhis_psu_codes", nhis["psu_codes"], "Distinct PSU codes in NHIS 2024 (codes are reused across strata)",
           SRC["nhis"], unit="codes")
count_fact("nhis_df", nhis["df"], "Rule-of-thumb design degrees of freedom (PSUs minus strata), NHIS 2024", SRC["nhis"],
           unit="degrees of freedom", note="NCHS notes the rule of thumb is not directly applicable to the NHIS design.")
count_fact("nhis_min_psus", nhis["min_psus"], "Fewest PSUs in any stratum of the full NHIS 2024 file", SRC["nhis"], unit="PSUs")
count_fact("nhis_shared_psus", nhis["shared"], "(STRATA, PSU) pairs of NHIS 2024 that also appear in NHIS 2023",
           SRC["nhis"], unit="PSUs")
F["nhis_smoking"] = fact(
    r6(e_domain["est"]), pct(e_domain["est"]),
    "Share of US civilian noninstitutionalized adults who currently smoke cigarettes (store flag current_smoker), NHIS 2024",
    SRC["nhis"], se=r6(e_domain["se"]), ci_low=r6(e_domain["lci"]), ci_high=r6(e_domain["uci"]),
    ci_display=f"{100 * e_domain['lci']:.1f}%–{100 * e_domain['uci']:.1f}%", df=int(e_domain["df"]),
    n=ad.height, weight="SAMPWEIGHT", variance="taylor",
    benchmark="NCHS published 9.9% for 2024 (external benchmark; reproduced in logs/validation_benchmarks_clean.md)",
    note="Declared on the whole 2024 file, estimated for sample adults with where=; all PSUs retained.")
F["nhis_se_taylor"] = fact(r6(100 * e_domain["se"]), f"{100 * e_domain['se']:.3f}",
                           "Taylor-linearization SE (strata and PSUs) of NHIS 2024 adult current smoking", SRC["nhis"],
                           unit="percentage points", variance="taylor", n=ad.height, df=int(e_domain["df"]))
F["nhis_se_crv1"] = fact(r6(100 * se_key), f"{100 * se_key:.3f}",
                         "CRV1 SE of the same weighted mean, clustered on the (STRATA, PSU) key, strata ignored",
                         SRC["nhis"], unit="percentage points", variance="cluster_robust(psu)", n=ad.height,
                         note="pyfixest feols(current_smoker ~ 1, weights=SAMPWEIGHT, vcov={'CRV1': psu_key}).")
F["nhis_crv1_ratio"] = fact(round(nhis_ratio_key, 4), f"{nhis_ratio_key:.2f}×",
                            "CRV1 (composite PSU key) SE divided by the Taylor SE with strata, NHIS 2024 adult smoking",
                            SRC["nhis"])
F["nhis_se_label"] = fact(r6(100 * se_lab), f"{100 * se_lab:.3f}",
                          "CRV1 SE clustered on the PSU code alone, which merges PSUs from different strata",
                          SRC["nhis"], unit="percentage points", variance="cluster_robust(psu)", n=ad.height)
F["nhis_label_ratio"] = fact(round(nhis_ratio_lab, 4), f"{nhis_ratio_lab:.2f}×",
                             "CRV1 (PSU code alone) SE divided by the Taylor SE with strata", SRC["nhis"])

count_fact("nhanes_n_int", nhanes["interviewed"], "Participants interviewed, NHANES August 2021-August 2023",
           SRC["nhanes"], unit="participants")
count_fact("nhanes_n_exam", nhanes["examined"], "Participants examined in the mobile examination center",
           SRC["nhanes"], unit="participants")
count_fact("nhanes_strata", nhanes["strata"], "Masked variance pseudo-strata, NHANES August 2021-August 2023",
           SRC["nhanes"], unit="strata")
count_fact("nhanes_psus", nhanes["psus"], "Masked variance pseudo-PSUs, NHANES August 2021-August 2023",
           SRC["nhanes"], unit="PSUs")
count_fact("nhanes_df", nhanes["df"], "Design degrees of freedom (PSUs minus strata), NHANES August 2021-August 2023",
           SRC["nhanes"], unit="degrees of freedom")

count_fact("brfss_n", brfss["n"], "Respondent records in the BRFSS 2024 public file", SRC["brfss"], unit="respondents")
count_fact("brfss_jurisdictions", brfss["jurisdictions"], "Jurisdictions in the BRFSS 2024 public file (49 states, DC, "
           "and three territories)", SRC["brfss"], unit="jurisdictions")
count_fact("brfss_strata", brfss["strata"], "Variance strata (_STSTR), BRFSS 2024", SRC["brfss"], unit="strata")
count_fact("brfss_psus", brfss["psus"], "Distinct (_STSTR, _PSU) pairs, BRFSS 2024", SRC["brfss"], unit="PSUs")
count_fact("brfss_df", brfss["df"], "Design degrees of freedom (PSUs minus strata), BRFSS 2024", SRC["brfss"],
           unit="degrees of freedom")
count_fact("brfss_singletons", brfss["singletons"], "Strata containing a single PSU (one respondent) in the full "
           "BRFSS 2024 file", SRC["brfss"], unit="strata")

count_fact("atus_n", atus["n"], "Respondents (diary days) in ATUS 2024", SRC["atus"], unit="respondents")
count_fact("atus_n_reps", 160, "Replicate final weights BLS and IPUMS provide for each ATUS final weight",
           "BLS ATUS user's guide (June 2026); IPUMS ATUS RWT06", unit="replicate weights")
F["atus_scale"] = fact(4 / 160, "4/160", "ATUS replicate variance constant", "BLS ATUS user's guide (June 2026)",
                       note="The 4 comes from replicate factors 1.7, 1.0, and 0.3.")

# ------------------------------------------------------------------ 8. guides (table figures)
print("8. figures")


def guide(key: str, title: str, subtitle: str, alt: str, rows: list[dict], docs: list[str], note: str = "") -> None:
    src = "; ".join(f"{d} ({DOCS[d]})" for d in docs)
    write_json(FIG / f"guide_{key}.json", {
        "type": "table", "title": title, "subtitle": subtitle, "alt": alt, "columns": GUIDE_COLUMNS,
        "rows": rows, "source": src, "note": note or "Provenance: design.json = machine-readable manifest field; "
        "design.json notes = the manifest's free text; producer = documentation read " + VERIFIED +
        "; computed = counted from the store by build.py; book guidance = editorial, not a producer rule."})


m = M["acs_meta"]
r = ACS_R
guide("acs", "ACS 2024 1-year: declared", "IPUMS USA person file with the 80-replicate companion file",
      "Table declaring the ACS 2024 1-year release: universe, weights, successive difference replication with 80 "
      "replicates and 79 degrees of freedom, pooling, series breaks, known traps, and the date each item was verified.",
      [
          row("Pinned release", f"ACS 2024 1-year sample, IPUMS USA (SAMPLE = {ACS_SAMPLE})", "computed from data"),
          row("Records", f"{acs['n']:,} person records in the 2024 sample", "computed from data"),
          row("Universe", "Persons in housing units and group quarters (2005, the first ACS year, covers the "
              "household population only)", "design.json notes"),
          row("Canonical weight", f"{m['canonical_weight']}; {m['weight_notes']}", "design.json"),
          row("Alternate weights", "; ".join(f"{k} ({v})" for k, v in m["alternate_weights"].items()), "design.json"),
          row("Variance method", f"Replicate: {r['method']}", "design.json"),
          row("Replicate weights", f"{r['p_prefix']}1–{r['p_prefix']}{r['n_reps']} (person) and {r['h_prefix']}1–"
              f"{r['h_prefix']}{r['n_reps']} (household), in the companion file {r['companion']} joined on "
              f"{', '.join(r['join'])}", "design.json"),
          row("Variance formula", f"({r['scale_txt']}) × Σ_r (θ_r − θ̂)², deviations taken from the full-sample "
              "estimate (the mse option)", "design.json"),
          row("Design df", f"{r['df']} ({r['df_note']})", "design.json"),
          row("Strata and PSUs", "None declared with the replicates: treat the sample as one stratum with no PSU. "
              "The extract also carries IPUMS STRATA and CLUSTER for Taylor linearization; the book uses the "
              "replicates", "producer: IPUMS USA repwt FAQ; acs.dictionary.json"),
          row("Lonely-PSU rule", "Not applicable: no PSUs are declared", "book guidance"),
          row("Pooling rule", "Not recorded. For a multi-year period prefer the ACS 5-year sample; to pool k one-year "
              "samples, divide PERWT and every replicate weight by k before estimating totals (means and shares "
              "are unchanged)", "book guidance"),
          row("Series breaks", " ".join(m["notes"]), "design.json notes"),
          row("Negative replicate values", r["neg"], "design.json"),
          row("Trap: svy default call", "The default estimation call ignores declared replicate weights and returns "
              "a Taylor SE with df = n − 1. Pass method=\"replication\" and variance_center=\"estimate\", then "
              "assert df = 79", "verified in this build (synthetic frame)"),
          row("Trap: bare REPWTP", "IPUMS extracts can carry a variable named REPWTP (a flag): select REPWTP1–"
              "REPWTP80 by name, never with a wildcard", "producer: IPUMS USA repwt FAQ"),
          row("Trap: PUMS is a subsample", "Replicate SEs from the PUMS will not reproduce the margins of error Census "
              "publishes from the full ACS sample", "book guidance"),
          row("Last verified", f"Replicate block verified {r['verified'].get('date')} against "
              f"{r['verified'].get('source')}; FAQ re-read {VERIFIED}", "design.json; this build"),
      ], ["IPUMS USA repwt FAQ"])

m = M["asec_meta"]
r = ASEC_R
guide("cps_asec", "CPS ASEC 2025: declared", "IPUMS CPS ASEC person file with the 160-replicate companion file",
      "Table declaring the CPS ASEC 2025 release: universe, weights, 160 replicate weights with 159 degrees of "
      "freedom, pooling, series breaks, known traps, and the date each item was verified.",
      [
          row("Pinned release", "CPS ASEC 2025, IPUMS CPS (YEAR = 2025); income and last-year coverage items refer "
              "to calendar year 2024", "producer: IPUMS CPS"),
          row("Records", f"{asec['wt_pos']:,} person records with a positive ASECWT", "computed from data"),
          row("Universe", "Noninstitutionalized persons in the 50 states and DC who are civilian adults (15 and "
              "older) or live with one; Armed Forces members living with their families are included, those in "
              "barracks are not", "producer: Census ASEC documentation"),
          row("Sample note", "Includes the CHIP expansion sample (about 10,000 extra eligible housing units, part of "
              "the CPS since July 2001) to improve state estimates of children's coverage", "producer: Census ASEC documentation"),
          row("Canonical weight", f"{m['canonical_weight']}; {m['weight_notes']}", "design.json"),
          row("Alternate weights", "; ".join(f"{k} ({v})" for k, v in m["alternate_weights"].items()), "design.json"),
          row("Variance method", f"Replicate: {r['method']}", "design.json"),
          row("Replicate weights", f"{r['p_prefix']}1–{r['p_prefix']}{r['n_reps']} (person) and {r['h_prefix']}1–"
              f"{r['h_prefix']}{r['n_reps']} (household), in the companion file {r['companion']} joined on "
              f"{', '.join(r['join'])}", "design.json"),
          row("Variance formula", f"({r['scale_txt']}) × Σ_r (θ_r − θ̂)², deviations taken from the full-sample "
              "estimate", "design.json"),
          row("Design df", f"{r['df']} ({r['df_note']}); replicate weights cover {r['coverage']}", "design.json"),
          row("Strata and PSUs", "None declared with the replicates", "producer: IPUMS CPS repwt FAQ"),
          row("Lonely-PSU rule", "Not applicable: no PSUs are declared", "book guidance"),
          row("Pooling rule", "Not recorded. To pool k ASEC years, divide ASECWT and every replicate weight by k "
              "before estimating totals (means and shares are unchanged)", "book guidance"),
          row("Series breaks", " ".join(m["notes"]) + " A 2020-Census-based CPS sample began phasing in with April "
              "2025 and completes in July 2026 (BLS expects a negligible effect on estimates)",
              "design.json notes; producer: BLS"),
          row("Negative replicate values", f"{r['neg']}; {neg_values:,} negative replicate values among the 2025 "
              "person records. Stata declares iweights for this reason", "design.json; computed from data; "
              "producer: IPUMS CPS repwt FAQ"),
          row("Trap: svy default call", f"Verified on the 2025 file: the default call reports a Taylor SE with "
              f"df = {int(asec_def['df']):,} (n − 1); the replicate call reports df = {int(asec_rep['df'])}",
              "verified in this build (real data)"),
          row("Trap: survey year", "YEAR is the survey year; income, poverty, and last-year coverage describe the "
              "previous calendar year", "producer: IPUMS CPS"),
          row("Last verified", f"Replicate block verified {r['verified'].get('date')} against "
              f"{r['verified'].get('source')}; FAQ re-read {VERIFIED}", "design.json; this build"),
      ], ["IPUMS CPS repwt FAQ", "Census ASEC documentation", "BLS CPS sample redesign"])

m = M["nhis_meta"]
geo = "; ".join(f"{g['level']}: {'licensed' if g['representative'] else 'not licensed'}" for g in m["geo_levels"])
guide("nhis", "NHIS 2024: declared", "IPUMS NHIS sample adult and sample child records, Taylor linearization",
      "Table declaring the NHIS 2024 release: universe, weights, strata and PSU counts, rule-of-thumb degrees of "
      "freedom, the lonely-PSU rule, pooling, series breaks, and known traps.",
      [
          row("Pinned release", "NHIS 2024 (IPUMS NHIS, YEAR = 2024), fielded under the 2016–2025 sample design",
              "producer: NCHS 2024 survey description"),
          row("Records", f"{nhis['adults']:,} sample adults and {nhis['children']:,} sample children", "computed from data"),
          row("Universe", "Civilian noninstitutionalized population of the United States", "producer: NCHS"),
          row("Canonical weight", f"{m['canonical_weight']}; {m['weight_notes']}", "design.json"),
          row("Full-population weight rule", m["weight_rule_fullpop"], "design.json"),
          row("Weight construction", "The final annual weight includes design, ratio, nonresponse, and calibration "
              "adjustments; calibration controls are age by sex, age by race and ethnicity, education, housing "
              "tenure, and region by MSA status", "producer: NCHS 2024 survey description"),
          row("Variance method", f"Taylor linearization (variance_tier: {m['variance_tier']}), PSUs treated as sampled with "
              "replacement", "design.json; producer: NCHS"),
          row("Strata and PSUs", f"STRATA and PSU (NCHS names PSTRAT and PPSU): {nhis['strata']} strata and "
              f"{nhis['psus']} PSUs, but only {nhis['psu_codes']} distinct PSU codes, reused across strata",
              "computed from data"),
          row("Composite key", m["composite_key_warning"], "design.json"),
          row("Design df", f"{nhis['df']} by the rule PSUs − strata. NCHS notes that the rule is not directly "
              "applicable to the NHIS design; a normal approximation may be adequate when a variable is spread "
              "across most clusters", "computed from data; producer: NCHS"),
          row("Lonely-PSU rule", f"{m['lonely_psu_rule']}. Every stratum of the full 2024 file has at least "
              f"{nhis['min_psus']} PSUs", "design.json; computed from data"),
          row("Zero-weight rows", m["zero_weight_rows"], "design.json"),
          row("Pooling rule", f"{m['pooling_rules']} NCHS's 2024 guidance: divide the weight by the number of years "
              f"pooled and keep PSTRAT and PPSU as they are; {nhis['shared']} of the {nhis['psus']} (STRATA, PSU) "
              "pairs of 2024 also appear in 2023", "design.json; producer: NCHS; computed from data"),
          row("Series breaks", "; ".join(f"{s['year']}: {s['label']}. {s['reason']}" for s in m["series_breaks"])
              + " The 2024 sample adds a 25 percent increase in nonmetropolitan households",
              "design.json; producer: NCHS"),
          row("Geography", geo, "design.json"),
          row("Trap: PSU codes", "svy nests PSU codes within the declared strata; R's svydesign stops without "
              "nest = TRUE; code that groups or clusters on PSU alone merges unrelated PSUs", "verified in this build (real data)"),
          row("Last verified", f"Extended design.json block added 2026-07-11; NCHS and IPUMS documents re-read {VERIFIED}",
              "design.json; this build"),
      ], ["NCHS 2024 NHIS survey description", "IPUMS NHIS variance note"])

m = M["atus_meta"]
guide("atus", "ATUS 2024: declared", "IPUMS ATUS respondent file; the book's extract carries weights only",
      "Table declaring the ATUS 2024 release: universe, the diary-day weight, day-of-week sampling, the absence of "
      "design variables in the book's extract, the producer's 160 replicate weights, pooling, and known traps.",
      [
          row("Pinned release", "ATUS 2024 (IPUMS ATUS, YEAR = 2024)", "computed from data"),
          row("Records", f"{atus['n']:,} respondents, one diary day each", "computed from data"),
          row("Universe", "Civilian noninstitutional population age 15 and older; one person per household, drawn "
              "from households completing their final CPS interview", "producer: BLS ATUS user's guide"),
          row("Unit", m["weight_notes"], "design.json"),
          row("Canonical weight", f"{m['canonical_weight']} (BLS: TUFNWGTP on multi-year files, TUFINLWGT on annual files)",
              "design.json; producer: BLS"),
          row("Alternate weights", "; ".join(f"{k}: {v}" for k, v in m["alternate_weights"].items()), "design.json"),
          row("Day sampling", "10 percent of the sample is assigned to each weekday and 25 percent to each weekend "
              "day; the weights return weekdays to about 5/7 of person-days", "producer: BLS ATUS user's guide"),
          row("Variance in the store", "Weights only: no strata, PSUs, or replicate weights in the extract (STRATA is "
              "empty), so SEs understate design variance. " + m["notes"][0], "design.json notes; computed from data"),
          row("Producer replicates", "160 replicate final weights (IPUMS RWT06_1–RWT06_160; BLS FINLWGT001–FINLWGT160); "
              "Var = (4/160) × Σ_r (Ŷ_r − Ŷ_0)², the 4 coming from replicate factors 1.7, 1.0, and 0.3",
              "producer: BLS ATUS user's guide; IPUMS ATUS"),
          row("Design df", "Not stated by BLS; the replicate-count convention gives 159", "book guidance"),
          row("Lonely-PSU rule", "Not applicable", "book guidance"),
          row("Pooling rule", "Combine years whose weights were built the same way: WT06 for 2003–2019 and 2021 "
              "onward, WT20 for 2020. " + m["notes"][1], "producer: BLS; design.json notes"),
          row("Series breaks", "2020: collection suspended March 18 to May 9, 2020, and WT20 represents only the days "
              "covered; the weighting method changed each year from 2003 to 2006", "producer: BLS; design.json"),
          row("Zero-weight rows", m["zero_weight_rows"], "design.json"),
          row("Trap: person-days", "Weights sum to person-days, not persons: an average over days is not an average "
              "over people", "design.json"),
          row("Trap: unweighted tabulations", "Unweighted tabulations overstate activities done more often on weekends",
              "producer: BLS ATUS user's guide"),
          row("Last verified", f"BLS user's guide (June 2026 edition) and IPUMS RWT06 description read {VERIFIED}",
              "this build"),
      ], ["BLS ATUS user's guide (June 2026)", "IPUMS ATUS RWT06"])

m = M["nhanes_meta"]
guide("nhanes", "NHANES August 2021–August 2023: declared", "Masked variance units, Taylor linearization",
      "Table declaring the NHANES August 2021 to August 2023 release: universe, sample design, exam and interview "
      "weights, 15 pseudo-strata and 30 pseudo-PSUs with 15 degrees of freedom, pooling rules, series breaks, and "
      "response rates.",
      [
          row("Pinned release", "NHANES August 2021–August 2023 (file suffix _L; store CYCLE_YEAR = 2021)",
              "design.json; producer: NCHS"),
          row("Records", f"{nhanes['interviewed']:,} interviewed, of whom {nhanes['examined']:,} were examined; "
              "NCHS's DEMO_L counts match", "computed from data; producer: NCHS DEMO_L documentation"),
          row("Universe", "US civilian noninstitutionalized population, all ages", "producer: NCHS"),
          row("Sample design", "Multi-year, stratified, clustered four-stage sample with 30 PSUs (counties). No "
              "oversampling by race, Hispanic origin, or income this cycle; everyone aged 0–19 or 60 and older "
              "encountered in a sampled household was selected", "producer: NCHS overview brief"),
          row("Canonical weight", "WTMEC2YR for examination and laboratory variables and for any model mixing "
              "interview and exam variables; WTINT2YR for interview-only analyses. Not WTMECPRP, which belongs to "
              "the 2017–March 2020 file", "design.json"),
          row("Alternate weights", "Dietary WTDRD1 and WTDR2D; fasting subsample WTSAF2YR; NCHS added a phlebotomy "
              "weight in this release to address possible nonresponse bias", "design.json; producer: NCHS overview brief"),
          row("Variance method", f"Taylor linearization (variance_method: {m['variance_method']}). "
              f"{m['replicate_weights_note']}", "design.json"),
          row("Strata and PSUs", f"SDMVSTRA (codes {nhanes['smin']}–{nhanes['smax']}) and SDMVPSU: {nhanes['strata']} "
              f"masked pseudo-strata and {nhanes['psus']} pseudo-PSUs, two per stratum", "computed from data; design.json"),
          row("Design df", f"{nhanes['df']} (PSUs − strata)", "computed from data; producer: NHANES tutorial"),
          row("Lonely-PSU rule", m["lonely_psu_guidance"] + " In svy 0.28 the rule is named \"center\": "
              "s.singleton.handle(\"center\"), which matched R's \"adjust\" exactly on BRFSS 2024 in this build.",
              "design.json; verified in this build"),
          row("Zero-weight rows", m["zero_weight_rows"], "design.json"),
          row("Pooling rule", m["pooling_rules"], "design.json"),
          row("Double count", m["double_count_caveat"], "design.json"),
          row("Series breaks", "Blood pressure is oscillometric (BPXO) from 2017 and reads lower than the "
              "auscultatory BPX used through 2015–2016; a 1.5-year gap separates this cycle from the 2017–March 2020 "
              "file; sample design and screener changed", "DATA_GUIDE.md; producer: NCHS overview brief"),
          row("Response", "Interview response 34.6% and examination response 25.7%, down from 51.0% and 46.9% in "
              "2017–March 2020; NCHS's nonresponse-bias assessment found no major bias not addressed by weighting",
              "producer: NCHS overview brief"),
          row("Geography", "National only; the masked variance units are not geography", "design.json notes"),
          row("Last verified", f"design.json generated 2026-07-11; DEMO_L documentation, overview brief, and tutorial "
              f"read {VERIFIED}", "design.json; this build"),
      ], ["NCHS DEMO_L documentation", "NCHS NHANES 2021-2023 overview brief", "NHANES tutorial: variance estimation"])

guide("brfss", "BRFSS 2024: declared", "CDC combined landline and cell-phone file; the book's store keeps the final weight",
      "Table declaring the BRFSS 2024 release: coverage without Tennessee, the weighting chain, 2,393 strata with every "
      "respondent its own PSU, the need for a lonely-PSU rule, pooling, series breaks, and known traps.",
      [
          row("Pinned release", "BRFSS 2024 combined landline and cell-phone file (LLCP2024), released August 2025; "
              "store: BRFSS_2026 cleaned parquet (iyear = 2024)", "producer: CDC; BRFSS_2026 CHANGELOG"),
          row("Records", f"{brfss['n']:,} respondents in {brfss['jurisdictions']} jurisdictions", "computed from data"),
          row("Universe", "Noninstitutionalized adults 18 and older in 49 states, DC, Guam, Puerto Rico, and the US "
              "Virgin Islands. Tennessee could not collect enough data for the 2024 public file: the target is "
              "adults in participating jurisdictions, not US adults", "producer: CDC 2024 overview; computed from data"),
          row("Canonical weight", "_LLCPWT (store: xllcpwt), the raked final weight", "producer: CDC complex sampling weights"),
          row("Alternate weights", "_LCPWTV1, _LCPWTV2, _LCPWTV3 for module questions asked on questionnaire versions "
              "1–3 (files LLCP24V1–LLCP24V3); _CLLCPWT for child interviews",
              "producer: CDC complex sampling weights; CDC 2024 weighting description"),
          row("Weight construction", "Design weight = _STRWT × (1/NUMPHON4) × NUMADULT (both factors 1 for cell "
              "respondents); dual-frame compositing for dual phone users; truncation within region at the mean "
              "± 1.96 SD (_LLCPWT2); raking to 8 state margins plus up to 8 regional and county margins, age by sex last",
              "producer: CDC 2024 weighting description"),
          row("Weights in the store", "Only the final xllcpwt; _STRWT, _WT2RAKE, _LLCPWT2, NUMADULT, and NUMPHON4 were "
              "dropped by the harmonized build", "BRFSS_2026 README; v4 plan"),
          row("Variance method", "Taylor linearization with _STSTR (strata) and _PSU (store: xststr, xpsu)",
              "producer: CDC complex sampling weights"),
          row("Strata and PSUs", f"{brfss['strata']:,} strata and {brfss['psus']:,} PSUs: every respondent is its own "
              f"PSU ({brfss['psu_codes']:,} distinct PSU codes, reused across strata)", "computed from data"),
          row("Design df", f"{brfss['df']:,} (PSUs − strata)", "computed from data"),
          row("Lonely-PSU rule", f"Required even for national estimates: {brfss['singletons']} strata hold a single "
              "respondent in the full 2024 file. CDC's R example sets survey.lonely.psu = \"adjust\"; the book uses "
              "\"adjust\" in R and \"center\" in svy", "computed from data; producer: CDC complex sampling weights"),
          row("Pooling rule", "Not covered by the 2024 documents consulted. When pooling years, keep each year's "
              "strata distinct and divide weights by the number of years before estimating totals", "book guidance"),
          row("Series breaks", "Raking and cell phones from 2011 (CDC: begin new trend lines in 2011); coverage "
              "changes by year (2021 omits Florida; 2023 omits Kentucky and Pennsylvania; 2024 omits Tennessee); "
              "2020 collection disrupted by COVID; the 2023 file was re-released in February 2025 without sexual "
              "orientation and gender identity items, which the 2024 file also omits",
              "producer: CDC; BRFSS_2026 CHANGELOG; v4 plan"),
          row("Geography", "Built for state estimates: each state's sample is weighted to its own adult population",
              "producer: CDC 2024 weighting description"),
          row("Trap: self-report", "Every measure is self-reported by telephone; weighting repairs representation, "
              "not measurement", "producer: CDC 2024 overview; book guidance"),
          row("Last verified", f"CDC 2024 overview, weighting description, and complex-sampling-weights document "
              f"read {VERIFIED}", "this build"),
      ], ["CDC BRFSS 2024 overview", "CDC BRFSS 2024 weighting description", "CDC BRFSS 2024 complex sampling weights"])

write_json(FIG / "surveys_at_a_glance.json", {
    "type": "table",
    "title": "Six surveys at a glance",
    "subtitle": "What a row represents, which weight, and where the uncertainty comes from",
    "alt": "Table comparing the six surveys: pinned release, unit, canonical weight, variance method, number of "
           "independent units, design degrees of freedom, and the variance tier in the book's store.",
    "columns": [
        {"key": "survey", "label": "Survey", "align": "left"},
        {"key": "unit", "label": "A row is", "align": "left"},
        {"key": "weight", "label": "Canonical weight", "align": "left"},
        {"key": "method", "label": "Variance method", "align": "left"},
        {"key": "units", "label": "Independent units", "align": "left"},
        {"key": "df", "label": "Design df", "align": "right"},
        {"key": "tier", "label": "Tier in the store", "align": "left"},
    ],
    "rows": [
        {"survey": "ACS 2024 1-year", "unit": "a person (households: HHWT on PERNUM = 1)", "weight": "PERWT",
         "method": "successive difference replication", "units": f"{ACS_R['n_reps']} replicates",
         "df": f"{ACS_R['df']}", "tier": "replicate"},
        {"survey": "CPS ASEC 2025", "unit": "a person (households: ASECWTH)", "weight": "ASECWT",
         "method": "SDR and modified half-sample replication", "units": f"{ASEC_R['n_reps']} replicates",
         "df": f"{ASEC_R['df']}", "tier": "replicate"},
        {"survey": "NHIS 2024", "unit": "a sample adult or sample child", "weight": "SAMPWEIGHT",
         "method": "Taylor linearization", "units": f"{nhis['psus']} PSUs in {nhis['strata']} strata",
         "df": f"{nhis['df']} (rule of thumb)", "tier": "taylor"},
        {"survey": "ATUS 2024", "unit": "a person-day (one diary day)", "weight": "WT06",
         "method": "producer: 160 replicates; store: weights only", "units": "none in the store",
         "df": "not available", "tier": "weights only (SEs understated)"},
        {"survey": "NHANES Aug 2021–Aug 2023", "unit": "a person (exam or interview)", "weight": "WTMEC2YR or WTINT2YR",
         "method": "Taylor linearization", "units": f"{nhanes['psus']} PSUs in {nhanes['strata']} strata",
         "df": f"{nhanes['df']}", "tier": "taylor"},
        {"survey": "BRFSS 2024", "unit": "an adult respondent", "weight": "_LLCPWT",
         "method": "Taylor linearization", "units": f"{brfss['psus']:,} PSUs (one per respondent) in {brfss['strata']:,} strata",
         "df": f"{brfss['df']:,}", "tier": "taylor"},
    ],
    "source": "Design manifests (design.json) and counts computed by ch07-field-guide/build.py; ATUS replicates per "
              "the BLS ATUS user's guide",
    "note": "Design df: replicates minus 1 for replicate designs; PSUs minus strata for Taylor designs.",
})

# ------------------------------------------------------------------ 9. ledger
ledger = {"nhis_smoking": {
    "title": "A field-guide example: adult cigarette smoking, NHIS 2024",
    "target_population": "Civilian noninstitutionalized adults 18 and older in the United States, 2024.",
    "estimand": "The share of those adults who currently smoke cigarettes, as coded by the store's current_smoker "
                "flag (from IPUMS SMOKESTATUS2): a finite-population proportion for 2024.",
    "estimator": "Hajek weighted proportion over sample adults with a known smoking status, declared on the whole "
                 "2024 file and estimated as a domain.",
    "explicit_weights": "SAMPWEIGHT (NCHS WTFA_A): base weights adjusted for nonresponse and calibrated to age by "
                        "sex, age by race and ethnicity, education, housing tenure, and region by MSA status.",
    "implicit_weights": "None beyond the explicit weights: a proportion gives each adult influence in proportion "
                        "to SAMPWEIGHT.",
    "randomness": "Sampling of address clusters (PSUs) within strata and of households within clusters, plus "
                  "response; the weight adjustments are themselves estimated.",
    "variance_estimator": "Taylor linearization with STRATA and PSU (PSUs nested in strata, treated as sampled with "
                          "replacement); df by the rule PSUs minus strata. A CRV1 shortcut on the same key omits the "
                          "stratification gain.",
    "assumptions": "The public pseudo-strata and PSUs approximate the confidential design; nonresponse and "
                   "calibration adjustments remove nonresponse bias; self-reports are accurate. An external "
                   "benchmark (NCHS's published rate) is a check, not truth.",
    "facts": ["ch7.nhis_smoking", "ch7.nhis_df", "ch7.nhis_strata", "ch7.nhis_psus", "ch7.nhis_crv1_ratio"],
}}

# ------------------------------------------------------------------ 10. snippet drift check and outputs
mdx_path = HERE / "article.mdx"
if mdx_path.exists():
    mdx = mdx_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    missing = [f"{k}.{e}" for (k, e), code in SNIPPETS.items() if code.strip() not in mdx]
    check("every generated snippet appears verbatim in article.mdx", not missing, missing=", ".join(missing))

write_json(ART / "facts.json", {"key": KEY, "facts": F})
write_json(ART / "ledger.json", {"key": KEY, "ledgers": ledger})
for k, v in (("acs_repwt", "ipums/analysis/usa/metadata/acs_repwt.design.json"),):
    pass
inputs = [
    {"path": "ipums/analysis/usa/metadata/acs.design.json", "note": "canonical weights, replicate block, notes"},
    {"path": "ipums/analysis/usa/metadata/acs_repwt.design.json", "note": "see_parent: acs"},
    {"path": "ipums/analysis/cps/metadata/cps_asec.design.json", "note": "canonical weights, replicate block, notes"},
    {"path": "ipums/analysis/cps/metadata/cps_asec_repwt.design.json", "note": "see_parent: cps_asec"},
    {"path": "ipums/analysis/nhis/metadata/nhis_core.design.json", "note": "extended block: variance tier, lonely-PSU rule, pooling, breaks, geography"},
    {"path": "ipums/analysis/atus/metadata/atus_respondent.design.json", "note": "weights and notes"},
    {"path": "NHANES/data/processed/design.json", "note": "weights, pooling, double-count caveat, lonely-PSU guidance"},
    {"path": "BRFSS/BRFSS_2026/{README,CHANGELOG,VERIFICATION}.md", "note": "store provenance; no design.json exists"},
    {"path": "ipums/analysis/cps/cps_asec_repwt/part_2020_2025.parquet", "rows": d_asec.height,
     "note": "YEAR, SERIAL, PERNUM, REPWTP1-REPWTP160 for YEAR = 2025 (read by the executed snippet)"},
] + inputs
write_json(ART / "manifest.json", {
    "key": KEY, "slug": SLUG, "status": "draft", "inputs": inputs, "code": "build.py",
    "verify": "verify.R (sourced snippets: snippets/*.R)",
    "producer_documents": DOCS, "producer_documents_read": VERIFIED,
    "validation": validation,
    "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
})
bad = [v["check"] for v in validation if v.get("pass") is False]
print(f"ch7: {len(F)} facts, {len(list(FIG.glob('*.json')))} figures; validation "
      + ("all pass" if not bad else f"FAILED: {bad}"))
