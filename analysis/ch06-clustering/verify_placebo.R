# verify_placebo.R -- R fixest check of two placebo regressions from placebo.py (Chapter 6).
#   "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe" verify_placebo.R
# Run after build.py (it reads _scratch/placebo_targets.json), then rerun build.py to embed
# _scratch/r_placebo_validation.json in artifacts/manifest.json. Persons come from the build's own
# cache (_scratch/analytic_2008_2019.parquet; microdata, stays in Box); the design states from
# _scratch/design_states.csv.
options(warn = 1)
suppressPackageStartupMessages({ library(arrow); library(data.table); library(fixest); library(jsonlite) })
here <- "C:/Users/Vishal Singh/Box/ipums/book/chapters/ch06-clustering"
tg <- fromJSON(file.path(here, "_scratch", "placebo_targets.json"), simplifyVector = FALSE)
ds <- fread(file.path(here, "_scratch", "design_states.csv"))
P <- as.data.table(read_parquet(file.path(here, "_scratch", "analytic_2008_2019.parquet"),
                                col_select = c("YEAR", "STATEFIP", "CLUSTER", "PERWT", "uninsured")))
P <- P[YEAR >= 2011 & YEAR <= 2019 & STATEFIP %in% ds$STATEFIP]
comp <- ds[treat == 0]$STATEFIP
checks <- list(); cases <- list()
add <- function(check, python, r, tol, rel = FALSE) {
  d <- if (rel) abs(r / python - 1) else abs(r - python)
  checks[[length(checks) + 1]] <<- list(check = check, python = python, r = r, diff = d, tolerance = tol, relative = rel, pass = d < tol)
}
for (nm in names(tg$cases)) {
  cs <- tg$cases[[nm]]
  T <- unlist(cs$states)
  D <- if (grepl("comparison", nm)) P[STATEFIP %in% comp] else P
  D[, Dp := as.integer(STATEFIP %in% T) * as.integer(YEAR >= 2014)]
  m <- feols(uninsured ~ Dp | STATEFIP + YEAR, data = D, weights = ~PERWT, vcov = "hetero")
  add(paste0("placebo (", nm, "): coefficient (points), fixest vs placebo.py"), cs$beta_points, unname(coef(m)["Dp"]) * 100, 1e-8)
  add(paste0("placebo (", nm, "): HC1 SE (points), fixest vs placebo.py"), cs$se_hc1_points, unname(se(m)["Dp"]) * 100, 1e-4, rel = TRUE)
  add(paste0("placebo (", nm, "): CRV1 SE by state (points), fixest vs placebo.py"), cs$se_state_points,
      unname(se(summary(m, cluster = ~STATEFIP))["Dp"]) * 100, 1e-4, rel = TRUE)
  add(paste0("placebo (", nm, "): CRV1 SE by household (points), fixest vs placebo.py"), cs$se_household_points,
      unname(se(summary(m, cluster = ~CLUSTER))["Dp"]) * 100, 1e-4, rel = TRUE)
  cases[[nm]] <- as.integer(T)
}
out <- list(python_beta_points = tg$beta_points, cases = cases, r_version = R.version.string,
            fixest = as.character(packageVersion("fixest")), checks = checks)
write_json(out, file.path(here, "_scratch", "r_placebo_validation.json"), auto_unbox = TRUE, digits = NA, pretty = TRUE)
for (ch in checks) cat(sprintf("%-5s %s | py %.10g | R %.10g\n", ifelse(ch$pass, "PASS", "FAIL"), ch$check, ch$python, ch$r))
