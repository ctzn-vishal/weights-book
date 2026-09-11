"""Chapter 0 build: the tiny synthetic example behind the worked Analysis Ledger.

No survey microdata are read. Every number is either a property of a seeded
synthetic population (definitional, variance "none") or a property of simulated
samples drawn from it (variance "simulation").

    python build.py   -> artifacts/{manifest,facts,ledger}.json
                         artifacts/figures/toy_sampling.json

Deterministic: fixed seed, fixed rounding, sorted keys; only manifest.json
carries a timestamp.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

os.environ.setdefault("NO_COLOR", "1")

import numpy as np
import polars as pl
import svy
from scipy import stats

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
KEY, SLUG = "ch0", "ch00-start-here"
SEED = 20260910
SOURCE = "Synthetic population defined in ch00-start-here/build.py (seed 20260910); no survey data"

N_RURAL, N_URBAN = 20_000, 80_000   # population sizes by stratum
P_RURAL, P_URBAN = 0.30, 0.10       # probabilities used once, to generate the fixed population
n_RURAL, n_URBAN = 500, 500         # stratified sample: rural adults sampled at 4x the urban rate
REPS = 2_000                        # repetitions of the same design


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, sort_keys=True, indent=2, ensure_ascii=False)
        f.write("\n")


def fact(value, display, estimand, **kw) -> dict:
    out = {"value": value, "display": display, "unit": None, "se": None, "ci_low": None,
           "ci_high": None, "ci_display": None, "df": None, "n": None, "weight": None,
           "variance": "none", "estimand": estimand, "source": SOURCE, "benchmark": None, "note": ""}
    out.update(kw)
    return out


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def r6(x: float) -> float:
    return round(float(x), 6)


# ------------------------------------------------------------------ the finite population
rng = np.random.default_rng(SEED)
y = np.concatenate([rng.binomial(1, P_RURAL, N_RURAL),
                    rng.binomial(1, P_URBAN, N_URBAN)]).astype(float)
N = y.size
truth = float(y.mean())                       # a finite-population quantity, known exactly
IDX_R, IDX_U = np.arange(N_RURAL), np.arange(N_RURAL, N)
D_R, D_U = N_RURAL / n_RURAL, N_URBAN / n_URBAN   # design weights d_i = 1/pi_i: 40 and 160
W_R, W_U = N_RURAL / N, N_URBAN / N               # population shares of the strata
DF = n_RURAL + n_URBAN - 2                        # design df = n - H (every unit its own PSU)
T975 = float(stats.t.ppf(0.975, DF))


def draw(g: np.random.Generator):
    """One stratified simple random sample without replacement."""
    return (y[g.choice(IDX_R, n_RURAL, replace=False)],
            y[g.choice(IDX_U, n_URBAN, replace=False)])


def estimate(yr: np.ndarray, yu: np.ndarray):
    unweighted = float(np.concatenate([yr, yu]).mean())
    weighted = float((D_R * yr.sum() + D_U * yu.sum()) / (D_R * n_RURAL + D_U * n_URBAN))
    # stratified with-replacement (Taylor) variance of the Hajek mean
    se = float(np.sqrt(W_R ** 2 * yr.var(ddof=1) / n_RURAL + W_U ** 2 * yu.var(ddof=1) / n_URBAN))
    return unweighted, weighted, se


# ------------------------------------------------------------------ one realized sample
yr1, yu1 = draw(np.random.default_rng(SEED + 1))
unw1, wtd1, se1 = estimate(yr1, yu1)
lo1, hi1 = wtd1 - T975 * se1, wtd1 + T975 * se1

# dual path: the same estimate through svy's declared stratified design
frame = pl.DataFrame({
    "y": np.concatenate([yr1, yu1]),
    "stratum": ["rural"] * n_RURAL + ["urban"] * n_URBAN,
    "w": [D_R] * n_RURAL + [D_U] * n_URBAN,
})
svy_est = (svy.Sample(frame, design=svy.Design(stratum="stratum", wgt="w"))
           .estimation.mean("y").to_dicts()[0])

# ------------------------------------------------------------------ repeated sampling
g = np.random.default_rng(SEED + 2)
sims = np.array([estimate(*draw(g)) for _ in range(REPS)])
unw, wtd, ses = sims[:, 0], sims[:, 1], sims[:, 2]
mc_sd = float(wtd.std(ddof=1))
coverage = float(np.mean(np.abs(wtd - truth) <= T975 * ses))
q = {k: np.quantile(v, [0.025, 0.975]) for k, v in (("unw", unw), ("wtd", wtd))}

# ------------------------------------------------------------------ facts
EST = "Share of the synthetic population's adults lacking a regular source of care"
facts = {
    "toy_pop_n": fact(N, f"{N:,}", "Size of the synthetic finite population (a design choice of the illustration)",
                      unit="adults", n=N),
    "toy_sample_n": fact(n_RURAL + n_URBAN, f"{n_RURAL + n_URBAN:,}",
                         "Sample size of each simulated stratified sample (a design choice)", unit="adults"),
    "toy_reps": fact(REPS, f"{REPS:,}", "Number of simulated repetitions of the same sampling design",
                     unit="repetitions"),
    "toy_truth": fact(r6(truth), pct(truth), f"{EST}: the finite-population proportion, computed exactly",
                      n=N, note="Known exactly because the whole synthetic population is in hand."),
    "toy_unweighted": fact(r6(unw1), pct(unw1), f"{EST}: unweighted sample mean, one simulated sample",
                           n=n_RURAL + n_URBAN, weight="none", variance="simulation",
                           note="Rural adults are half the sample but a fifth of the population."),
    "toy_weighted": fact(r6(wtd1), pct(wtd1), f"{EST}: Hajek weighted mean, one simulated sample",
                         se=r6(se1), ci_low=r6(lo1), ci_high=r6(hi1),
                         ci_display=f"{100 * lo1:.1f}%–{100 * hi1:.1f}%", df=DF,
                         n=n_RURAL + n_URBAN, weight="d_i = 1/pi_i (40 rural, 160 urban)",
                         variance="simulation",
                         note="SE from the stratified with-replacement (Taylor) formula on this one sample; "
                              "identical to svy's declared-design SE (dual-path check in manifest)."),
    "toy_weighted_se": fact(r6(100 * se1), f"{100 * se1:.1f}",
                            f"{EST}: design-based SE of the weighted mean in the one simulated sample",
                            unit="percentage points", variance="simulation", n=n_RURAL + n_URBAN),
    "toy_unweighted_avg": fact(r6(unw.mean()), pct(unw.mean()),
                               f"{EST}: average of the unweighted mean over repeated samples",
                               n=n_RURAL + n_URBAN, weight="none", variance="simulation",
                               note=f"Average over {REPS:,} repetitions of the stratified design."),
    "toy_weighted_avg": fact(r6(wtd.mean()), pct(wtd.mean()),
                             f"{EST}: average of the weighted mean over repeated samples",
                             n=n_RURAL + n_URBAN, weight="d_i = 1/pi_i", variance="simulation",
                             note=f"Average over {REPS:,} repetitions of the stratified design."),
    "toy_weighted_sd": fact(r6(100 * mc_sd), f"{100 * mc_sd:.1f}",
                            f"{EST}: standard deviation of the weighted mean across repeated samples",
                            unit="percentage points", variance="simulation",
                            note="The repeated-sampling spread that a design-based SE estimates."),
    "toy_coverage": fact(r6(coverage), pct(coverage),
                         "Share of repeated samples whose nominal 95% interval for the weighted mean covers the truth",
                         variance="simulation", note=f"t interval with {DF} df, {REPS:,} repetitions."),
}

# ------------------------------------------------------------------ ledger
ledger = {
    "toy_care": {
        "title": "A worked Ledger: share of a synthetic population lacking a regular source of care",
        "target_population": "The 100,000 adults of the chapter's synthetic population: a finite "
                             "population fixed once by the build script's seed, a fifth of them rural.",
        "estimand": "The population proportion lacking a regular source of care, a finite-population "
                    "quantity that can be computed exactly here because the whole population is known.",
        "estimator": "Hajek weighted mean over the 1,000 sampled adults: sum of w_i y_i divided by sum of w_i.",
        "explicit_weights": "Design weights d_i = 1/pi_i: 40 for rural adults (sampled 1 in 40) and 160 for "
                            "urban adults (1 in 160). No nonresponse or calibration adjustment (g_i = 1), so w_i = d_i.",
        "implicit_weights": "None beyond the explicit weights: for a mean, each unit enters in proportion to "
                            "w_i. Unweighted, rural adults would carry half the influence while making up a "
                            "fifth of the population.",
        "randomness": "Sampling only: which adults the stratified design selects. The population values are fixed.",
        "variance_estimator": "Stratified with-replacement (Taylor) variance with n - H = 998 df, checked against "
                              "the spread of the weighted mean over 2,000 simulated repetitions of the same design.",
        "assumptions": "Inclusion probabilities are known and positive; every sampled adult responds; the "
                       "outcome is measured without error. Relax any of these and the weights stop being 1/pi_i.",
        "facts": ["ch0.toy_truth", "ch0.toy_weighted", "ch0.toy_unweighted",
                  "ch0.toy_weighted_sd", "ch0.toy_coverage"],
    }
}

# ------------------------------------------------------------------ figure
figure = {
    "type": "dot",
    "title": "Two estimators under the same design, 2,000 repeated samples",
    "subtitle": "Dot: average estimate across repetitions; bar: middle 95% of estimates",
    "alt": "Dot plot: across 2,000 simulated stratified samples the weighted estimate centers on the "
           "population truth, while the unweighted mean centers well above it; bars show the middle 95% "
           "of estimates.",
    "format": "pct1",
    "x_label": "Share lacking a regular source of care",
    "reference": {"value": r6(truth), "label": "population truth"},
    "rows": [
        {"label": "Population truth", "estimate": r6(truth), "role": "truth"},
        {"label": "Weighted mean (design weights)", "estimate": r6(wtd.mean()),
         "ci_low": r6(q["wtd"][0]), "ci_high": r6(q["wtd"][1]), "role": "weighted", "n": n_RURAL + n_URBAN},
        {"label": "Unweighted mean", "estimate": r6(unw.mean()),
         "ci_low": r6(q["unw"][0]), "ci_high": r6(q["unw"][1]), "role": "unweighted", "n": n_RURAL + n_URBAN},
    ],
    "source": SOURCE,
    "note": "Rural adults (a fifth of the population) are sampled at four times the urban rate.",
}

# ------------------------------------------------------------------ validation + manifest
z_unbiased = (wtd.mean() - truth) / (mc_sd / np.sqrt(REPS))
validation = [
    {"check": "dual-path point estimate: numpy Hajek mean vs svy declared design",
     "numpy": round(wtd1, 12), "svy": round(float(svy_est["est"]), 12),
     "abs_diff": float(f"{abs(wtd1 - svy_est['est']):.3e}"), "pass": bool(abs(wtd1 - svy_est["est"]) < 1e-12)},
    {"check": "dual-path SE: stratified formula vs svy Taylor",
     "numpy": round(se1, 12), "svy": round(float(svy_est["se"]), 12),
     "rel_diff": float(f"{abs(se1 - svy_est['se']) / se1:.3e}"),
     "pass": bool(abs(se1 - svy_est["se"]) / se1 < 1e-9)},
    {"check": "svy design df equals n - H", "svy_df": int(svy_est["df"]), "expected": DF,
     "pass": int(svy_est["df"]) == DF},
    {"check": "Monte Carlo: weighted mean centers on the truth",
     "mc_mean": round(float(wtd.mean()), 6), "truth": round(truth, 6), "z": round(float(z_unbiased), 3),
     "pass": bool(abs(z_unbiased) < 3)},
    {"check": "Monte Carlo: unweighted mean is biased under the oversample",
     "mc_mean": round(float(unw.mean()), 6), "truth": round(truth, 6),
     "bias": round(float(unw.mean() - truth), 6), "pass": bool(unw.mean() - truth > 0.03)},
    {"check": "formula SE calibrated to repeated-sampling SD",
     "mean_formula_se": round(float(ses.mean()), 6), "mc_sd": round(mc_sd, 6),
     "ratio": round(float(ses.mean() / mc_sd), 4), "pass": bool(abs(ses.mean() / mc_sd - 1) < 0.05)},
    {"check": "nominal 95% interval coverage", "coverage": round(coverage, 4),
     "pass": bool(abs(coverage - 0.95) < 0.02)},
]
manifest = {
    "key": KEY, "slug": SLUG, "status": "draft",
    "inputs": [],
    "code": "build.py",
    "note": "No survey data: a seeded synthetic population (seed 20260910). "
            "The PopulationSampler widget uses the canonical population in lib/synthpop.ts, not this one.",
    "validation": validation,
    "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}

write_json(ART / "facts.json", {"key": KEY, "facts": facts})
write_json(ART / "ledger.json", {"key": KEY, "ledgers": ledger})
write_json(ART / "figures" / "toy_sampling.json", figure)
write_json(ART / "manifest.json", manifest)

failed = [v["check"] for v in validation if not v["pass"]]
print(f"ch0: truth {pct(truth)}, one sample unweighted {pct(unw1)} weighted {pct(wtd1)} (SE {100*se1:.2f} pp); "
      f"MC mean unweighted {pct(unw.mean())} weighted {pct(wtd.mean())}, SD {100*mc_sd:.2f} pp, coverage {pct(coverage)}")
print("validation:", "all pass" if not failed else f"FAILED {failed}")
