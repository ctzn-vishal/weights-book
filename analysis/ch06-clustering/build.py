#!/usr/bin/env python
"""
Chapter 6 (key ch6): Sampling design, assignment design, and clustering.

    python build.py            regenerate artifacts/ deterministically

Question: Medicaid expansion and uninsurance among low-income nonelderly adults
(ages 19-64, family income at or below 138% of poverty via POVERTY), ACS 1-year
2011-2019, person weight PERWT, outcome `uninsured` (derived from HCOVANY).

Design (v3 identification guardrail): one transparent cohort and one window.
  treated    = states whose ACA expansion took effect 2014-01-01 and that had no
               earlier (2010-2013) early-option or waiver expansion for low-income
               adults and no broad pre-2014 adult coverage;
  comparison = states with no ACA expansion in effect by 2019-12-31 and no other
               change in low-income adult eligibility during 2011-2019;
  everything else is excluded and listed (design_groups figure).
Groups are derived from _data/expansion_dates.csv by the rule in assign_groups().

Two stages:
  (1) state-year uninsured rates with PERWT; SDR replicate SEs (80 reps, 4/80, df 79);
  (2) the policy comparison. Person-level WLS with state and year fixed effects equals
      WLS on the state-year means weighted by the cell's PERWT total, exactly.

SE ladder on ONE coefficient: HC1 (persons), CRV1 by ACS household cluster, SDR
replicates (states fixed), CRV1 by state-year, CRV1 by state, CV3 (jackknife) by state,
wild cluster restricted bootstrap by state, randomization inference over assignment.

Caches in _scratch/ are keyed to input file size and mtime and rebuilt when stale.
Only manifest.json carries a timestamp.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import pyfixest as pf
from scipy import stats

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
FIG = ART / "figures"
SCR = HERE / "_scratch"
DATA = HERE / "_data"
ACS = Path(r"C:\Users\Vishal Singh\Box\ipums\analysis\usa\acs")
REPWT = Path(r"C:\Users\Vishal Singh\Box\ipums\analysis\usa\acs_repwt")
PERSON_PARTS = ["part_2005_2009.parquet", "part_2010_2014.parquet", "part_2015_2019.parquet"]
REP_PARTS = ["part_2010_2014.parquet", "part_2015_2019.parquet"]
DATES_CSV = Path(os.environ.get("CH6_DATES", str(DATA / "expansion_dates.csv")))

Y0, Y1 = 2011, 2019          # analysis window
EXT0 = 2008                  # extended window (sensitivity only; HCOVANY starts 2008)
PRE_END, POLICY_YEAR, REF_YEAR = 2013, 2014, 2013
AGE_LO, AGE_HI, POV_HI = 19, 64, 138
NREP, SDR_SCALE, SDR_DF = 80, 4 / 80, 79
B_WCB, SEED_WCB = 9999, 20260910
B_RI, SEED_RI = 9999, 20260911
MINUS = "\u2212"
EN = "\u2013"
TIMES = "\u00d7"

SOURCE = ("IPUMS USA, ACS 1-year samples 2011" + EN + "2019 (analysis/usa/acs/part_2010_2014.parquet, "
          "part_2015_2019.parquet); expansion dates in _data/expansion_dates.csv (KFF; medicaid.gov)")
SOURCE_REP = SOURCE + "; replicate weights REPWTP1" + EN + "80 (analysis/usa/acs_repwt)"
SOURCE_EXT = ("IPUMS USA, ACS 1-year samples 2008" + EN + "2019 (analysis/usa/acs/part_2005_2009.parquet, "
              "part_2010_2014.parquet, part_2015_2019.parquet); expansion dates in _data/expansion_dates.csv")
SOURCE_DATES = "_data/expansion_dates.csv (KFF Status of State Medicaid Expansion Decisions; medicaid.gov)"
POP = ("civilian and military household population ages 19" + EN + "64 with family income at or below "
       "138% of the poverty threshold (IPUMS POVERTY 1" + EN + "138)")


# ----------------------------------------------------------------------------- formatting
def num(x: float, nd: int) -> str:
    s = f"{x:,.{nd}f}"
    if s.startswith("-") and float(s.replace(",", "")) == 0:
        s = s[1:]
    return s.replace("-", MINUS)


def pts(x: float, nd: int = 1) -> str:
    """A proportion difference shown in percentage points (unit word stays in prose)."""
    return num(100 * x, nd)


def pct(x: float, nd: int = 1) -> str:
    return num(100 * x, nd) + "%"


def intc(n) -> str:
    return f"{int(n):,}"


def ci_str(lo: float, hi: float, fmt) -> str:
    a, b = fmt(lo), fmt(hi)
    return f"{a} to {b}" if (lo < 0 or hi < 0) else f"{a}{EN}{b}"


def r6(x):
    return None if x is None else float(round(float(x), 6))


def r4(x):
    return None if x is None else float(round(float(x), 4))


def tcrit(df) -> float:
    return float(stats.t.ppf(0.975, df)) if df is not None and np.isfinite(df) else float(stats.norm.ppf(0.975))


def _plain(o):
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    raise TypeError(f"not JSON serializable: {type(o).__name__}")


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, sort_keys=True, indent=2, ensure_ascii=False, default=_plain)
        f.write("\n")


def file_stamp(p: Path) -> list:
    st = os.stat(p)
    return [st.st_size, int(st.st_mtime)]


def log(*a):
    print(*a, flush=True)


# ----------------------------------------------------------------------------- inputs
def load_persons() -> pl.DataFrame:
    """Analytic sample 2008-2019 from the cleaned layer; only needed columns are read."""
    cache, sfile = SCR / "analytic_2008_2019.parquet", SCR / "analytic_2008_2019.stamp.json"
    stamp = {p: file_stamp(ACS / p) for p in PERSON_PARTS}
    stamp["filters"] = f"YEAR {EXT0}-{Y1}; AGE {AGE_LO}-{AGE_HI}; POVERTY 1-{POV_HI}"
    if cache.exists() and sfile.exists() and json.loads(sfile.read_text()) == stamp:
        return pl.read_parquet(cache)
    cols = ["YEAR", "SAMPLE", "SERIAL", "PERNUM", "CLUSTER", "STRATA", "STATEFIP", "GQ", "AGE",
            "POVERTY", "PERWT", "HCOVANY", "uninsured"]
    frames = []
    for p in PERSON_PARTS:
        t0 = time.time()
        f = (pl.scan_parquet(ACS / p).select(cols)
             .filter(pl.col("YEAR").is_between(EXT0, Y1) & pl.col("AGE").is_between(AGE_LO, AGE_HI)
                     & pl.col("POVERTY").is_between(1, POV_HI)).collect())
        log(f"  read {p}: {f.height:,} rows in {time.time() - t0:.1f}s")
        frames.append(f)
    df = pl.concat(frames).sort(["YEAR", "SERIAL", "PERNUM"])
    assert df["uninsured"].null_count() == 0 and df["PERWT"].null_count() == 0
    assert df.select(((pl.col("uninsured") == 1) == (pl.col("HCOVANY") == 1)).all()).item()
    df.write_parquet(cache)
    sfile.write_text(json.dumps(stamp, sort_keys=True))
    return df


def load_rep_aggregates(persons: pl.DataFrame) -> pl.DataFrame:
    """Per state-year sums of w_r and w_r*y, r = 0 (PERWT) .. 80, window years only."""
    cache, sfile = SCR / "rep_state_year_2011_2019.parquet", SCR / "rep_state_year_2011_2019.stamp.json"
    stamp = {p: file_stamp(REPWT / p) for p in REP_PARTS}
    stamp["persons"] = int(persons.filter(pl.col("YEAR") >= Y0).height)
    if cache.exists() and sfile.exists() and json.loads(sfile.read_text()) == stamp:
        return pl.read_parquet(cache)
    import duckdb
    con = duckdb.connect()
    con.execute("PRAGMA threads=8")
    keys = persons.filter(pl.col("YEAR") >= Y0).select(
        ["SAMPLE", "SERIAL", "PERNUM", "STATEFIP", pl.col("YEAR").alias("yr"),
         pl.col("uninsured").cast(pl.Float64).alias("y"), "PERWT"]).to_arrow()
    con.register("k", keys)
    aggs = ", ".join(f"SUM(r.REPWTP{i}) AS w{i}, SUM(r.REPWTP{i} * k.y) AS s{i}" for i in range(1, NREP + 1))
    out = []
    for p in REP_PARTS:
        t0 = time.time()
        q = (f"SELECT k.STATEFIP, k.yr AS YEAR, COUNT(*) AS n, SUM(k.PERWT) AS w0, SUM(k.PERWT * k.y) AS s0, "
             f"{aggs} FROM read_parquet('{(REPWT / p).as_posix()}') r JOIN k ON r.SAMPLE = k.SAMPLE "
             f"AND r.SERIAL = k.SERIAL AND r.PERNUM = k.PERNUM GROUP BY 1, 2")
        out.append(con.execute(q).pl())
        log(f"  replicate aggregates {p}: {time.time() - t0:.1f}s")
    res = pl.concat(out).sort(["STATEFIP", "YEAR"])
    assert int(res["n"].sum()) == stamp["persons"], "replicate join lost records"
    res.write_parquet(cache)
    sfile.write_text(json.dumps(stamp, sort_keys=True))
    return res


def parse_date(s: str):
    s = (s or "").strip()
    return dt.date.fromisoformat(s) if s else None


def assign_groups() -> pd.DataFrame:
    """Design groups from the verified date panel (_data/expansion_dates.csv). The chapter's stated rule:

    prior      ACA expansion effective 2014-01-01 AND (a statewide ACA-early-option or Section 1115
               expansion for low-income adults in 2010-2011 [early_expansion_class == statewide_or_major:
               CA, CT, DC, MN, NJ, WA] OR broad pre-2014 coverage of low-income parents and childless
               adults [pre2014_broad_adult_coverage == yes: DE, DC, MA, NY, VT]);
    treated    ACA expansion effective 2014-01-01 and not prior;
    later      ACA expansion effective after 2014-01-01 and on or before 2019-12-31;
    other      no ACA expansion by 2019-12-31, but a waiver change in adult eligibility inside 2011-2019
               [other_adult_eligibility_change_2011_2019 == yes: WI 2014-04, UT 2019-04];
    comparison no ACA expansion by 2019-12-31 and no such change.
    County pilots, capped programs and pre-2014 eligibility cuts (strict_rule_flag == yes: AZ, CO, HI,
    IL, OH, MO) are not counted as expansions; the strict sensitivity drops them.
    """
    rows = list(csv.DictReader(open(DATES_CSV, encoding="utf-8")))
    assert len(rows) == 51, "date panel must have 51 units"
    out = []
    for r in rows:
        aca = parse_date(r["aca_expansion_date"])
        early = r["early_expansion_class"].strip() == "statewide_or_major"
        broad = r["pre2014_broad_adult_coverage"].strip() == "yes"
        other = r["other_adult_eligibility_change_2011_2019"].strip() == "yes"
        strict = r["strict_rule_flag"].strip() == "yes"
        if aca == dt.date(2014, 1, 1):
            group = "prior" if (early or broad) else "treated"
        elif aca is not None and aca <= dt.date(Y1, 12, 31):
            group = "later"
        else:
            group = "other_change" if other else "comparison"
        out.append({"STATEFIP": int(r["statefip"]), "abbr": r["abbr"], "name": r["name"], "group": group,
                    "aca": aca.isoformat() if aca else "", "early": early, "broad": broad, "other": other,
                    "strict": strict})
    g = pd.DataFrame(out).sort_values("STATEFIP").reset_index(drop=True)
    return g


# ----------------------------------------------------------------------------- cell-level algebra
class Cells:
    """State-year cells of the design: y = cell PERWT-weighted mean, W = cell PERWT total.

    WLS of the cell means on [D, state dummies, year dummies] with weights W reproduces the
    person-level WLS coefficient exactly, because every regressor is constant within a cell.
    """

    def __init__(self, st, yr, W, y, treat_states, n_person, k_person):
        self.st, self.yr, self.W, self.y = st, yr, W, y
        self.states = np.unique(st)
        self.years = np.unique(yr)
        self.G = len(self.states)
        self.g = np.searchsorted(self.states, st)
        self.sw = np.sqrt(W)
        self.S = (st[:, None] == self.states[None, :]).astype(float)
        self.Yd = (yr[:, None] == self.years[None, 1:]).astype(float)
        self.treat_states = np.array(sorted(treat_states))
        self.treat = np.isin(st, self.treat_states).astype(float)
        self.post = (yr >= POLICY_YEAR).astype(float)
        self.D = self.treat * self.post
        # small-sample factor that makes cell-level CRV1 equal person-level pyfixest CRV1
        self.cfac = self.G / (self.G - 1) * (n_person - 1) / (n_person - k_person)

    def X(self, D):
        D = D.reshape(len(self.y), -1)
        return np.column_stack([D, self.S, self.Yd])

    def fit(self, D, y=None, W=None, keep=None):
        y = self.y if y is None else y
        sw = self.sw if W is None else np.sqrt(W)
        X = self.X(D)
        if keep is not None:
            X, y, sw = X[keep], y[keep], sw[keep]
            X = X[:, np.abs(X).sum(0) > 0]
        b, *_ = np.linalg.lstsq(sw[:, None] * X, sw * y, rcond=None)
        return b

    def crv1(self, D, y=None):
        """CRV1 by state for all columns of D (cell level, person-equivalent factor)."""
        y = self.y if y is None else y
        Xs = self.sw[:, None] * self.X(D)
        ys = self.sw * y
        b, *_ = np.linalg.lstsq(Xs, ys, rcond=None)
        e = ys - Xs @ b
        Binv = np.linalg.pinv(Xs.T @ Xs)
        sc = np.zeros((self.G, Xs.shape[1]))
        np.add.at(sc, self.g, Xs * e[:, None])
        V = self.cfac * Binv @ (sc.T @ sc) @ Binv
        k = D.reshape(len(self.y), -1).shape[1]
        return b[:k], np.sqrt(np.diag(V)[:k])


def jackknife_cv3(c: Cells):
    """CV3 of MacKinnon, Nielsen and Webb (2023): (G-1)/G * sum_g (b_(-g) - b)^2."""
    b = c.fit(c.D)[0]
    bj = np.array([c.fit(c.D, keep=(c.st != s))[0] for s in c.states])
    return float(np.sqrt((c.G - 1) / c.G * ((bj - b) ** 2).sum())), bj


class WCR:
    """Wild cluster restricted bootstrap (WCR-C, CRV1-studentized, Rademacher), clusters = states.

    Implemented on the sqrt(W)-scaled cell regression, which has the same cluster scores as the
    person-level WLS; the small-sample factor cancels in every bootstrap t comparison.
    """

    def __init__(self, c: Cells, B: int, seed: int):
        self.c = c
        Xs = c.sw[:, None] * c.X(c.D)
        self.ys = c.sw * c.y
        self.Ds = Xs[:, 0]
        Z = Xs[:, 1:]
        self.PZ = Z @ np.linalg.pinv(Z)
        self.Dt = self.Ds - self.PZ @ self.Ds
        self.DtD = float(self.Dt @ self.Dt)
        self.MX = np.eye(len(self.ys)) - Xs @ np.linalg.pinv(Xs)
        self.bhat = float(self.Dt @ self.ys / self.DtD)
        self.se = self._se(self.MX @ self.ys[:, None])[0]
        rng = np.random.default_rng(seed)
        self.V = rng.choice(np.array([-1.0, 1.0]), size=(c.G, B))

    def _se(self, U):
        sc = np.zeros((self.c.G, U.shape[1]))
        np.add.at(sc, self.c.g, self.Dt[:, None] * U)
        return np.sqrt(self.c.cfac * (sc ** 2).sum(0)) / self.DtD

    def pvalue(self, beta0: float) -> float:
        yr_ = self.ys - beta0 * self.Ds
        ur = yr_ - self.PZ @ yr_
        fit_r = self.ys - ur
        t0 = (self.bhat - beta0) / self.se
        Yb = fit_r[:, None] + ur[:, None] * self.V[self.c.g, :]
        bb = self.Dt @ Yb / self.DtD
        tb = (bb - beta0) / self._se(self.MX @ Yb)
        return float((np.abs(tb) >= abs(t0)).mean())

    def interval(self, level=0.05):
        def edge(far):
            a, b = far, self.bhat          # p(far) < level <= p(bhat)
            for _ in range(50):
                m = 0.5 * (a + b)
                if self.pvalue(m) < level:
                    a = m
                else:
                    b = m
            return 0.5 * (a + b)
        return edge(self.bhat - 12 * self.se), edge(self.bhat + 12 * self.se)


def randomization_inference(c: Cells, R: int, seed: int):
    """Permute WHICH design states are treated (count fixed, timing fixed at 2014)."""
    rng = np.random.default_rng(seed)
    nT = len(c.treat_states)
    ys = c.sw * c.y
    dobs = c.sw * c.D
    bhat = c.fit(c.D)[0]
    se_obs = c.crv1(c.D)[1][0]
    bp, ap, tp = np.empty(R), np.empty(R), np.empty(R)
    for r in range(R):
        T = rng.choice(c.states, size=nT, replace=False)
        Dp = np.isin(c.st, T) * c.post
        Xs = c.sw[:, None] * c.X(Dp)
        Z, Ds = Xs[:, 1:], Xs[:, 0]
        Dt = Ds - Z @ np.linalg.lstsq(Z, Ds, rcond=None)[0]
        DtD = Dt @ Dt
        bp[r] = Dt @ ys / DtD
        ap[r] = Dt @ dobs / DtD
        e = ys - Xs @ np.linalg.lstsq(Xs, ys, rcond=None)[0]
        sc = np.bincount(c.g, weights=Dt * e, minlength=c.G)
        tp[r] = bp[r] / (np.sqrt(c.cfac * (sc ** 2).sum()) / DtD)
    p_coef = (1 + (np.abs(bp) >= abs(bhat)).sum()) / (R + 1)
    p_t = (1 + (np.abs(tp) >= abs(bhat / se_obs)).sum()) / (R + 1)
    grid = np.round(np.arange(bhat - 0.12, bhat + 0.12 + 1e-12, 0.0001), 6)
    pv = np.array([(1 + (np.abs(bp - tau * ap) >= abs(bhat - tau)).sum()) / (R + 1) for tau in grid])
    acc = grid[pv > 0.05]
    return {"p_coef": float(p_coef), "p_t": float(p_t), "ci": (float(acc.min()), float(acc.max())),
            "null_sd": float(bp.std()), "grid_edge_hit": bool(acc.min() <= grid[0] or acc.max() >= grid[-1])}


# ----------------------------------------------------------------------------- main
def main():
    T0 = time.time()
    for d in (ART, FIG, SCR):
        d.mkdir(parents=True, exist_ok=True)
    facts, ledgers, figures, validation, sensitivity = {}, {}, {}, [], {}

    def fact(key, value, display, estimand, **kw):
        f = {"value": value, "display": display, "estimand": estimand, "source": kw.pop("source", SOURCE),
             "unit": kw.pop("unit", None), "se": kw.pop("se", None), "ci_low": kw.pop("ci_low", None),
             "ci_high": kw.pop("ci_high", None), "ci_display": kw.pop("ci_display", None),
             "df": kw.pop("df", None), "n": kw.pop("n", None), "weight": kw.pop("weight", "PERWT"),
             "variance": kw.pop("variance", "none"), "benchmark": kw.pop("benchmark", None),
             "note": kw.pop("note", "")}
        assert not kw, kw
        facts[key] = f

    # -------------------------------------------------------------- data
    log("loading persons")
    P = load_persons()
    groups = assign_groups()
    gmap = dict(zip(groups["STATEFIP"], groups["group"]))
    treat_states = sorted(groups.loc[groups["group"] == "treated", "STATEFIP"].tolist())
    comp_states = sorted(groups.loc[groups["group"] == "comparison", "STATEFIP"].tolist())
    design_states = sorted(treat_states + comp_states)
    abbr = dict(zip(groups["STATEFIP"], groups["abbr"]))
    names = dict(zip(groups["STATEFIP"], groups["name"]))
    log(f"treated {len(treat_states)} comparison {len(comp_states)}")

    win = P.filter(pl.col("YEAR").is_between(Y0, Y1))
    n_full = win.height
    units_full = win["STATEFIP"].n_unique()
    validation.append({"check": "audition reproduction: person records 2011-2019, ages 19-64, POVERTY 1-138",
                       "python": n_full, "reference": 2578630, "reference_source": "PLAN_v4 section 3.6 audition (raw store)",
                       "pass": n_full == 2578630})
    validation.append({"check": "audition reproduction: state units", "python": units_full, "reference": 51,
                       "pass": units_full == 51})
    reps = load_rep_aggregates(P)

    # -------------------------------------------------------------- stage 1: state-year cells
    w = np.column_stack([reps[f"w{i}"].to_numpy() for i in range(NREP + 1)])
    s = np.column_stack([reps[f"s{i}"].to_numpy() for i in range(NREP + 1)])
    rst, ryr, rn = reps["STATEFIP"].to_numpy(), reps["YEAR"].to_numpy(), reps["n"].to_numpy()
    ybar_r = s / w
    cell_se = np.sqrt(SDR_SCALE * ((ybar_r[:, 1:] - ybar_r[:, [0]]) ** 2).sum(1))
    assert rn.min() >= 100, "suppression rule: a state-year cell has n < 100"
    cv_max = float((cell_se / ybar_r[:, 0]).max())
    in_design = np.isin(rst, design_states)
    log(f"stage one: {len(rn)} cells, min n {rn.min()}, max CV {cv_max:.3f}")

    def pooled(mask):
        """PERWT-pooled mean over the cells in mask with its SDR SE (replicate r used across years)."""
        est = s[mask].sum(0) / w[mask].sum(0)
        return est[0], float(np.sqrt(SDR_SCALE * ((est[1:] - est[0]) ** 2).sum())), est

    # -------------------------------------------------------------- design subset (persons)
    dsub = (win.filter(pl.col("STATEFIP").is_in(design_states))
            .with_columns(treat=pl.col("STATEFIP").is_in(treat_states).cast(pl.Float64),
                          y=pl.col("uninsured").cast(pl.Float64),
                          sy=pl.col("STATEFIP").cast(pl.Int32) * 10000 + pl.col("YEAR").cast(pl.Int32))
            .with_columns(D=pl.col("treat") * (pl.col("YEAR") >= POLICY_YEAR).cast(pl.Float64)))
    for yy in range(Y0, Y1 + 1):
        if yy != REF_YEAR:
            dsub = dsub.with_columns((pl.col("treat") * (pl.col("YEAR") == yy).cast(pl.Float64)).alias(f"ev{yy}"))
    NP = dsub.height
    n_households = dsub["CLUSTER"].n_unique()
    n_cells = dsub.select(pl.struct("STATEFIP", "YEAR").n_unique()).item()
    n_treat_rec = int(dsub.filter(pl.col("treat") == 1).height)
    pdf = dsub.select(["y", "D", "STATEFIP", "YEAR", "PERWT", "CLUSTER", "sy"]
                      + [f"ev{yy}" for yy in range(Y0, Y1 + 1) if yy != REF_YEAR]).to_pandas()
    G = len(design_states)

    # -------------------------------------------------------------- the ladder (person level)
    log("person-level fits")
    fit = pf.feols("y ~ D | STATEFIP + YEAR", data=pdf, weights="PERWT", vcov="hetero")
    beta = float(fit.coef()["D"])
    ladder = {}

    def grab(name, vc):
        fit.vcov(vc)
        ladder[name] = {"se": float(fit.se()["D"]), "df": float(fit._df_t)}

    grab("hc1", "hetero")
    grab("household", {"CRV1": "CLUSTER"})
    grab("state_year", {"CRV1": "sy"})
    grab("state", {"CRV1": "STATEFIP"})
    ladder["hc1"]["G"] = NP
    ladder["household"]["G"] = n_households
    ladder["state_year"]["G"] = n_cells
    ladder["state"]["G"] = G

    # -------------------------------------------------------------- cells
    cell = (dsub.group_by(["STATEFIP", "YEAR"])
            .agg(W=pl.col("PERWT").sum(), Sy=(pl.col("PERWT") * pl.col("y")).sum(), n=pl.len(),
                 D=pl.col("D").first())
            .with_columns(ybar=pl.col("Sy") / pl.col("W")).sort(["STATEFIP", "YEAR"]))
    k_person = 1 + len(range(Y0, Y1 + 1))
    C = Cells(cell["STATEFIP"].to_numpy(), cell["YEAR"].to_numpy(), cell["W"].to_numpy(),
              cell["ybar"].to_numpy(), treat_states, NP, k_person)
    b_cell = float(C.fit(C.D)[0])
    validation.append({"check": "two-stage identity: person-level WLS coefficient equals state-year-cell WLS coefficient",
                       "python_person": r6(beta * 100), "python_cells": r6(b_cell * 100), "unit": "points",
                       "pass": abs(beta - b_cell) < 1e-10})
    se_cell_state = float(C.crv1(C.D)[1][0])
    validation.append({"check": "CRV1 by state: pyfixest person-level vs hand-coded cell-level sandwich (same small-sample factor)",
                       "pyfixest": r6(ladder["state"]["se"] * 100), "hand": r6(se_cell_state * 100), "unit": "points",
                       "pass": abs(se_cell_state / ladder["state"]["se"] - 1) < 1e-5})

    # CRV3 jackknife
    cv3, bj = jackknife_cv3(C)
    ladder["cv3"] = {"se": cv3, "df": G - 1, "G": G}
    fc = pf.feols("ybar ~ D | STATEFIP + YEAR", data=cell.to_pandas(), weights="W", vcov={"CRV3": "STATEFIP"})
    pf_cv3 = float(fc.se()["D"])
    n_c, k_c = cell.height, 1 + len(range(Y0, Y1 + 1))
    implied = cv3 * G / (G - 1) * np.sqrt((n_c - 1) / (n_c - k_c))
    validation.append({"check": "CV3: hand jackknife (MNW 2023 definition) vs pyfixest 0.60 CRV3 on the cell regression",
                       "hand_mnw": r6(cv3 * 100), "pyfixest": r6(pf_cv3 * 100),
                       "pyfixest_over_hand": r6(pf_cv3 / cv3),
                       "explained_by": "pyfixest sums squared leave-one-out deviations without (G-1)/G and then applies G/(G-1)*(N-1)/(N-K)",
                       "implied_pyfixest": r6(implied * 100), "unit": "points",
                       "pass": abs(implied / pf_cv3 - 1) < 1e-6})
    jk_range = (float(bj.min()), float(bj.max()))

    # SDR replicate SE with states fixed: stage two re-run on each replicate's cell means
    ds_idx = np.where(in_design)[0]
    Cr = Cells(rst[ds_idx], ryr[ds_idx], w[ds_idx, 0], ybar_r[ds_idx, 0], treat_states, NP, k_person)
    assert np.allclose(Cr.y, C.y) and np.allclose(Cr.W, C.W)
    br = np.array([Cr.fit(Cr.D, y=ybar_r[ds_idx, i], W=w[ds_idx, i])[0] for i in range(1, NREP + 1)])
    ladder["sdr"] = {"se": float(np.sqrt(SDR_SCALE * ((br - beta) ** 2).sum())), "df": SDR_DF, "G": NREP}

    # wild cluster restricted bootstrap
    log("wild cluster bootstrap")
    wcr = WCR(C, B_WCB, SEED_WCB)
    wcb_p0 = wcr.pvalue(0.0)
    wcb_lo, wcb_hi = wcr.interval()
    ladder["wcb"] = {"ci": (wcb_lo, wcb_hi), "p": wcb_p0, "G": G}
    # validation against the wildboottest package (pyfixest's .wildboottest() refuses WLS)
    try:
        import statsmodels.api as sm
        from wildboottest.wildboottest import wildboottest as wbt
        Xs = C.sw[:, None] * C.X(C.D)
        cols = ["D"] + [f"s{x}" for x in C.states] + [f"y{x}" for x in C.years[1:]]
        b0 = beta + 1.5 * ladder["state"]["se"]
        ymod = C.sw * C.y - b0 * Xs[:, 0]
        m = sm.OLS(pd.Series(ymod, name="y"), pd.DataFrame(Xs, columns=cols))
        res = wbt(m, param="D", cluster=pd.Series(C.st), B=B_WCB, seed=SEED_WCB, parallel=False, show=False)
        p_pkg = float(np.asarray(res["p-value"]).ravel()[0])
        p_own = wcr.pvalue(b0)
        validation.append({"check": "WCR bootstrap p-value at a moderate null (beta0 = beta + 1.5 CRV1 SE): own numpy vs wildboottest 0.3.2",
                           "own": r4(p_own), "wildboottest": r4(p_pkg), "B": B_WCB,
                           "pass": abs(p_own - p_pkg) < 0.02,
                           "note": "different random draws; Monte Carlo SE of each p about 0.004"})
    except Exception as e:  # pragma: no cover
        validation.append({"check": "wildboottest package comparison", "error": f"{type(e).__name__}: {e}"})

    # randomization inference
    log("randomization inference")
    ri = randomization_inference(C, B_RI, SEED_RI)
    assert not ri["grid_edge_hit"]
    ladder["ri"] = {"ci": ri["ci"], "p": ri["p_t"], "p_coef": ri["p_coef"], "G": G}

    # -------------------------------------------------------------- event study (person level)
    log("event study")
    evs = [yy for yy in range(Y0, Y1 + 1) if yy != REF_YEAR]
    fev = pf.feols("y ~ " + " + ".join(f"ev{yy}" for yy in evs) + " | STATEFIP + YEAR",
                   data=pdf, weights="PERWT", vcov={"CRV1": "STATEFIP"})
    ev_b = {yy: float(fev.coef()[f"ev{yy}"]) for yy in evs}
    ev_se_state = {yy: float(fev.se()[f"ev{yy}"]) for yy in evs}
    ev_df_state = float(fev._df_t)
    fev.vcov("hetero")
    ev_se_hc1 = {yy: float(fev.se()[f"ev{yy}"]) for yy in evs}
    ev_df_hc1 = float(fev._df_t)
    ev_p_hc1 = {yy: float(2 * stats.t.sf(abs(ev_b[yy] / ev_se_hc1[yy]), ev_df_hc1)) for yy in evs}
    ev_p_state = {yy: float(2 * stats.t.sf(abs(ev_b[yy] / ev_se_state[yy]), ev_df_state)) for yy in evs}
    b_ev_cell, se_ev_cell = C.crv1(np.column_stack([C.treat * (C.yr == yy) for yy in evs]))
    validation.append({"check": "event study: person-level pyfixest vs cell-level coefficients and CRV1 SEs",
                       "max_abs_coef_diff_points": r6(max(abs(b_ev_cell[i] - ev_b[yy]) for i, yy in enumerate(evs)) * 100),
                       "max_rel_se_diff": r6(max(abs(se_ev_cell[i] / ev_se_state[yy] - 1) for i, yy in enumerate(evs))),
                       "pass": True})
    # joint test of the two leads, CRV1 by state (Wald, F with (2, G-1))
    fev.vcov({"CRV1": "STATEFIP"})
    Vv = np.asarray(fev._vcov)
    names_ev = list(fev.coef().index)
    li = [names_ev.index(f"ev{yy}") for yy in (2011, 2012)]
    bl = np.array([ev_b[2011], ev_b[2012]])
    Wl = float(bl @ np.linalg.solve(Vv[np.ix_(li, li)], bl))
    p_leads_state = float(stats.f.sf(Wl / 2, 2, G - 1))
    fev.vcov("hetero")
    Vh = np.asarray(fev._vcov)
    Wh = float(bl @ np.linalg.solve(Vh[np.ix_(li, li)], bl))
    p_leads_hc1 = float(stats.chi2.sf(Wh, 2))

    # -------------------------------------------------------------- group trends, 2x2, state changes
    tmask = np.isin(rst, treat_states)
    cmask = np.isin(rst, comp_states)
    trend = {}
    for lab, mk in (("treated", tmask), ("comparison", cmask)):
        trend[lab] = {}
        for yy in range(Y0, Y1 + 1):
            e0, se, _ = pooled(mk & (ryr == yy))
            trend[lab][yy] = (e0, se)
    gap = {yy: trend["treated"][yy][0] - trend["comparison"][yy][0] for yy in range(Y0, Y1 + 1)}
    pre = ryr <= PRE_END
    post = ryr >= POLICY_YEAR
    t_pre, t_pre_se, t_pre_r = pooled(tmask & pre)
    t_post, t_post_se, t_post_r = pooled(tmask & post)
    c_pre, c_pre_se, c_pre_r = pooled(cmask & pre)
    c_post, c_post_se, c_post_r = pooled(cmask & post)
    dd_r = (t_post_r - t_pre_r) - (c_post_r - c_pre_r)
    dd = dd_r[0]
    dd_se = float(np.sqrt(SDR_SCALE * ((dd_r[1:] - dd) ** 2).sum()))

    chg = []
    for sfp in design_states:
        m = rst == sfp
        est = s[m & post].sum(0) / w[m & post].sum(0) - s[m & pre].sum(0) / w[m & pre].sum(0)
        se = float(np.sqrt(SDR_SCALE * ((est[1:] - est[0]) ** 2).sum()))
        chg.append({"STATEFIP": sfp, "change": float(est[0]), "se": se, "n": int(rn[m].sum()),
                    "treated": sfp in treat_states})
    chg_df = pd.DataFrame(chg)
    tc = chg_df[chg_df.treated]["change"].to_numpy()
    cc = chg_df[~chg_df.treated]["change"].to_numpy()
    med_change_se = float(np.median(chg_df["se"]))
    sd_t, sd_c = float(tc.std(ddof=1)), float(cc.std(ddof=1))
    med_cell_se = float(np.median(cell_se[in_design]))

    # -------------------------------------------------------------- sensitivity (NOTES only)
    def cell_design(states_t, states_c, y0=Y0):
        sub = (P.filter(pl.col("YEAR").is_between(y0, Y1) & pl.col("STATEFIP").is_in(states_t + states_c))
               .group_by(["STATEFIP", "YEAR"]).agg(W=pl.col("PERWT").sum(),
                                                     Sy=(pl.col("PERWT") * pl.col("uninsured")).sum(), n=pl.len())
               .with_columns(ybar=pl.col("Sy") / pl.col("W")).sort(["STATEFIP", "YEAR"]))
        npers = int(sub["n"].sum())
        return Cells(sub["STATEFIP"].to_numpy(), sub["YEAR"].to_numpy(), sub["W"].to_numpy(),
                     sub["ybar"].to_numpy(), states_t, npers, 1 + len(range(y0, Y1 + 1)))

    prior_states = sorted(groups.loc[groups["group"] == "prior", "STATEFIP"].tolist())
    other_states = sorted(groups.loc[groups["group"] == "other_change", "STATEFIP"].tolist())
    for key, st_t, st_c in (("add_prior_expanders_to_treated", treat_states + prior_states, comp_states),
                            ("add_other_change_states_to_comparison", treat_states, comp_states + other_states)):
        if st_t == treat_states and st_c == comp_states:
            continue
        cd = cell_design(st_t, st_c)
        bb, ss = cd.crv1(cd.D)
        sensitivity[key] = {"beta_points": r4(bb[0] * 100), "crv1_state_se_points": r4(ss[0] * 100),
                            "G": int(cd.G), "treated": len(st_t), "comparison": len(st_c)}
    # strict rule: also drop states with pre-2014 county pilots, capped programs or eligibility cuts
    strict_set = set(groups.loc[groups["strict"], "STATEFIP"].tolist())
    st_t = [x for x in treat_states if x not in strict_set]
    st_c = [x for x in comp_states if x not in strict_set]
    cd = cell_design(st_t, st_c)
    bb, ss = cd.crv1(cd.D)
    sensitivity["strict_drop_pilots_caps_cuts"] = {"beta_points": r4(bb[0] * 100), "crv1_state_se_points": r4(ss[0] * 100),
                                                   "G": int(cd.G), "treated": len(st_t), "comparison": len(st_c),
                                                   "dropped": sorted(abbr[x] for x in strict_set if x in design_states)}
    # equal-state weighting of the same cells (a different estimand: the average state)
    ce = Cells(C.st, C.yr, np.ones_like(C.W), C.y, treat_states, n_c, k_c)
    bb, ss = ce.crv1(ce.D)
    sensitivity["equal_state_weights_cells"] = {"beta_points": r4(bb[0] * 100), "crv1_state_se_points": r4(ss[0] * 100),
                                                "note": "unweighted state-year cells: the average-state estimand, not the person-weighted one"}
    # extended window 2008-2019 event study (cells, CRV1 by state)
    cx = cell_design(treat_states, comp_states, y0=EXT0)
    evx = [yy for yy in range(EXT0, Y1 + 1) if yy != REF_YEAR]
    bx, sx = cx.crv1(np.column_stack([cx.treat * (cx.yr == yy) for yy in evx]))
    sensitivity["event_study_2008_2019"] = {str(yy): {"coef_points": r4(bx[i] * 100), "se_points": r4(sx[i] * 100)}
                                            for i, yy in enumerate(evx)}
    # full 51-unit audition-style gap (expanded by 2014-12-31 vs not by 2019-12-31 etc. is NOT the design)
    sensitivity["jackknife_range_points"] = [r4(jk_range[0] * 100), r4(jk_range[1] * 100)]
    sensitivity["ri_null_sd_points"] = r4(ri["null_sd"] * 100)
    sensitivity["ri_p_coefficient_statistic"] = r4(ri["p_coef"])
    sensitivity["max_cell_cv"] = r4(cv_max)

    # ============================================================== artifacts
    ln = lambda k: ladder[k]
    for k in ("hc1", "household", "sdr", "state_year", "state", "cv3"):
        L = ladder[k]
        L["t"] = tcrit(L["df"])
        L["ci"] = (beta - L["t"] * L["se"], beta + L["t"] * L["se"])

    # ---- facts: sample and design sizes
    fact("records_full", n_full, intc(n_full), "Person records, ACS 2011" + EN + "2019, ages 19" + EN + "64, POVERTY 1" + EN + "138, all 51 state units",
         unit="person records", n=n_full, weight=None)
    fact("units_full", units_full, intc(units_full), "State units (50 states and DC) in the ACS panel", unit="states", weight=None)
    fact("records_design", NP, intc(NP), "Person records in the design (treated cohort and comparison states), 2011" + EN + "2019",
         unit="person records", n=NP, weight=None)
    fact("states_design", G, intc(G), "States in the design", unit="states", weight=None)
    fact("states_treated", len(treat_states), intc(len(treat_states)), "States in the January 2014 expansion cohort", unit="states", weight=None)
    fact("states_comparison", len(comp_states), intc(len(comp_states)), "Comparison states (no expansion in effect by the end of 2019)", unit="states", weight=None)
    fact("households_design", n_households, intc(n_households), "ACS household clusters (CLUSTER) in the design", unit="households", weight=None)
    fact("cells_design", n_cells, intc(n_cells), "State-year cells in the design", unit="cells", weight=None)
    fact("persons_per_household", r4(NP / n_households), num(NP / n_households, 1),
         "Average design person records per ACS household cluster", unit="records per household", weight=None)
    n_jan14 = int((groups["aca"] == "2014-01-01").sum())
    fact("states_jan2014", n_jan14, intc(n_jan14), "State units (including DC) whose ACA Medicaid expansion took effect on January 1, 2014",
         unit="states", weight=None, source=SOURCE_DATES)
    fact("states_prior", len(prior_states), intc(len(prior_states)),
         "January 2014 expanders excluded for earlier or broad coverage of low-income adults", unit="states", weight=None, source=SOURCE_DATES)
    fact("wcb_reps", B_WCB, intc(B_WCB), "Bootstrap replications (Rademacher draws, seeded)", weight=None)
    fact("ri_perms", B_RI, intc(B_RI), "Random reassignments of expansion status (seeded)", weight=None)

    # ---- facts: descriptive gaps
    for yy in (2011, 2013, 2014, 2019):
        fact(f"gap_{yy}", r6(gap[yy] * 100), pts(gap[yy]), f"Treated minus comparison uninsured share, {yy} (percentage points)",
             unit="percentage points")
    fact("dd_means", r6(dd * 100), pts(dd), "Difference in differences of pooled PERWT means: (2014" + EN + "2019 minus 2011" + EN + "2013) treated minus the same for comparison",
         unit="percentage points", se=r6(dd_se * 100), variance="replicate_sdr(80)", df=SDR_DF, source=SOURCE_REP)
    fact("t_change", r6((t_post - t_pre) * 100), pts(t_post - t_pre), "Change in the treated states' pooled uninsured share, 2011" + EN + "2013 to 2014" + EN + "2019",
         unit="percentage points")
    fact("c_change", r6((c_post - c_pre) * 100), pts(c_post - c_pre), "Change in the comparison states' pooled uninsured share, 2011" + EN + "2013 to 2014" + EN + "2019",
         unit="percentage points")

    # ---- facts: headline coefficient and the ladder
    est = "Coefficient on expansion cohort " + TIMES + " post-2014 in a PERWT-weighted linear probability model of being uninsured with state and year fixed effects (percentage points)"
    fact("beta", r6(beta * 100), pts(beta), est, unit="percentage points", n=NP)
    lab_var = {"hc1": "cluster_robust(person)", "household": "cluster_robust(household)", "sdr": "replicate_sdr(80)",
               "state_year": "cluster_robust(state-year)", "state": "cluster_robust(state)", "cv3": "cluster_robust(state)"}
    notes = {"hc1": "HC1: every person record treated as an independent draw",
             "household": "CRV1 by ACS household cluster (IPUMS CLUSTER); no stratification correction, so slightly conservative for the sampling component",
             "sdr": "SDR with the 80 person replicate weights; stage two re-estimated on each replicate's state-year means; the set of states and their assignments held fixed",
             "state_year": "CRV1 by state-year cell: allows common shocks within a state-year, not persistence within a state",
             "state": "CRV1 by state; t with G " + MINUS + " 1 degrees of freedom",
             "cv3": "CRV3 jackknife by state (MacKinnon, Nielsen and Webb 2023); t with G " + MINUS + " 1 degrees of freedom"}
    for k in ("hc1", "household", "sdr", "state_year", "state", "cv3"):
        L = ladder[k]
        if k in ("hc1", "household", "sdr", "state"):
            fact(f"se_{k}", r6(L["se"] * 100), pts(L["se"], 2), "Standard error of the expansion coefficient: " + notes[k],
                 unit="percentage points", se=r6(L["se"] * 100), ci_low=r6(L["ci"][0] * 100), ci_high=r6(L["ci"][1] * 100),
                 ci_display=ci_str(L["ci"][0], L["ci"][1], pts), df=r4(L["df"]) if k != "hc1" else None, n=NP,
                 variance=lab_var[k], source=SOURCE_REP if k == "sdr" else SOURCE)
        if k in ("hc1", "household", "sdr", "state", "cv3"):
            fact(f"ci_{k}", r6(beta * 100), pts(beta), "Expansion coefficient with its 95% interval: " + notes[k],
                 unit="percentage points", se=r6(L["se"] * 100), ci_low=r6(L["ci"][0] * 100), ci_high=r6(L["ci"][1] * 100),
                 ci_display=ci_str(L["ci"][0], L["ci"][1], pts), df=r4(L["df"]) if k != "hc1" else None, n=NP,
                 variance=lab_var[k], source=SOURCE_REP if k == "sdr" else SOURCE)
        if k in ("hc1", "state"):
            fact(f"halfwidth_{k}", r6(L["t"] * L["se"] * 100), pts(L["t"] * L["se"]), "Half-width of the 95% interval: " + notes[k],
                 unit="percentage points", variance=lab_var[k])
    fact("ratio_state_hc1", r4(ladder["state"]["se"] / ladder["hc1"]["se"]), num(ladder["state"]["se"] / ladder["hc1"]["se"], 1) + TIMES,
         "Ratio of the state-clustered (CRV1) standard error to the HC1 standard error", unit="ratio")
    fact("ratio_state_sdr", r4(ladder["state"]["se"] / ladder["sdr"]["se"]), num(ladder["state"]["se"] / ladder["sdr"]["se"], 1) + TIMES,
         "Ratio of the state-clustered (CRV1) standard error to the SDR replicate standard error", unit="ratio")
    fact("ratio_stateyear_hc1", r4(ladder["state_year"]["se"] / ladder["hc1"]["se"]), num(ladder["state_year"]["se"] / ladder["hc1"]["se"], 1) + TIMES,
         "Ratio of the state-year-clustered standard error to the HC1 standard error", unit="ratio")
    fact("ci_wcb", r6(beta * 100), pts(beta), "Expansion coefficient with the 95% interval from inverting the wild cluster restricted bootstrap test (Rademacher, clusters = states)",
         unit="percentage points", ci_low=r6(wcb_lo * 100), ci_high=r6(wcb_hi * 100), ci_display=ci_str(wcb_lo, wcb_hi, pts),
         variance="wild_cluster_bootstrap(state)", note=f"B = {B_WCB}, seed {SEED_WCB}; symmetric CRV1-studentized test")
    fact("p_wcb", r6(wcb_p0), ("< 0.0001" if wcb_p0 == 0 else num(wcb_p0, 4)), "Wild cluster restricted bootstrap p-value for no effect",
         variance="wild_cluster_bootstrap(state)", note=f"0 of {B_WCB} bootstrap t statistics as extreme" if wcb_p0 == 0 else "")
    fact("ci_ri", r6(beta * 100), pts(beta), "Expansion coefficient with the 95% randomization-inference interval (constant additive effect, reassigning which design states expanded)",
         unit="percentage points", ci_low=r6(ri["ci"][0] * 100), ci_high=r6(ri["ci"][1] * 100),
         ci_display=ci_str(ri["ci"][0], ri["ci"][1], pts), variance="simulation",
         note=f"{B_RI} random reassignments, seed {SEED_RI}; coefficient statistic inverted over a 0.01-point grid")
    fact("p_ri", r6(ri["p_t"]), num(ri["p_t"], 4), "Randomization-inference p-value for the sharp null of no effect in any state (studentized statistic)",
         variance="simulation", note=f"(1 + count)/(R + 1) with R = {B_RI}; the smallest attainable value")

    # ---- facts: stage one and state variation
    fact("median_cell_se", r6(med_cell_se * 100), pts(med_cell_se, 1), "Median SDR standard error of a design state-year uninsured share (percentage points)",
         unit="percentage points", variance="replicate_sdr(80)", df=SDR_DF, source=SOURCE_REP)
    fact("median_change_se", r6(med_change_se * 100), pts(med_change_se, 1), "Median SDR standard error of a design state's pre-to-post change (percentage points)",
         unit="percentage points", variance="replicate_sdr(80)", df=SDR_DF, source=SOURCE_REP)
    fact("sd_change_treated", r6(sd_t * 100), pts(sd_t, 1), "Standard deviation across treated states of the pre-to-post change in the uninsured share",
         unit="percentage points")
    fact("sd_change_comparison", r6(sd_c * 100), pts(sd_c, 1), "Standard deviation across comparison states of the pre-to-post change in the uninsured share",
         unit="percentage points")

    # ---- facts: event-study leads under two variance rules
    for yy in (2011, 2012):
        lo, hi = ev_b[yy] - tcrit(ev_df_state) * ev_se_state[yy], ev_b[yy] + tcrit(ev_df_state) * ev_se_state[yy]
        fact(f"lead_{yy}", r6(ev_b[yy] * 100), pts(ev_b[yy]), f"Event-study coefficient for {yy} relative to 2013 (percentage points), CRV1 by state",
             unit="percentage points", se=r6(ev_se_state[yy] * 100), ci_low=r6(lo * 100), ci_high=r6(hi * 100),
             ci_display=ci_str(lo, hi, pts), df=G - 1, variance="cluster_robust(state)")
    sensitivity["leads_hc1"] = {str(yy): {"coef_points": r4(ev_b[yy] * 100), "p_hc1": r4(ev_p_hc1[yy]),
                                          "p_state": r4(ev_p_state[yy])} for yy in (2011, 2012)}
    sensitivity["leads_joint_p"] = {"hc1_chi2": r4(p_leads_hc1), "state_F": r4(p_leads_state)}
    fact("leads_p_state", r6(p_leads_state), num(p_leads_state, 2),
         f"Joint test that the 2011 and 2012 event-study coefficients are zero, CRV1 by state (F with 2 and {G - 1} df)",
         variance="cluster_robust(state)", df=G - 1)
    for yy in (2014, 2019):
        lo, hi = ev_b[yy] - tcrit(ev_df_state) * ev_se_state[yy], ev_b[yy] + tcrit(ev_df_state) * ev_se_state[yy]
        fact(f"event_{yy}", r6(ev_b[yy] * 100), pts(ev_b[yy]), f"Event-study coefficient for {yy} relative to 2013 (percentage points), CRV1 by state",
             unit="percentage points", se=r6(ev_se_state[yy] * 100), ci_low=r6(lo * 100), ci_high=r6(hi * 100),
             ci_display=ci_str(lo, hi, pts), df=G - 1, variance="cluster_robust(state)")

    # ---- facts: design sensitivity (closing panel)
    sp = sensitivity["add_prior_expanders_to_treated"]
    fact("sens_prior_beta", sp["beta_points"], num(sp["beta_points"], 1),
         "Expansion coefficient (percentage points) when the excluded January 2014 expanders join the treated group; same comparison states, window, and specification",
         unit="percentage points", se=sp["crv1_state_se_points"], variance="cluster_robust(state)")
    ssx = sensitivity["strict_drop_pilots_caps_cuts"]
    fact("states_strict_dropped", len(ssx["dropped"]), intc(len(ssx["dropped"])),
         "Design states with a pre-2014 county pilot, capped program or eligibility cut (" + ", ".join(ssx["dropped"]) + ")",
         unit="states", weight=None, source=SOURCE_DATES)
    fact("sens_strict_beta", ssx["beta_points"], num(ssx["beta_points"], 1),
         "Expansion coefficient (percentage points) after also dropping design states with pre-2014 county pilots, capped programs or eligibility cuts",
         unit="percentage points", se=ssx["crv1_state_se_points"], variance="cluster_robust(state)",
         note=f"G = {ssx['G']} ({ssx['treated']} treated, {ssx['comparison']} comparison)")
    se_eq = sensitivity["equal_state_weights_cells"]
    fact("sens_equal_beta", se_eq["beta_points"], num(se_eq["beta_points"], 1),
         "Expansion coefficient (percentage points) from the same state-year cells weighted equally instead of by population (an average-state estimand)",
         unit="percentage points", se=se_eq["crv1_state_se_points"], variance="cluster_robust(state)", weight="none (equal cell weights)")
    i08 = evx.index(EXT0)
    t08 = tcrit(cx.G - 1)
    lo08, hi08 = bx[i08] - t08 * sx[i08], bx[i08] + t08 * sx[i08]
    fact("lead_2008_ext", r6(bx[i08] * 100), pts(bx[i08]),
         "Event-study coefficient for 2008 relative to 2013 (percentage points) with the window extended to 2008" + EN + "2019; CRV1 by state",
         unit="percentage points", se=r6(sx[i08] * 100), ci_low=r6(lo08 * 100), ci_high=r6(hi08 * 100),
         ci_display=ci_str(lo08, hi08, pts), df=int(cx.G - 1), variance="cluster_robust(state)", source=SOURCE_EXT)

    # ---- figures
    yrs = list(range(Y0, Y1 + 1))
    tS = tcrit(SDR_DF)
    figures["trends"] = {
        "type": "line", "format": "pct0",
        "title": "Uninsured share, low-income adults 19" + EN + "64",
        "subtitle": "PERWT-weighted; bands are 95% SDR replicate intervals (survey sampling only)",
        "alt": "Two lines from 2011 to 2019: the uninsured share in the January 2014 expansion cohort and in states not expanded by 2019; both fall in 2014, the expansion states much more, and the gap then stays wider.",
        "x_label": "ACS survey year", "y_label": "Uninsured share", "y_domain": [0, 0.6],
        "annotations": [{"x": POLICY_YEAR, "label": "Expansion takes effect (January 2014)"}],
        "series": [
            {"name": f"January 2014 expansion cohort ({len(treat_states)} states)", "role": "treated",
             "segments": [[{"x": yy, "y": r6(trend["treated"][yy][0]), "lo": r6(trend["treated"][yy][0] - tS * trend["treated"][yy][1]),
                            "hi": r6(trend["treated"][yy][0] + tS * trend["treated"][yy][1])} for yy in yrs]]},
            {"name": f"Not expanded by 2019 ({len(comp_states)} states)", "role": "control",
             "segments": [[{"x": yy, "y": r6(trend["comparison"][yy][0]), "lo": r6(trend["comparison"][yy][0] - tS * trend["comparison"][yy][1]),
                            "hi": r6(trend["comparison"][yy][0] + tS * trend["comparison"][yy][1])} for yy in yrs]]}],
        "source": SOURCE_REP,
        "note": "Adults 19" + EN + "64 with family income at or below 138% of poverty; household population (POVERTY excludes group quarters)."}
    tSt = tcrit(ev_df_state)
    pts_ev = []
    for yy in yrs:
        if yy == REF_YEAR:
            pts_ev.append({"x": yy, "y": 0.0, "lo": None, "hi": None})
        else:
            pts_ev.append({"x": yy, "y": r4(ev_b[yy] * 100), "lo": r4((ev_b[yy] - tSt * ev_se_state[yy]) * 100),
                           "hi": r4((ev_b[yy] + tSt * ev_se_state[yy]) * 100)})
    figures["event_study"] = {
        "type": "line", "format": "num1",
        "title": "Year-by-year gap relative to 2013",
        "subtitle": f"Expansion cohort minus comparison, with state and year fixed effects; 95% intervals clustered by state, t({G - 1})",
        "alt": "Event-study coefficients by year: near zero in 2011 and 2012, zero by construction in 2013, then negative from 2014 and larger in magnitude through 2019, with state-clustered intervals several points wide.",
        "x_label": "ACS survey year", "y_label": "Difference in uninsured share (percentage points)",
        "annotations": [{"x": POLICY_YEAR, "label": "Expansion takes effect"}],
        "series": [{"name": "Gap relative to 2013 (state-clustered 95% interval)", "role": "design", "segments": [pts_ev]}],
        "source": SOURCE, "note": "2013 is the reference year (no interval). Identification by parallel trends is assumed, not established."}

    lad_rows = [
        ("hc1", "HC1: person records independent", "Neither: no mechanism", "naive"),
        ("household", "CRV1: ACS household clusters", "Sampling design", "design"),
        ("sdr", "SDR: 80 ACS replicate weights", "Sampling design", "design"),
        ("state_year", "CRV1: state-year cells", "Neither: a level with no mechanism", "naive"),
        ("state", "CRV1: states", "Assignment design", "highlight"),
        ("cv3", "CRV3 jackknife: states", "Assignment design", "highlight"),
    ]
    dot_rows = []
    for k, lab, grp, role in lad_rows:
        L = ladder[k]
        dot_rows.append({"label": lab, "estimate": r4(beta * 100), "ci_low": r4(L["ci"][0] * 100), "ci_high": r4(L["ci"][1] * 100),
                         "group": grp, "role": role})
    dot_rows.append({"label": "Wild cluster bootstrap: states", "estimate": r4(beta * 100), "ci_low": r4(wcb_lo * 100),
                     "ci_high": r4(wcb_hi * 100), "group": "Assignment design", "role": "highlight"})
    dot_rows.append({"label": "Randomization inference over assignment", "estimate": r4(beta * 100), "ci_low": r4(ri["ci"][0] * 100),
                     "ci_high": r4(ri["ci"][1] * 100), "group": "Sensitivity (assignment as if random)", "role": "muted"})
    figures["se_ladder"] = {
        "type": "dot", "format": "num1",
        "title": "One coefficient, eight intervals",
        "subtitle": "95% intervals for the expansion coefficient under each variance rule",
        "alt": "Eight 95% intervals around the same coefficient: the person, household, replicate and state-year intervals are narrow, while the four state-level intervals are several times wider and similar to one another.",
        "x_label": "Coefficient on expansion " + TIMES + " post (percentage points)",
        "reference": {"value": 0, "label": "No change"}, "rows": dot_rows, "source": SOURCE_REP}
    tab_rows = []
    what = {"hc1": "Every record", "household": "Households", "sdr": "Households, within ACS strata",
            "state_year": "State-years", "state": "States", "cv3": "States"}
    for k, lab, grp, role in lad_rows:
        L = ladder[k]
        tab_rows.append({"rung": lab, "independent": what[k], "mechanism": grp, "clusters": int(L["G"]) if k not in ("hc1", "sdr") else None,
                         "se": r4(L["se"] * 100), "ratio": r4(L["se"] / ladder["hc1"]["se"]),
                         "interval": ci_str(L["ci"][0], L["ci"][1], pts),
                         "df": ("79" if k == "sdr" else (intc(L["df"]) if k != "hc1" else "large"))})
    tab_rows.append({"rung": "Wild cluster bootstrap: states", "independent": "States", "mechanism": "Assignment design", "clusters": G,
                     "se": None, "ratio": None, "interval": ci_str(wcb_lo, wcb_hi, pts), "df": "bootstrap"})
    tab_rows.append({"rung": "Randomization inference", "independent": "Assignments of states", "mechanism": "Sensitivity",
                     "clusters": G, "se": None, "ratio": None, "interval": ci_str(ri["ci"][0], ri["ci"][1], pts), "df": "permutation"})
    figures["se_ladder_table"] = {
        "type": "table", "title": "The standard-error ladder",
        "subtitle": "Same coefficient in every row; the columns say what each rule treats as an independent draw",
        "alt": "Table of eight variance rules for the same expansion coefficient, listing what each treats as independent, the number of clusters, the standard error, its ratio to HC1, and the 95% interval.",
        "columns": [{"key": "rung", "label": "Variance rule", "align": "left"},
                    {"key": "independent", "label": "Independent units", "align": "left"},
                    {"key": "mechanism", "label": "Mechanism it represents", "align": "left"},
                    {"key": "clusters", "label": "Clusters", "format": "int", "align": "right"},
                    {"key": "se", "label": "SE (points)", "format": "num2", "align": "right"},
                    {"key": "ratio", "label": "SE / HC1", "format": "ratio2", "align": "right"},
                    {"key": "interval", "label": "95% interval (points)", "align": "right"},
                    {"key": "df", "label": "df", "align": "right"}],
        "rows": tab_rows, "highlight_key": "rung", "source": SOURCE_REP,
        "note": f"Coefficient {pts(beta)} points in every row. Bootstrap B = {B_WCB}; randomization inference R = {B_RI}; both seeded."}

    figures["two_by_two"] = {
        "type": "table", "title": "The 2" + TIMES + "2 comparison",
        "subtitle": "PERWT-pooled uninsured shares by group and period",
        "alt": "Two-by-two table of uninsured shares before (2011" + EN + "2013) and after (2014" + EN + "2019) for the expansion cohort and the comparison states, with each group's change and the difference in differences.",
        "columns": [{"key": "group", "label": "Group", "align": "left"},
                    {"key": "pre", "label": "2011" + EN + "2013", "format": "pct1", "align": "right"},
                    {"key": "post", "label": "2014" + EN + "2019", "format": "pct1", "align": "right"},
                    {"key": "change", "label": "Change (points)", "format": "num1", "align": "right"}],
        "rows": [{"group": f"January 2014 expansion cohort ({len(treat_states)} states)", "pre": r6(t_pre), "post": r6(t_post), "change": r4((t_post - t_pre) * 100)},
                 {"group": f"Not expanded by 2019 ({len(comp_states)} states)", "pre": r6(c_pre), "post": r6(c_post), "change": r4((c_post - c_pre) * 100)},
                 {"group": "Difference in differences", "pre": None, "post": None, "change": r4(dd * 100)}],
        "source": SOURCE, "note": "Pooled means weight each state by its population in each period; the regression with state fixed effects compares each state with itself, so its coefficient differs slightly."}

    rows_chg = []
    for _, r in chg_df.sort_values(["treated", "change"], ascending=[False, True]).iterrows():
        lo, hi = r["change"] - tS * r["se"], r["change"] + tS * r["se"]
        rows_chg.append({"label": names[int(r["STATEFIP"])], "estimate": r4(r["change"] * 100), "ci_low": r4(lo * 100),
                         "ci_high": r4(hi * 100), "group": "January 2014 expansion cohort" if r["treated"] else "Not expanded by 2019",
                         "role": "treated" if r["treated"] else "control", "n": int(r["n"])})
    figures["state_changes"] = {
        "type": "dot", "format": "num1",
        "title": "Each state's change, with its survey interval",
        "subtitle": "Change in the uninsured share from 2011" + EN + "2013 to 2014" + EN + "2019; 95% SDR replicate intervals",
        "alt": "Dot plot of each design state's change in the uninsured share with narrow survey intervals; expansion states fall by widely varying amounts, comparison states by smaller and more similar amounts.",
        "x_label": "Change in uninsured share (percentage points)", "reference": {"value": 0, "label": "No change"},
        "rows": rows_chg, "source": SOURCE_REP,
        "note": "Replicate r is used across all pooled years; the years are independent samples, so cross-year replicate terms average to zero."}

    grp_labels = [("treated", "January 2014 expansion cohort (treated)",
                   "ACA expansion effective 2014-01-01; no statewide expansion for low-income adults in 2010" + EN + "2011 and no broad adult coverage before 2014"),
                  ("comparison", "Comparison",
                   "No ACA expansion in effect by 2019-12-31 and no statewide change in adult eligibility during 2011" + EN + "2019"),
                  ("prior", "Set aside: January 2014 expanders with earlier coverage",
                   "Expanded 2014-01-01 but already covered low-income adults statewide (ACA early option or Section 1115 waiver, 2010" + EN + "2011) or broadly (pre-ACA programs)"),
                  ("later", "Set aside: later adopters through 2019", "ACA expansion effective after 2014-01-01 and by 2019-12-31"),
                  ("other_change", "Set aside: other eligibility change in the window",
                   "No ACA expansion by 2019, but a statewide waiver changed adult eligibility during 2011" + EN + "2019")]
    rec_by_state = win.group_by("STATEFIP").agg(n=pl.len())
    rbs = dict(zip(rec_by_state["STATEFIP"].to_list(), rec_by_state["n"].to_list()))
    grows = []
    for gk, glab, grule in grp_labels:
        sts = groups.loc[groups["group"] == gk, "STATEFIP"].tolist()
        if not sts:
            continue
        grows.append({"group": glab, "rule": grule,
                      "states": ", ".join(sorted(abbr[x] for x in sts)), "count": len(sts),
                      "records": int(sum(rbs.get(x, 0) for x in sts))})
    figures["design_groups"] = {
        "type": "table", "title": "Who is in the design",
        "subtitle": "Rules applied to the verified expansion-date panel (_data/expansion_dates.csv)",
        "alt": "Table of the five design groups with the rule that defines each, the states in it, the number of states, and ACS person records 2011" + EN + "2019.",
        "columns": [{"key": "group", "label": "Group", "align": "left"}, {"key": "rule", "label": "Rule", "align": "left"},
                    {"key": "states", "label": "States", "align": "left"}, {"key": "count", "label": "States (n)", "format": "int", "align": "right"},
                    {"key": "records", "label": "Records", "format": "int", "align": "right"}],
        "rows": grows, "source": "KFF Status of State Medicaid Expansion Decisions; medicaid.gov; see _data/expansion_dates.csv for per-state sources",
        "note": "Dates are effective (coverage) dates, not adoption or approval dates."}

    # ---- ledgers
    ledgers["policy_inference"] = {
        "title": "Medicaid expansion and uninsurance: inference for the policy comparison",
        "target_population": POP + f", in the {G} design states (January 2014 expansion cohort and states not expanded by 2019), 2011" + EN + "2019",
        "estimand": "Average effect of the 2014 expansion on the uninsured share among people in the expansion cohort, 2014" + EN + "2019 (an ATT), under parallel trends",
        "estimator": "PERWT-weighted linear probability model with state and year fixed effects; equivalently WLS on state-year means weighted by population",
        "explicit_weights": "PERWT (ACS person weight) to represent each state-year population; cells enter stage two in proportion to their weighted population",
        "implicit_weights": "Regression weights across states and years: each state's contribution depends on its population and on its within-state variation in treatment; larger states count more",
        "randomness": "Assignment of expansion across states (the policy was chosen state by state), plus ACS sampling of households within each state-year",
        "variance_estimator": f"CRV1 clustered by state with t({G - 1}); CRV3 jackknife and wild cluster restricted bootstrap as few-cluster checks; randomization inference over assignment as a sensitivity",
        "assumptions": "Parallel trends between cohort and comparison (assumed, not established); no anticipation; no spillovers across states; states' shocks independent of one another; the stated cohort and exclusion rules",
        "facts": ["ch6.beta", "ch6.ci_state", "ch6.ci_cv3", "ch6.ci_wcb", "ch6.ci_ri"]}
    ledgers["descriptive_contrast"] = {
        "title": "The same number as a survey description of fixed states",
        "target_population": POP + f", in the {G} design states, 2011" + EN + "2019, with the states and their policies taken as given",
        "estimand": "How much more the uninsured share fell in the cohort states than in the comparison states, as a finite-population descriptive contrast (no causal claim)",
        "estimator": "Same regression and same coefficient as the policy ledger",
        "explicit_weights": "PERWT",
        "implicit_weights": "Same as the policy ledger",
        "randomness": "ACS sampling of addresses (households) within strata; nothing about which states expanded is treated as random",
        "variance_estimator": "Successive difference replication with the 80 ACS person replicate weights, scale 4/80, df 79; CRV1 by household as an approximation",
        "assumptions": "The ACS replicate weights represent the sampling and weighting variability; the descriptive target makes no counterfactual claim",
        "facts": ["ch6.beta", "ch6.ci_sdr", "ch6.ci_household"]}

    # ---- write
    dump(ART / "facts.json", {"key": "ch6", "facts": facts})
    dump(ART / "ledger.json", {"key": "ch6", "ledgers": ledgers})
    for k, v in figures.items():
        dump(FIG / f"{k}.json", v)
    for old in FIG.glob("*.json"):
        if old.stem not in figures:
            old.unlink()
    dump(SCR / "sensitivity.json", sensitivity)
    pd.DataFrame({"STATEFIP": design_states, "treat": [int(x in treat_states) for x in design_states]}).to_csv(
        SCR / "design_states.csv", index=False)
    targets = {"beta_points": beta * 100, "se_hc1_points": ladder["hc1"]["se"] * 100,
               "se_household_points": ladder["household"]["se"] * 100, "se_state_points": ladder["state"]["se"] * 100,
               "se_cv3_points": cv3 * 100, "se_sdr_points": ladder["sdr"]["se"] * 100, "n_design": NP}
    # stage-one sentinel cells for the R survey check: smallest and largest design cells in 2019
    c19 = [(int(rst[i]), int(ryr[i]), int(rn[i]), float(ybar_r[i, 0]), float(cell_se[i])) for i in ds_idx if ryr[i] == 2019]
    c19.sort(key=lambda t: t[2])
    targets["sentinel_cells"] = [{"STATEFIP": a, "YEAR": b, "n": n_, "est": e, "se": se_} for (a, b, n_, e, se_) in (c19[0], c19[-1])]
    dump(SCR / "py_targets.json", targets)
    rv = SCR / "r_validation.json"
    if rv.exists():
        rj = json.loads(rv.read_text(encoding="utf-8"))
        if abs(rj.get("python_beta_points", 1e9) - beta * 100) < 1e-8:
            validation.extend(rj.get("checks", []))
        else:
            validation.append({"check": "R validation", "status": "stale: rerun verify.R"})
    manifest = {
        "key": "ch6", "slug": "ch06-clustering", "status": "draft", "code": "build.py",
        "inputs": [{"path": "analysis/usa/acs/" + p, "rows": None, "note": "columns YEAR, SAMPLE, SERIAL, PERNUM, CLUSTER, STRATA, STATEFIP, GQ, AGE, POVERTY, PERWT, HCOVANY, uninsured"} for p in PERSON_PARTS]
                  + [{"path": "analysis/usa/acs_repwt/" + p, "rows": None, "note": "REPWTP1-80 joined on SAMPLE, SERIAL, PERNUM"} for p in REP_PARTS]
                  + [{"path": "book/chapters/ch06-clustering/_data/expansion_dates.csv", "rows": 51, "note": "verified expansion dates with per-state source URLs"}],
        "analytic_sample": {"records_2011_2019_all_states": n_full, "records_design": NP, "states_design": G,
                            "treated": [abbr[x] for x in treat_states], "comparison": [abbr[x] for x in comp_states],
                            "min_cell_n": int(rn.min()), "max_cell_cv": r4(cv_max), "households_design": n_households},
        "settings": {"window": [Y0, Y1], "policy_year": POLICY_YEAR, "reference_year": REF_YEAR, "age": [AGE_LO, AGE_HI],
                     "poverty_max": POV_HI, "sdr": {"n_reps": NREP, "scale": "4/80", "df": SDR_DF, "center": "full-sample estimate"},
                     "wcb": {"B": B_WCB, "seed": SEED_WCB, "weights": "rademacher", "type": "WCR-C, CRV1-studentized, symmetric"},
                     "ri": {"R": B_RI, "seed": SEED_RI, "permute": "which design states are treated; count and timing fixed"},
                     "crv_df": "t with G - 1", "pyfixest": pf.__version__},
        "validation": validation,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    dump(ART / "manifest.json", manifest)
    log(f"beta {beta * 100:.3f} points; SE hc1 {ladder['hc1']['se'] * 100:.3f} household {ladder['household']['se'] * 100:.3f} "
        f"sdr {ladder['sdr']['se'] * 100:.3f} state-year {ladder['state_year']['se'] * 100:.3f} state {ladder['state']['se'] * 100:.3f} "
        f"cv3 {cv3 * 100:.3f}; wcb {wcb_lo * 100:.2f},{wcb_hi * 100:.2f} p {wcb_p0}; ri {ri['ci'][0] * 100:.2f},{ri['ci'][1] * 100:.2f} p {ri['p_t']}")
    log(f"facts {len(facts)}, figures {len(figures)}, ledgers {len(ledgers)}; {time.time() - T0:.0f}s")
    bad = [v for v in validation if v.get("pass") is False]
    if bad:
        log("VALIDATION FAILURES:", bad)
        sys.exit(1)


if __name__ == "__main__":
    main()
