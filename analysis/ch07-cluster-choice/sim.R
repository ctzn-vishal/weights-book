# Chapter 7 (key ch7): the clustering menu, checked by simulation with fixest.
#
#   Rscript sim.R            writes _scratch/sim_results.json and _scratch/opening_draw.csv
#   REPS=50 Rscript sim.R    quick run
#
# Six designs in which the source of variation is fixed by construction, so the
# right variance estimator is known and every candidate can be scored by how
# often a nominal 5% test rejects a true null. Every estimator is a `vcov`
# argument to fixest::feols (fixest 0.14.x; the default VCOV has been "iid" since
# 0.13.0). p-values come from fixest's own reference distributions, so the small-
# sample corrections are fixest's defaults: ssc(K.adj = TRUE, K.fixef = "nonnested",
# G.adj = TRUE, G.df = "min", t.df = "min").
#
# Deterministic: one fixed seed per design; results do not depend on REPS order.

suppressPackageStartupMessages({
  library(fixest)
  library(jsonlite)
})
setFixest_nthreads(1)

REPS  <- as.integer(Sys.getenv("REPS", "1000"))
ALPHA <- 0.05
HERE  <- normalizePath(dirname(sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE)[1])), winslash = "/")
SCR   <- file.path(HERE, "_scratch")
dir.create(SCR, showWarnings = FALSE)

# ---------------------------------------------------------------- helpers
# One design = a data generator (returns a data.frame with a true null on `x` or `d`),
# a fixest formula, and a named list of vcov specifications.
run_design <- function(name, seed, gen, fml, vcovs, coef = NULL, extra = NULL) {
  set.seed(seed)
  rej <- setNames(numeric(length(vcovs)), names(vcovs))
  se_sum <- rej
  se_iid_sum <- 0
  t0 <- Sys.time()
  for (r in seq_len(REPS)) {
    d <- gen()
    fit <- feols(fml, data = d, warn = FALSE, notes = FALSE)
    k <- if (is.null(coef)) names(coef(fit))[1] else coef
    se_iid_sum <- se_iid_sum + se(fit, vcov = "iid")[k]
    for (v in names(vcovs)) {
      vc <- vcovs[[v]]$vcov
      p <- pvalue(fit, vcov = vc)[k]
      rej[v] <- rej[v] + as.numeric(p < ALPHA)
      se_sum[v] <- se_sum[v] + se(fit, vcov = vc)[k]
    }
  }
  secs <- as.numeric(difftime(Sys.time(), t0, units = "secs"))
  cat(sprintf("%-28s n=%6d  %5.0fs  ", name, nrow(d), secs))
  cat(paste(sprintf("%s=%.3f", names(rej), rej / REPS), collapse = "  "), "\n")
  list(
    name = name, seed = seed, reps = REPS, n_obs = nrow(d), seconds = round(secs, 1),
    extra = extra,
    estimators = lapply(names(vcovs), function(v) list(
      key = v, label = vcovs[[v]]$label, code = vcovs[[v]]$code, verdict = vcovs[[v]]$verdict,
      reject = unname(rej[v]) / REPS,
      se_mean = unname(se_sum[v]) / REPS,
      se_ratio_to_iid = unname(se_sum[v]) / se_iid_sum
    ))
  )
}
V <- function(vcov, label, code, verdict) list(vcov = vcov, label = label, code = code, verdict = verdict)
ar1 <- function(T, rho, sd) {
  x <- numeric(T); x[1] <- rnorm(1, 0, sd)
  innov <- sd * sqrt(1 - rho^2)
  for (t in 2:T) x[t] <- rho * x[t - 1] + rnorm(1, 0, innov)
  x
}

results <- list()

# ---------------------------------------------------------------- D0: an experiment, randomized at two levels
# 40 schools x 4 classrooms x 25 students. Classroom-specific treatment effects with mean
# zero (so the average effect, the null, is exactly zero) plus school and classroom shocks.
# Arm A assigns treatment student by student; arm B assigns whole classrooms.
S <- 40; C <- 4; NS <- 25
gen_exp <- function(arm) function() {
  school <- rep(seq_len(S), each = C * NS)
  class  <- rep(seq_len(S * C), each = NS)
  u_s <- rnorm(S, 0, 0.5)[school]
  u_c <- rnorm(S * C, 0, 0.5)[class]
  tau <- rnorm(S * C, 0, 0.5); tau <- tau - mean(tau)   # the average effect over these classrooms is exactly zero
  tau_c <- tau[class]
  d <- if (arm == "individual") rbinom(S * C * NS, 1, 0.5) else {
    treated_class <- as.vector(sapply(seq_len(S), function(s) (s - 1) * C + sample(C, C / 2)))
    as.integer(class %in% treated_class)
  }
  y <- tau_c * d + u_s + u_c + rnorm(S * C * NS)
  data.frame(y, d, school, class)
}
vc_exp <- list(
  hetero = V("hetero", "HC1, no clustering", 'vcov = "hetero"', NA),
  class  = V(~class,   "cluster by classroom", "vcov = ~classroom", NA),
  school = V(~school,  "cluster by school", "vcov = ~school", NA)
)
results$exp_individual <- run_design("D0a experiment: individual", 601, gen_exp("individual"), y ~ d | school, vc_exp, coef = "d",
  extra = list(schools = S, classrooms = S * C, students = S * C * NS))
results$exp_classroom  <- run_design("D0b experiment: classroom", 602, gen_exp("classroom"), y ~ d | school, vc_exp, coef = "d",
  extra = list(schools = S, classrooms = S * C, students = S * C * NS))

# ---------------------------------------------------------------- D1: an aggregate regressor (Moulton)
# 50 states x 200 people. The regressor of interest varies only by state; the outcome has a
# state shock (ICC 0.2) and an individual covariate.
G1 <- 50; NG1 <- 200; SD_U1 <- 0.5
gen_moulton <- function() {
  state <- rep(seq_len(G1), each = NG1)
  x <- rnorm(G1)[state]
  z <- rnorm(G1 * NG1)
  y <- z + rnorm(G1, 0, SD_U1)[state] + rnorm(G1 * NG1)
  data.frame(y, x, z, state)
}
icc1 <- SD_U1^2 / (SD_U1^2 + 1)
results$moulton <- run_design("D1 Moulton", 611, gen_moulton, y ~ x + z, list(
  iid    = V("iid",    "IID (fixest default)", 'vcov = "iid"', NA),
  hetero = V("hetero", "HC1, no clustering", 'vcov = "hetero"', NA),
  state  = V(~state,   "cluster by state", "vcov = ~state", NA)
), coef = "x", extra = list(states = G1, per_state = NG1, icc = icc1, moulton_factor = sqrt(1 + (NG1 - 1) * icc1)))

# ---------------------------------------------------------------- D2: difference-in-differences with serial correlation
# States x 20 years x 10 people per state-year. Half the states adopt a policy in a year
# drawn from 6..15; state shocks follow an AR(1) with rho 0.8. State and year fixed effects.
T2 <- 20; NC2 <- 10; RHO2 <- 0.8; SD_V2 <- 0.5
gen_did <- function(G) function() {
  state <- rep(seq_len(G), each = T2 * NC2)
  year  <- rep(rep(seq_len(T2), each = NC2), times = G)
  adopt <- rep(NA_integer_, G); adopt[sample(G, G / 2)] <- sample(6:15, G / 2, replace = TRUE)
  d <- as.integer(!is.na(adopt[state]) & year >= adopt[state])
  v <- as.vector(sapply(seq_len(G), function(s) rep(ar1(T2, RHO2, SD_V2), each = NC2)))
  y <- rnorm(G, 0, 0.5)[state] + rnorm(T2, 0, 0.3)[year] + v + rnorm(G * T2 * NC2)
  data.frame(y, d, state, year)
}
vc_did <- list(
  hetero    = V("hetero",     "HC1, no clustering", 'vcov = "hetero"', NA),
  stateyear = V(~state^year,  "cluster by state-year", "vcov = ~state^year", NA),
  state     = V(~state,       "cluster by state", "vcov = ~state", NA),
  twoway    = V(~state + year, "two-way: state and year", "vcov = ~state + year", NA)
)
results$did_g50 <- run_design("D2a DiD, 50 states", 621, gen_did(50), y ~ d | state + year, vc_did, coef = "d",
  extra = list(states = 50, years = T2, per_cell = NC2, rho = RHO2))
results$did_g10 <- run_design("D2b DiD, 10 states", 622, gen_did(10), y ~ d | state + year, vc_did, coef = "d",
  extra = list(states = 10, years = T2, per_cell = NC2, rho = RHO2))

# The opening draw: one data set from D2a, the same coefficient under six vcov arguments.
set.seed(621); d_open <- gen_did(50)()
write.csv(d_open, file.path(SCR, "opening_draw.csv"), row.names = FALSE)
f_open <- feols(y ~ d | state + year, data = d_open)
open_specs <- list(
  iid       = list(vcov = "iid",         code = 'vcov = "iid"',        label = "IID (fixest 0.13+ default)"),
  hetero    = list(vcov = "hetero",      code = 'vcov = "hetero"',     label = "HC1"),
  stateyear = list(vcov = ~state^year,   code = "vcov = ~state^year",  label = "Cluster by state-year"),
  twoway    = list(vcov = ~state + year, code = "vcov = ~state + year", label = "Two-way: state and year"),
  state     = list(vcov = ~state,        code = "vcov = ~state",       label = "Cluster by state (fixest <= 0.12 default)"),
  dk        = list(vcov = DK(4) ~ year,  code = "vcov = DK(4) ~ year", label = "Driscoll-Kraay, 4 lags")
)
opening <- list(
  coef = unname(coef(f_open)["d"]), n_obs = nrow(d_open), states = 50, years = T2,
  treated_states = length(unique(d_open$state[d_open$d == 1])),
  estimators = lapply(names(open_specs), function(k) list(
    key = k, label = open_specs[[k]]$label, code = open_specs[[k]]$code,
    se = unname(se(f_open, vcov = open_specs[[k]]$vcov)["d"]),
    p  = unname(pvalue(f_open, vcov = open_specs[[k]]$vcov)["d"]),
    ci_low  = unname(confint(f_open, vcov = open_specs[[k]]$vcov)["d", 1]),
    ci_high = unname(confint(f_open, vcov = open_specs[[k]]$vcov)["d", 2])
  ))
)

# ---------------------------------------------------------------- D3: two non-nested dimensions
# 50 regions x 30 industries, one cell each. The regressor and the error both carry a
# region component and an industry component.
R3 <- 50; I3 <- 30
gen_twoway <- function() {
  g <- expand.grid(region = seq_len(R3), industry = seq_len(I3))
  x <- rnorm(R3)[g$region] + rnorm(I3)[g$industry] + rnorm(nrow(g))
  y <- rnorm(R3, 0, 0.5)[g$region] + rnorm(I3, 0, 0.5)[g$industry] + rnorm(nrow(g))
  data.frame(y, x, g)
}
results$twoway <- run_design("D3 two-way", 631, gen_twoway, y ~ x, list(
  hetero   = V("hetero",            "HC1, no clustering", 'vcov = "hetero"', NA),
  region   = V(~region,             "cluster by region", "vcov = ~region", NA),
  industry = V(~industry,           "cluster by industry", "vcov = ~industry", NA),
  twoway   = V(~region + industry,  "two-way: region and industry", "vcov = ~region + industry", NA)
), coef = "x", extra = list(regions = R3, industries = I3))

# ---------------------------------------------------------------- D4: spatial correlation on a lattice
# A 40 x 40 grid of points half a degree apart (about 40-55 km). Regressor and error are
# both Gaussian fields with an exponential covariance of range 150 km, plus white noise.
# "Blocks" are 25 arbitrary 8 x 8 administrative regions drawn over the grid.
K4 <- 40; RANGE_KM <- 150
grid <- expand.grid(i = 0:(K4 - 1), j = 0:(K4 - 1))
grid$lat <- 30 + 0.5 * grid$i; grid$lon <- -110 + 0.5 * grid$j
grid$block <- (grid$i %/% 8) * 5 + (grid$j %/% 8) + 1
haversine <- function(lat, lon) {
  to_rad <- pi / 180
  la <- lat * to_rad; lo <- lon * to_rad
  dlat <- outer(la, la, "-"); dlon <- outer(lo, lo, "-")
  a <- sin(dlat / 2)^2 + outer(cos(la), cos(la)) * sin(dlon / 2)^2
  2 * 6371 * asin(pmin(sqrt(a), 1))
}
D4 <- haversine(grid$lat, grid$lon)
L4 <- t(chol(exp(-D4 / RANGE_KM) + diag(1e-8, nrow(D4))))
n4 <- nrow(grid)
gen_spatial <- function() {
  x <- as.vector(L4 %*% rnorm(n4)) + 0.5 * rnorm(n4)
  y <- as.vector(L4 %*% rnorm(n4)) + 0.5 * rnorm(n4)
  data.frame(y, x, lat = grid$lat, lon = grid$lon, block = grid$block)
}
results$spatial <- run_design("D4 spatial", 641, gen_spatial, y ~ x, list(
  hetero    = V("hetero",                  "HC1, no clustering", 'vcov = "hetero"', NA),
  block     = V(~block,                    "cluster by 25 arbitrary blocks", "vcov = ~block", NA),
  conley100 = V(conley(100) ~ lat + lon,   "Conley, 100 km cutoff", "vcov = conley(100) ~ lat + lon", NA),
  conley300 = V(conley(300) ~ lat + lon,   "Conley, 300 km cutoff", "vcov = conley(300) ~ lat + lon", NA),
  conley600 = V(conley(600) ~ lat + lon,   "Conley, 600 km cutoff", "vcov = conley(600) ~ lat + lon", NA)
), coef = "x", extra = list(points = n4, spacing_deg = 0.5, range_km = RANGE_KM, blocks = 25))

# ---------------------------------------------------------------- D5: a panel with persistent common shocks
# 50 units x 400 periods (a monthly panel). Two independent common AR(1) factors (rho 0.7), one in the error and
# one in the regressor, sharing unit-specific loadings, so the score is correlated across
# units within a period and across periods, with no bias. Unit and period fixed effects.
N5 <- 50; T5 <- 400; RHO5 <- 0.7
gen_common <- function() {
  id <- rep(seq_len(N5), each = T5); time <- rep(seq_len(T5), times = N5)
  f <- ar1(T5, RHO5, 1)[time]; g <- ar1(T5, RHO5, 1)[time]
  lam <- rnorm(N5, 1, 0.5)[id]; gam <- lam   # units exposed to one shock are exposed to the other
  w <- as.vector(replicate(N5, ar1(T5, 0.5, 1)))
  x <- gam * g + w
  y <- rnorm(N5, 0, 0.5)[id] + lam * f + rnorm(N5 * T5)
  data.frame(y, x, id, time)
}
results$common <- run_design("D5 common shock", 651, gen_common, y ~ x | id + time, list(
  unit   = V(~id,                 "cluster by unit", "vcov = ~id", NA),
  nw     = V(NW(8) ~ id + time,   "Newey-West within unit, 8 lags", "vcov = NW(8) ~ id + time", NA),
  twoway = V(~id + time,          "two-way: unit and period", "vcov = ~id + time", NA),
  dk     = V(DK(8) ~ time,        "Driscoll-Kraay, 8 lags", "vcov = DK(8) ~ time", NA)
), coef = "x", extra = list(units = N5, periods = T5, rho = RHO5))

out <- list(
  fixest_version = as.character(packageVersion("fixest")),
  r_version = paste(R.version$major, R.version$minor, sep = "."),
  reps = REPS, alpha = ALPHA,
  ssc = "K.adj = TRUE, K.fixef = 'nonnested', G.adj = TRUE, G.df = 'min', t.df = 'min' (fixest defaults)",
  opening = opening,
  designs = results
)
write_json(out, file.path(SCR, "sim_results.json"), auto_unbox = TRUE, digits = 10, pretty = TRUE, na = "null")
cat("wrote", file.path(SCR, "sim_results.json"), "\n")
