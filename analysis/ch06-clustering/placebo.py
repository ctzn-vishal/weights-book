"""placebo.py -- placebo-law check for Chapter 6, on the chapter's own state-year cells.

Bertrand, Duflo and Mullainathan (2004) assigned laws that never happened to randomly chosen states
and counted how often each standard error rejected the (true) null of no effect. This module does the
same on the design's cells, with the same regression as the chapter (PERWT-weighted linear probability
model of being uninsured, state and year fixed effects, an indicator for placebo states from 2014 on).

Two designs:
  comparison  the 15 states that never expanded; 7 of them are labelled placebo expanders. Every one
              of the C(15, 7) = 6,435 assignments is enumerated (a labelling of 8 gives the same |t|
              under every rule, since the indicator is post minus the 7-state indicator). No expansion
              happened in any of these states, so the null of no effect holds. No seed is needed.
  all         the 30 design states; 15 are labelled placebo expanders in each of R seeded draws. The
              real expansion stays in the outcome and acts as a state-level shock that the placebo
              regression does not model.

Person-level HC1, household-clustered, state-year-clustered and state-clustered (CRV1) standard errors
are exact functions of a few per-cell sums (sum w, sum w y, sum w^2, sum w^2 y, and the household
sums sum_h A_h^2, sum_h A_h B_h, sum_h B_h^2 with A_h = sum w y and B_h = sum w in household h), so
each placebo regression costs a few vector operations on the 270 (or 135) cells. CV3 is the
leave-one-state-out jackknife of MacKinnon, Nielsen and Webb (2023). Tests use the same reference
distributions as pyfixest: t(N - K) for HC1, t(G - 1) for the clustered rules.

build.py calls run(); it never writes artifacts itself.
"""
from __future__ import annotations

import itertools

import numpy as np
from scipy import stats

POLICY_YEAR = 2014


class PlaceboCells:
    """Cells of one placebo design, with the per-cell sums needed for every rung."""

    def __init__(self, cells, n_person, n_households):
        c = cells
        self.st, self.yr = c["st"], c["yr"]
        self.W, self.y = c["W"], c["ybar"]
        self.S2, self.S2y = c["S2"], c["S2y"]
        self.HA2, self.HAB, self.HB2 = c["HA2"], c["HAB"], c["HB2"]
        self.NP, self.NH, self.NC = int(n_person), int(n_households), len(self.y)
        self.states = np.unique(self.st)
        self.G = len(self.states)
        self.g = np.searchsorted(self.states, self.st)
        years = np.unique(self.yr)
        self.ny = len(years)
        self.sw = np.sqrt(self.W)
        Z = np.column_stack([(self.st[:, None] == self.states[None, :]).astype(float),
                             (self.yr[:, None] == years[None, 1:]).astype(float)])
        self.Zs = self.sw[:, None] * Z
        self.PZ = self.Zs @ np.linalg.pinv(self.Zs)
        self.ys = self.sw * self.y
        self.ytil = self.ys - self.PZ @ self.ys
        self.post = (self.yr >= POLICY_YEAR).astype(float)
        # pyfixest's small-sample conventions: K counts fixed effects not nested in the cluster
        self.K_full = 1 + self.G + (self.ny - 1)      # HC1, household, state-year
        self.K_state = 1 + (self.ny - 1)              # state clusters absorb the state effects
        self.t_hc1 = stats.t.ppf(0.975, self.NP - self.K_full)
        self.t_hh = stats.t.ppf(0.975, self.NH - 1)
        self.t_sy = stats.t.ppf(0.975, self.NC - 1)
        self.t_g = stats.t.ppf(0.975, self.G - 1)

    def D_for(self, treated):
        return np.isin(self.st, np.asarray(treated)) * self.post

    def fit(self, D, jackknife=False):
        """Coefficient and the five standard errors for one placebo indicator."""
        Ds = self.sw * D
        Dt = Ds - self.PZ @ Ds
        DtD = float(Dt @ Dt)
        b = float(Dt @ self.ytil / DtD)
        e = self.ytil - Dt * b                       # sqrt(W)-scaled cell residual
        f = self.y - e / self.sw                     # fitted cell value
        xt = Dt / self.sw                            # within-transformed D at the cell level
        NP, K, Kg = self.NP, self.K_full, self.K_state
        meat_h = np.sum(xt ** 2 * (self.S2y * (1 - 2 * f) + f ** 2 * self.S2))
        se_hc1 = np.sqrt((NP - 1) / (NP - K) * meat_h) / DtD
        meat_hh = np.sum(xt ** 2 * (self.HA2 - 2 * f * self.HAB + f ** 2 * self.HB2))
        se_hh = np.sqrt(self.NH / (self.NH - 1) * (NP - 1) / (NP - K) * meat_hh) / DtD
        meat_sy = np.sum((Dt * e) ** 2)
        se_sy = np.sqrt(self.NC / (self.NC - 1) * (NP - 1) / (NP - K) * meat_sy) / DtD
        sc = np.bincount(self.g, weights=Dt * e, minlength=self.G)
        se_st = np.sqrt(self.G / (self.G - 1) * (NP - 1) / (NP - Kg) * np.sum(sc ** 2)) / DtD
        out = {"b": b, "hc1": se_hc1, "household": se_hh, "state_year": se_sy, "state": se_st}
        if jackknife:
            Xs = np.column_stack([Ds, self.Zs])
            bj = np.empty(self.G)
            for j, s in enumerate(self.states):
                keep = self.st != s
                Xk = Xs[keep]
                Xk = Xk[:, np.abs(Xk).sum(0) > 0]
                bj[j] = np.linalg.lstsq(Xk, self.ys[keep], rcond=None)[0][0]
            out["cv3"] = float(np.sqrt((self.G - 1) / self.G * np.sum((bj - b) ** 2)))
        return out

    def rejects(self, r):
        return {"hc1": abs(r["b"]) > self.t_hc1 * r["hc1"], "household": abs(r["b"]) > self.t_hh * r["household"],
                "state_year": abs(r["b"]) > self.t_sy * r["state_year"], "state": abs(r["b"]) > self.t_g * r["state"],
                "cv3": abs(r["b"]) > self.t_g * r["cv3"]}


RUNGS = ("hc1", "household", "state_year", "state", "cv3")


def summarize(pc: PlaceboCells, assignments) -> dict:
    n = len(assignments)
    b = np.empty(n)
    se = {k: np.empty(n) for k in RUNGS}
    rej = {k: 0 for k in RUNGS}
    for i, T in enumerate(assignments):
        r = pc.fit(pc.D_for(T), jackknife=True)
        b[i] = r["b"]
        for k in RUNGS:
            se[k][i] = r[k]
        for k, v in pc.rejects(r).items():
            rej[k] += int(v)
    return {"n": n, "sd_coef": float(b.std(ddof=1)), "mean_coef": float(b.mean()), "coefs": b,
            "reject": {k: rej[k] / n for k in RUNGS}, "median_se": {k: float(np.median(se[k])) for k in RUNGS},
            "median_ratio_to_hc1": {k: float(np.median(se[k] / se["hc1"])) for k in RUNGS}}


def run(cells_comp, cells_all, n_comp, nh_comp, n_all, nh_all, comp_states, design_states, n_placebo_comp,
        R_all, seed_all):
    """cells_*: dicts of per-cell arrays (st, yr, W, ybar, S2, S2y, HA2, HAB, HB2), sorted by state then year."""
    pc_comp = PlaceboCells(cells_comp, n_comp, nh_comp)
    pc_all = PlaceboCells(cells_all, n_all, nh_all)
    comp_states = sorted(int(s) for s in comp_states)
    enum = [list(c) for c in itertools.combinations(comp_states, n_placebo_comp)]
    rng = np.random.default_rng(seed_all)
    design_states = np.array(sorted(int(s) for s in design_states))
    draws = [sorted(rng.choice(design_states, size=len(design_states) // 2, replace=False).tolist()) for _ in range(R_all)]
    res_comp = summarize(pc_comp, enum)
    res_all = summarize(pc_all, draws)
    return {"comparison": res_comp, "all": res_all, "first_enum": enum[0], "first_draw": draws[0],
            "pc_comp": pc_comp, "pc_all": pc_all, "n_assignments_comp": len(enum)}
