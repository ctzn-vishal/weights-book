"""wfhlib -- shared pipeline for Chapters 4 and 5 (ACS 2024 work-from-home wage contrast).

Frozen analytic sample (reproduces the v4 audition exactly; see NOTES.md):
  ACS 2024 1-year (SAMPLE 202401), analysis layer (read-only),
  CLASSWKR == 2 ("Works for wages"), AGE 25-64,
  UHRSWORK >= 30 (usually worked 30+ hours a week in the past 12 months),
  WKSWORK2 in {4, 5, 6} (worked 40-47, 48-49 or 50-52 weeks),
  INCWAGE > 0,
  TRANWORK != 0 (a means of transportation is recorded, i.e. at work in the reference week).
Treatment  D = 1[TRANWORK == 80]  ("Worked at home"; label verified in acs.dictionary.json).
Outcome    y = log(INCWAGE / (UHRSWORK * weeks midpoint)), midpoints 43.5 / 48.5 / 51.
Controls   z = (AGE - 45, (AGE - 45)^2, female) plus education (educ4) or finer cells.

Variance: ACS successive difference replication, Var = (4/80) * sum_r (theta_r - theta)^2,
df = 79 (analysis/usa/metadata/acs.design.json). Every replicate estimate is a full re-solve of
the estimator with REPWTP<r> in place of PERWT.
"""
from __future__ import annotations

import json
import math

import duckdb
import numpy as np
import polars as pl
import scipy.linalg as sla
import scipy.sparse as sp
from scipy import stats

BOX = "C:/Users/Vishal Singh/Box/ipums"
ACS_PATH = f"{BOX}/analysis/usa/acs/part_2020_2024.parquet"
REP_PATH = f"{BOX}/analysis/usa/acs_repwt/part_2020_2024.parquet"
DICT_PATH = f"{BOX}/analysis/usa/metadata/acs.dictionary.json"
DESIGN_PATH = f"{BOX}/analysis/usa/metadata/acs.design.json"

SAMPLE_ID = 202401
N_REPS = 80
SDR_SCALE = 4.0 / N_REPS
DF_SDR = N_REPS - 1
T_SDR = float(stats.t.ppf(0.975, DF_SDR))
Z975 = float(stats.norm.ppf(0.975))
WEEKS_MID = {4: 43.5, 5: 48.5, 6: 51.0}
EDUC4_LEVELS = ["Less than HS", "HS", "Some college", "BA+"]
EDUC4_SHORT = {"Less than HS": "less than HS", "HS": "HS", "Some college": "some college", "BA+": "BA+"}

# 2018 Census occupation codes (ACS 2018+) -> 2018 SOC major groups. Ranges from the Census
# Bureau's 2018 occupation code list; documented in NOTES.md. Every OCC in the sample maps.
OCC_GROUPS = [
    (10, 440, "Management", "11"),
    (500, 960, "Business & financial", "13"),
    (1005, 1240, "Computer & math", "15"),
    (1305, 1560, "Architecture & engineering", "17"),
    (1600, 1980, "Life, physical & social science", "19"),
    (2001, 2060, "Community & social service", "21"),
    (2100, 2180, "Legal", "23"),
    (2205, 2555, "Education & library", "25"),
    (2600, 2920, "Arts, design, media & sports", "27"),
    (3000, 3550, "Healthcare practitioners", "29"),
    (3601, 3655, "Healthcare support", "31"),
    (3700, 3960, "Protective service", "33"),
    (4000, 4160, "Food preparation & serving", "35"),
    (4200, 4255, "Building & grounds", "37"),
    (4330, 4655, "Personal care & service", "39"),
    (4700, 4965, "Sales", "41"),
    (5000, 5940, "Office & admin support", "43"),
    (6005, 6130, "Farming, fishing & forestry", "45"),
    (6200, 6950, "Construction & extraction", "47"),
    (7000, 7640, "Installation & repair", "49"),
    (7700, 8990, "Production", "51"),
    (9005, 9760, "Transportation & moving", "53"),
    (9800, 9830, "Military specific", "55"),
]


# ----------------------------------------------------------------------------- formatting
def fnum(x: float, d: int = 3, sign: bool = False) -> str:
    s = f"{x:+.{d}f}" if sign else f"{x:.{d}f}"
    return s.replace("-", "\u2212")  # typographic minus


def fpct(p: float, d: int = 1) -> str:
    return fnum(100.0 * p, d) + "%"


def fint(n: float) -> str:
    return f"{int(round(n)):,}"


def fusd(x: float, d: int = 2) -> str:
    return ("\u2212$" if x < 0 else "$") + f"{abs(x):,.{d}f}"


def fci(lo: float, hi: float, kind: str = "num", d: int = 3) -> str:
    f = {"num": lambda v: fnum(v, d), "pct": lambda v: fpct(v, d), "usd": lambda v: fusd(v, d)}[kind]
    return f"{f(lo)}\u2013{f(hi)}"


def fp(p: float) -> str:
    return "< 0.001" if p < 0.001 else fnum(p, 3)


def clean(obj, sig: int = 8):
    """Round floats to `sig` significant digits so reruns are byte-identical."""
    if isinstance(obj, float):
        if not math.isfinite(obj):
            return None
        if obj == 0.0:
            return 0.0
        return float(f"{obj:.{sig}g}")
    if isinstance(obj, (np.floating,)):
        return clean(float(obj), sig)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, dict):
        return {k: clean(v, sig) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v, sig) for v in obj]
    return obj


def dump(obj, path: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(clean(obj), f, sort_keys=True, indent=2, ensure_ascii=False)
        f.write("\n")


# ----------------------------------------------------------------------------- data
def duck() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET threads=8")
    con.execute("SET memory_limit='4GB'")
    return con


SAMPLE_WHERE = ("SAMPLE = {s} AND CLASSWKR = 2 AND AGE BETWEEN 25 AND 64 AND UHRSWORK >= 30 "
                "AND WKSWORK2 IN (4, 5, 6) AND INCWAGE > 0 AND TRANWORK <> 0")


def sample_flow(con) -> dict:
    """Record counts at each sample restriction (one scan of the 2024 rows)."""
    q = f"""
    SELECT COUNT(*) AS persons_2024,
      SUM(CASE WHEN CLASSWKR = 2 AND AGE BETWEEN 25 AND 64 THEN 1 ELSE 0 END) AS wage_25_64,
      SUM(CASE WHEN CLASSWKR = 2 AND AGE BETWEEN 25 AND 64 AND UHRSWORK >= 30 THEN 1 ELSE 0 END) AS hours_30,
      SUM(CASE WHEN CLASSWKR = 2 AND AGE BETWEEN 25 AND 64 AND UHRSWORK >= 30 AND WKSWORK2 IN (4,5,6)
          THEN 1 ELSE 0 END) AS weeks_40,
      SUM(CASE WHEN CLASSWKR = 2 AND AGE BETWEEN 25 AND 64 AND UHRSWORK >= 30 AND WKSWORK2 IN (4,5,6)
          AND INCWAGE > 0 THEN 1 ELSE 0 END) AS wage_pos,
      SUM(CASE WHEN CLASSWKR = 2 AND AGE BETWEEN 25 AND 64 AND UHRSWORK >= 30 AND WKSWORK2 IN (4,5,6)
          AND INCWAGE > 0 AND TRANWORK <> 0 THEN 1 ELSE 0 END) AS at_work
    FROM read_parquet('{ACS_PATH}') WHERE SAMPLE = {SAMPLE_ID}"""
    row = con.execute(q).fetchone()
    names = ["persons_2024", "wage_25_64", "hours_30", "weeks_40", "wage_pos", "at_work"]
    return {k: int(v) for k, v in zip(names, row)}


def state_labels() -> dict[int, str]:
    d = json.load(open(DICT_PATH, encoding="utf-8"))["variables"]
    lab = d["STATEFIP"]["codes"]
    tran = d["TRANWORK"]["codes"]
    assert tran["80"] == "Worked at home", tran["80"]
    assert d["CLASSWKR"]["codes"]["2"] == "Works for wages"
    assert d["WKSWORK2"]["codes"]["4"] == "40-47 weeks" and d["WKSWORK2"]["codes"]["6"] == "50-52 weeks"
    return {int(k): v for k, v in lab.items()}


def occ_group_index(occ: np.ndarray) -> np.ndarray:
    out = np.full(occ.shape, -1, dtype=np.int64)
    for j, (lo, hi, _, _) in enumerate(OCC_GROUPS):
        out[(occ >= lo) & (occ <= hi)] = j
    if (out < 0).any():
        bad = np.unique(occ[out < 0])
        raise ValueError(f"unmapped OCC codes: {bad[:20]}")
    return out


def load_sample(con) -> pl.DataFrame:
    q = f"""SELECT SERIAL, PERNUM, PERWT, STATEFIP, AGE, female, EDUC, CAST(educ4 AS VARCHAR) AS educ4,
                   UHRSWORK, WKSWORK2, INCWAGE, TRANWORK, OCC, IND
            FROM read_parquet('{ACS_PATH}')
            WHERE {SAMPLE_WHERE.format(s=SAMPLE_ID)}
            ORDER BY SERIAL, PERNUM"""
    df = con.execute(q).pl()
    df = df.with_columns(wk=pl.col("WKSWORK2").replace_strict(WEEKS_MID, default=None)).with_columns(
        hw=pl.col("INCWAGE") / (pl.col("UHRSWORK") * pl.col("wk")),
        D=(pl.col("TRANWORK") == 80).cast(pl.Float64),
        z1=(pl.col("AGE").cast(pl.Float64) - 45.0),
        z3=pl.col("female").cast(pl.Float64),
        e4=pl.col("educ4").replace_strict({lv: i for i, lv in enumerate(EDUC4_LEVELS)}, default=None),
    ).with_columns(lnw=pl.col("hw").log(), z2=pl.col("z1") ** 2)
    assert df["e4"].null_count() == 0 and df["female"].null_count() == 0
    df = df.with_columns(og=pl.Series(occ_group_index(df["OCC"].to_numpy())))
    return df


def load_repwts(con, df: pl.DataFrame) -> np.ndarray:
    """One read of the replicate part: REPWTP1-80 for the sample rows, aligned to df order."""
    con.register("sample_keys", df.select("SERIAL", "PERNUM").to_arrow())
    reps = ", ".join(f"r.REPWTP{i}" for i in range(1, N_REPS + 1))
    q = f"""SELECT r.SERIAL, r.PERNUM, {reps}
            FROM read_parquet('{REP_PATH}') r
            JOIN sample_keys k ON r.SERIAL = k.SERIAL AND r.PERNUM = k.PERNUM
            WHERE r.SAMPLE = {SAMPLE_ID}
            ORDER BY r.SERIAL, r.PERNUM"""
    rep = con.execute(q).pl()
    con.unregister("sample_keys")
    if len(rep) != len(df):
        raise AssertionError(f"replicate join returned {len(rep)} rows for {len(df)} sample rows")
    if not ((rep["SERIAL"] == df["SERIAL"]).all() and (rep["PERNUM"] == df["PERNUM"]).all()):
        raise AssertionError("replicate rows are not aligned with the sample")
    R = rep.select([f"REPWTP{i}" for i in range(1, N_REPS + 1)]).to_numpy().astype(np.float64)
    del rep
    return R


# ----------------------------------------------------------------------------- variance helpers
def sdr_se(theta: float, reps: np.ndarray) -> float:
    reps = np.asarray(reps, dtype=float)
    return float(math.sqrt(SDR_SCALE * np.sum((reps - theta) ** 2, axis=0)))


def sdr_se_vec(theta: np.ndarray, reps: np.ndarray) -> np.ndarray:
    """theta: (k,), reps: (R, k)."""
    return np.sqrt(SDR_SCALE * np.sum((reps - theta[None, :]) ** 2, axis=0))


# ----------------------------------------------------------------------------- cell-moment engine
# Per observation v = (1, D, z1, z2, z3, y). For groups g = (cell, D) we accumulate weighted sums of
# the outer product v v'. Every one-way fixed-effect WLS quantity in Chapters 4-5 (coefficients,
# cell contrasts, the linear propensity score, Sloczynski's decomposition) is a function of these
# sums, so each of the 80 replicates is an exact re-solve at the cost of one grouped sum.
TRIU = np.triu_indices(6)


class CellMoments:
    def __init__(self, cell: np.ndarray, D: np.ndarray, Z: np.ndarray, y: np.ndarray, n_cells: int):
        self.n_cells = n_cells
        n = len(y)
        V = np.column_stack([np.ones(n), D, Z, y])
        self.P = V[:, TRIU[0]] * V[:, TRIU[1]]  # n x 21
        g = 2 * cell + D.astype(np.int64)
        self.G = sp.csr_matrix((np.ones(n), (g, np.arange(n))), shape=(2 * n_cells, n))

    def sums(self, w: np.ndarray) -> np.ndarray:
        s = self.G @ (self.P * w[:, None])  # (2C, 21)
        S = np.zeros((s.shape[0], 6, 6))
        S[:, TRIU[0], TRIU[1]] = s
        S[:, TRIU[1], TRIU[0]] = s
        return S.reshape(self.n_cells, 2, 6, 6)


def fe_solve(S: np.ndarray, use_z: bool = True) -> dict:
    """WLS of y on D (+ z) with cell fixed effects, from moment sums S[c, d] (d = D value).

    Returns beta (coef on D), gamma, and the exact FWL representation
    beta = sum_c omega_c tau_c / sum_c omega_c,  omega_c = N_c p_c (1 - p_c),
    where tau_c is the within-cell WFH-commuter difference in mean (y - gamma'z).
    """
    St = S.sum(axis=1)
    N = St[:, 0, 0]
    xi = [1, 2, 3, 4] if use_z else [1]
    cross = np.einsum("ci,cj->cij", St[:, xi, 0], St[:, 0, xi]) / N[:, None, None]
    Sxx = (St[:, xi][:, :, xi] - cross).sum(axis=0)
    Sxy = (St[:, xi, 5] - St[:, xi, 0] * St[:, 0, 5][:, None] / N[:, None]).sum(axis=0)
    b = np.linalg.solve(Sxx, Sxy)
    beta = float(b[0])
    gamma = b[1:] if use_z else np.zeros(3)
    n1 = S[:, 1, 0, 0]
    n0 = S[:, 0, 0, 0]
    with np.errstate(divide="ignore", invalid="ignore"):
        m1 = (S[:, 1, 0, 5] - S[:, 1, 0, 2:5] @ gamma) / n1
        m0 = (S[:, 0, 0, 5] - S[:, 0, 0, 2:5] @ gamma) / n0
    tau = m1 - m0
    p = n1 / N
    omega = N * p * (1.0 - p)
    return {"beta": beta, "gamma": gamma, "tau": tau, "p": p, "N": N, "omega": omega,
            "m1": m1, "m0": m0, "fwl": float(np.nansum(omega * tau) / np.sum(omega))}


def estimands_from_cells(fit: dict) -> dict:
    """Population-, treated- and untreated-weighted averages of the cell contrasts."""
    N, p, tau, omega = fit["N"], fit["p"], fit["tau"], fit["omega"]
    Ntot = N.sum()
    rho = float((N * p).sum() / Ntot)
    pate = float((N * tau).sum() / Ntot)
    att = float((N * p * tau).sum() / (N * p).sum())
    atu = float((N * (1 - p) * tau).sum() / (N * (1 - p)).sum())
    proj = float((omega * tau).sum() / omega.sum())
    return {"rho": rho, "pate": pate, "att": att, "atu": atu, "proj": proj,
            "pop_share": N / Ntot, "reg_share": omega / omega.sum()}


def sloczynski_from_moments(S: np.ndarray, use_z: bool = True) -> dict:
    """Sloczynski (2022) Theorem 1 for y ~ D + z + cell FE, from moment sums.

    p(X) = linear projection of D on (cell FE, z); within each treatment group, y is projected on
    p(X); ATT/ATU are the average partial linear effects (APLE) on the treated / untreated:
      ATT_S = E[y|d=1] - (a0 + g0 E[p|d=1]),  ATU_S = (a1 + g1 E[p|d=0]) - E[y|d=0].
    w1 = (1-rho) V0 / (rho V1 + (1-rho) V0), OLS = w1 ATT_S + (1-w1) ATU_S exactly (in sample).
    """
    St = S.sum(axis=1)
    N = St[:, 0, 0]
    zi = [2, 3, 4]
    if use_z:
        cross = np.einsum("ci,cj->cij", St[:, zi, 0], St[:, 0, zi]) / N[:, None, None]
        Szz = (St[:, zi][:, :, zi] - cross).sum(axis=0)
        SzD = (St[:, zi, 1] - St[:, zi, 0] * St[:, 0, 1][:, None] / N[:, None]).sum(axis=0)
        bl = np.linalg.solve(Szz, SzD)
    else:
        bl = np.zeros(3)
    a = (St[:, 0, 1] - St[:, 0, zi] @ bl) / N  # cell intercepts of the LPM
    grp = {}
    for d in (0, 1):
        Sd = S[:, d]
        Nd = Sd[:, 0, 0].sum()
        Q = (a * Sd[:, 0, 0] + Sd[:, 0, zi] @ bl).sum()
        Q2 = (a ** 2 * Sd[:, 0, 0] + 2 * a * (Sd[:, 0, zi] @ bl)
              + np.einsum("i,cij,j->c", bl, Sd[:, zi][:, :, zi], bl)).sum()
        Y = Sd[:, 0, 5].sum()
        QY = (a * Sd[:, 0, 5] + Sd[:, zi, 5] @ bl).sum()
        qbar, ybar = Q / Nd, Y / Nd
        V = Q2 / Nd - qbar ** 2
        C = QY / Nd - qbar * ybar
        g = C / V
        grp[d] = {"N": Nd, "qbar": qbar, "ybar": ybar, "V": V, "g": g, "a": ybar - g * qbar}
    g0, g1 = grp[0], grp[1]
    rho = g1["N"] / (g0["N"] + g1["N"])
    att = g1["ybar"] - (g0["a"] + g0["g"] * g1["qbar"])
    atu = (g1["a"] + g1["g"] * g0["qbar"]) - g0["ybar"]
    w1 = (1 - rho) * g0["V"] / (rho * g1["V"] + (1 - rho) * g0["V"])
    return {"rho": float(rho), "w1": float(w1), "w0": float(1 - w1), "att": float(att), "atu": float(atu),
            "ape": float(rho * att + (1 - rho) * atu), "delta": float(rho - w1),
            "implied": float(w1 * att + (1 - w1) * atu), "V1": float(g1["V"]), "V0": float(g0["V"])}


# ----------------------------------------------------------------------------- generic regression SEs
def within(cell: np.ndarray, X: np.ndarray, w: np.ndarray, n_cells: int) -> np.ndarray:
    Nc = np.bincount(cell, weights=w, minlength=n_cells)
    out = np.empty_like(X)
    for j in range(X.shape[1]):
        m = np.bincount(cell, weights=w * X[:, j], minlength=n_cells) / Nc
        out[:, j] = X[:, j] - m[cell]
    return out


def sandwich(h: np.ndarray, w: np.ndarray, e: np.ndarray, n: int, k: int, clusters: dict | None = None,
             ainv_dd: float | None = None) -> dict:
    """SEs for one coefficient from its influence representation psi_i = h_i w_i e_i.

    h = X A^{-1} e_j (A = X'WX), so beta_j - beta_j0 = sum_i psi_i.
    iid uses sigma^2 = sum w e^2/(n-k) times (A^{-1})_jj; HC1 = n/(n-k) sum psi^2;
    CR1 = G/(G-1) (n-1)/(n-k) sum_g (sum_{i in g} psi_i)^2.
    """
    psi = h * w * e
    out = {}
    if ainv_dd is not None:
        s2 = float(np.sum(w * e ** 2) / (n - k))
        out["iid"] = math.sqrt(s2 * ainv_dd)
    out["hc1"] = math.sqrt(n / (n - k) * float(np.sum(psi ** 2)))
    for name, codes in (clusters or {}).items():
        sg = np.bincount(codes, weights=psi)
        G = int(np.count_nonzero(np.bincount(codes)))
        out[f"cr_{name}"] = math.sqrt(G / (G - 1) * (n - 1) / (n - k) * float(np.sum(sg ** 2)))
        out[f"G_{name}"] = G
    return out


def fe_ses(cell, n_cells, D, Z, y, w, clusters) -> dict:
    """Coefficient on D and its iid/HC1/CR1 SEs for y ~ D + Z + cell FE (weights w)."""
    X = np.column_stack([D, Z]) if Z is not None else D[:, None]
    Xt = within(cell, X, w, n_cells)
    yt = within(cell, y[:, None], w, n_cells)[:, 0]
    A = Xt.T @ (Xt * w[:, None])
    b = np.linalg.solve(A, Xt.T @ (w * yt))
    e = yt - Xt @ b
    ej = np.zeros(X.shape[1])
    ej[0] = 1.0
    a = np.linalg.solve(A, ej)
    h = Xt @ a
    n = len(y)
    k = X.shape[1] + n_cells
    se = sandwich(h, w, e, n, k, clusters, ainv_dd=float(a[0]))
    return {"beta": float(b[0]), "se": se, "resid": e, "k": k}


class SparseFE:
    """y ~ dense columns + several sets of fixed effects, as sparse normal equations."""

    def __init__(self, dense: np.ndarray, fe_codes: list[np.ndarray], d_col: int = 1):
        blocks = [sp.csr_matrix(dense)]
        self.n_fe = []
        for codes in fe_codes:
            levels, inv = np.unique(codes, return_inverse=True)
            m = sp.csr_matrix((np.ones(len(codes)), (np.arange(len(codes)), inv)), shape=(len(codes), len(levels)))
            blocks.append(m[:, 1:])
            self.n_fe.append(len(levels))
        self.X = sp.hstack(blocks).tocsr()
        self.Xt = self.X.T.tocsr()
        self.d_col = d_col
        self.k = self.X.shape[1]

    def normal(self, w: np.ndarray) -> np.ndarray:
        return (self.Xt @ self.X.multiply(w[:, None]).tocsr()).toarray()

    def fit(self, y: np.ndarray, w: np.ndarray, A: np.ndarray | None = None) -> np.ndarray:
        A = self.normal(w) if A is None else A
        return sla.solve(A, self.Xt @ (w * y), assume_a="sym")

    def ses(self, y, w, clusters) -> dict:
        A = self.normal(w)
        b = sla.solve(A, self.Xt @ (w * y), assume_a="sym")
        e = y - self.X @ b
        ej = np.zeros(self.k)
        ej[self.d_col] = 1.0
        a = sla.solve(A, ej, assume_a="sym")
        h = self.X @ a
        se = sandwich(h, w, e, len(y), self.k, clusters, ainv_dd=float(a[self.d_col]))
        return {"beta": float(b[self.d_col]), "se": se, "coef": b}


# ----------------------------------------------------------------------------- misc statistics
def icc_anova(values: np.ndarray, codes: np.ndarray) -> tuple[float, float]:
    """One-way ANOVA intraclass correlation for unequal cluster sizes; also returns m0."""
    m = np.bincount(codes)
    keep = m > 0
    m = m[keep]
    s = np.bincount(codes, weights=values)[keep]
    ss = np.bincount(codes, weights=values ** 2)[keep]
    n, G = values.size, m.size
    grand = values.mean()
    ssb = float(np.sum(s ** 2 / m) - n * grand ** 2)
    ssw = float(np.sum(ss - s ** 2 / m))
    msb, msw = ssb / (G - 1), ssw / (n - G)
    m0 = (n - float(np.sum(m ** 2)) / n) / (G - 1)
    return (msb - msw) / (msb + (m0 - 1) * msw), m0


def moulton_factor(rho_x: float, rho_u: float, codes: np.ndarray) -> tuple[float, float]:
    """1 + [V(m)/mbar + mbar - 1] rho_x rho_u (Moulton 1986; Angrist-Pischke eq. 8.2.5)."""
    m = np.bincount(codes)
    m = m[m > 0].astype(float)
    mbar = m.mean()
    k = m.var() / mbar + mbar - 1.0
    return 1.0 + k * rho_x * rho_u, k


def wald_test(b: np.ndarray, V: np.ndarray, df2: float) -> tuple[float, float, int]:
    q = len(b)
    W = float(b @ np.linalg.solve(V, b))
    F = W / q
    return F, float(stats.f.sf(F, q, df2)), q
