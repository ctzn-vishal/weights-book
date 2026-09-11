# verify.R -- independent R checks of Chapter 6 (ch6) headline numbers.
#
#   "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe" verify.R
#
# Run after build.py (it reads _scratch/py_targets.json and _scratch/design_states.csv),
# then rerun build.py to embed _scratch/r_validation.json in artifacts/manifest.json.
# Persons are read straight from the analysis layer, not from the Python cache.
options(survey.lonely.psu = "fail", warn = 1)
suppressPackageStartupMessages({
  library(arrow); library(dplyr); library(data.table); library(fixest); library(survey); library(jsonlite)
})
here <- "C:/Users/Vishal Singh/Box/ipums/book/chapters/ch06-clustering"
acs  <- "C:/Users/Vishal Singh/Box/ipums/analysis/usa/acs"
rep  <- "C:/Users/Vishal Singh/Box/ipums/analysis/usa/acs_repwt"
tg <- fromJSON(file.path(here, "_scratch", "py_targets.json"))
ds <- fread(file.path(here, "_scratch", "design_states.csv"))
checks <- list()
add <- function(check, python, r, tol, rel = FALSE, note = "") {
  d <- if (rel) abs(r / python - 1) else abs(r - python)
  checks[[length(checks) + 1]] <<- list(check = check, python = python, r = r,
                                        diff = d, tolerance = tol, relative = rel, pass = d < tol, note = note)
}

cols <- c("YEAR", "SAMPLE", "SERIAL", "PERNUM", "CLUSTER", "STATEFIP", "AGE", "POVERTY", "PERWT", "uninsured")
P <- rbindlist(lapply(c("part_2010_2014.parquet", "part_2015_2019.parquet"), function(p) {
  open_dataset(file.path(acs, p)) |>
    select(all_of(cols)) |>
    filter(YEAR >= 2011, YEAR <= 2019, AGE >= 19, AGE <= 64, POVERTY >= 1, POVERTY <= 138) |>
    collect() |> as.data.table()
}))
cat("persons 2011-2019:", nrow(P), "\n")
D <- P[STATEFIP %in% ds$STATEFIP]
D[, treat := as.integer(STATEFIP %in% ds[treat == 1]$STATEFIP)]
D[, Dv := treat * as.integer(YEAR >= 2014)]
add("design records (R count vs Python)", tg$n_design, nrow(D), 0.5)

# ---- person-level WLS with state and year fixed effects: coefficient, HC1, CRV1 household, CRV1 state
m <- feols(uninsured ~ Dv | STATEFIP + YEAR, data = D, weights = ~PERWT, vcov = "hetero")
b <- unname(coef(m)["Dv"]) * 100
add("coefficient (points): fixest vs pyfixest", tg$beta_points, b, 1e-6)
add("HC1 SE (points): fixest vs pyfixest", tg$se_hc1_points, unname(se(m)["Dv"]) * 100, 1e-4, rel = TRUE)
add("CRV1 SE by state (points): fixest vs pyfixest", tg$se_state_points,
    unname(se(summary(m, cluster = ~STATEFIP))["Dv"]) * 100, 1e-4, rel = TRUE)
add("CRV1 SE by ACS household cluster (points): fixest vs pyfixest", tg$se_household_points,
    unname(se(summary(m, cluster = ~CLUSTER))["Dv"]) * 100, 1e-4, rel = TRUE)

# ---- CV3: leave-one-state-out jackknife on the state-year cells, (G-1)/G centring at the estimate
cells <- D[, .(W = sum(PERWT), ybar = sum(PERWT * uninsured) / sum(PERWT)), by = .(STATEFIP, YEAR, Dv)]
bc <- unname(coef(feols(ybar ~ Dv | STATEFIP + YEAR, data = cells, weights = ~W))["Dv"])
add("two-stage identity in R: cell WLS coefficient equals person WLS coefficient (points)", b, bc * 100, 1e-8)
G <- uniqueN(cells$STATEFIP)
bj <- sapply(sort(unique(cells$STATEFIP)), function(s)
  unname(coef(feols(ybar ~ Dv | STATEFIP + YEAR, data = cells[STATEFIP != s], weights = ~W))["Dv"]))
add("CV3 jackknife SE by state (points)", tg$se_cv3_points, sqrt((G - 1) / G * sum((bj - bc)^2)) * 100, 1e-6)

# ---- SDR, stage one: survey package on two sentinel 2019 cells (smallest and largest design cells)
for (k in seq_len(nrow(tg$sentinel_cells))) {
  sc <- tg$sentinel_cells[k, ]
  cellp <- P[STATEFIP == sc$STATEFIP & YEAR == sc$YEAR]
  smp <- unique(cellp$SAMPLE); stopifnot(length(smp) == 1)
  serials <- unique(cellp$SERIAL)
  rw <- open_dataset(file.path(rep, "part_2015_2019.parquet")) |>
    select(all_of(c("SAMPLE", "SERIAL", "PERNUM", paste0("REPWTP", 1:80)))) |>
    filter(SAMPLE == smp, SERIAL %in% serials) |> collect() |> as.data.table()
  x <- merge(cellp, rw, by = c("SAMPLE", "SERIAL", "PERNUM"))
  stopifnot(nrow(x) == nrow(cellp))
  des <- svrepdesign(data = x, weights = ~PERWT, repweights = "REPWTP[0-9]+",
                     type = "successive-difference", mse = TRUE)
  est <- svymean(~uninsured, des)
  add(sprintf("stage-one share, state %d, %d (survey::svrepdesign SDR)", sc$STATEFIP, sc$YEAR), sc$est, unname(coef(est)), 1e-10)
  add(sprintf("stage-one SDR SE, state %d, %d (scale 4/80, mse centring)", sc$STATEFIP, sc$YEAR), sc$se,
      unname(SE(est)), 1e-8, rel = TRUE, note = sprintf("n = %d", nrow(x)))
}

# ---- SDR, stage two: re-estimate the coefficient on each replicate's cell means (states fixed)
ra <- as.data.table(read_parquet(file.path(here, "_scratch", "rep_state_year_2011_2019.parquet")))
ra <- ra[STATEFIP %in% ds$STATEFIP]
ra[, Dv := as.integer(STATEFIP %in% ds[treat == 1]$STATEFIP) * as.integer(YEAR >= 2014)]
br <- sapply(0:80, function(i) {
  dd <- data.table(STATEFIP = ra$STATEFIP, YEAR = ra$YEAR, Dv = ra$Dv,
                   y = ra[[paste0("s", i)]] / ra[[paste0("w", i)]], w = ra[[paste0("w", i)]])
  unname(coef(feols(y ~ Dv | STATEFIP + YEAR, data = dd, weights = ~w))["Dv"])
})
add("SDR SE of the coefficient, states fixed (points)", tg$se_sdr_points, sqrt(4 / 80 * sum((br[-1] - br[1])^2)) * 100, 1e-6,
    note = "replicate aggregates from build.py; regression re-derived in fixest")

out <- list(python_beta_points = tg$beta_points, r_version = R.version.string,
            packages = list(fixest = as.character(packageVersion("fixest")), survey = as.character(packageVersion("survey")),
                            arrow = as.character(packageVersion("arrow"))),
            checks = checks)
write_json(out, file.path(here, "_scratch", "r_validation.json"), auto_unbox = TRUE, digits = NA, pretty = TRUE)
for (ch in checks) cat(sprintf("%-5s %s | py %.10g | R %.10g\n", ifelse(ch$pass, "PASS", "FAIL"), ch$check, ch$python, ch$r))
