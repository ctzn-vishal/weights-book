# verify.R -- independent R sentinel checks for Chapters 4-5 (R `survey` 4.5 and `fixest`).
# Reads the analytic sample written by build.py (_scratch/analytic_ch45.parquet: microdata, stays
# in Box) and writes _scratch/r_check.json after every check, which build.py folds into
# manifest.validation.   "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe" verify.R
#
# Two replicate routes, on purpose:
#  * survey::withReplicates with the WLS normal equations (keeps every replicate weight, including
#    the 475 negative SDR entries, exactly as Var = (4/80) sum (b_r - b)^2 requires);
#  * survey::svyglm, the route most users take. glm.fit fits only records with positive weights,
#    so each replicate silently drops the few records whose replicate weight is negative
#    (R warns "NaNs produced"). Its SEs therefore differ slightly from the exact SDR formula.
# The 85-cell fixed-effect svyglm exhausted memory on this machine (R exit 127 at ~5 GB), so the
# cell-FE check uses weighted within-cell demeaning inside withReplicates instead.
suppressPackageStartupMessages({
  library(arrow)
  library(survey)
  library(fixest)
})
options(survey.lonely.psu = "fail", digits = 12)
here <- "C:/Users/Vishal Singh/Box/ipums/book/chapters/ch04-regression/_scratch"
out_file <- file.path(here, "r_check.json")
rw <- paste0("REPWTP", 1:80)
d <- as.data.frame(read_parquet(file.path(here, "analytic_ch45.parquet")))
d$educ4 <- factor(d$educ4, levels = c("Less than HS", "HS", "Some college", "BA+"))
cat("rows:", nrow(d), " negative replicate weights:", sum(as.matrix(d[, rw]) < 0), "\n")

res <- character(0)
flush_json <- function() {
  writeLines(paste0('{"r_version": "', R.version.string, '", "survey": "', as.character(packageVersion("survey")),
                    '", "fixest": "', as.character(packageVersion("fixest")), '", "checks": [',
                    paste(res, collapse = ", "), "]}"), out_file)
}
add <- function(name, est, se, method) {
  res <<- c(res, sprintf('{"check": "%s", "estimate": %.12g, "se": %.12g, "method": "%s"}', name, est, se, method))
  cat(sprintf("%-28s est = %.10f  se = %.10f  [%s]\n", name, est, se, method))
  flush_json()
}

# 1. fixest: point estimates with high-dimensional fixed effects and cluster-robust SEs
f1 <- feols(lnw ~ D + z1 + z2 + z3 + educ4, data = d, weights = ~PERWT, cluster = ~SERIAL)
add("fixest_headline_wls_crhh", coef(f1)[["D"]], se(f1)[["D"]], "fixest CR1 SERIAL")
f2 <- feols(lnw ~ D + z1 + z2 + z3 + educ4, data = d, cluster = ~SERIAL)
add("fixest_headline_ols_crhh", coef(f2)[["D"]], se(f2)[["D"]], "fixest CR1 SERIAL")
f3 <- feols(lnw ~ D + z1 + z2 + z3 + educ4 | OCC + IND + STATEFIP, data = d, weights = ~PERWT, vcov = "hetero")
add("fixest_occind_wls_hetero", coef(f3)[["D"]], se(f3)[["D"]], "fixest hetero")
f4 <- feols(lnw ~ D + z1 + z2 + z3 + educ4 | OCC + IND + STATEFIP, data = d, vcov = "hetero")
add("fixest_occind_ols_hetero", coef(f4)[["D"]], se(f4)[["D"]], "fixest hetero")
rm(f1, f2, f3, f4); invisible(gc())
# 1b. separate regressions within one education level (pass 2: the group where OLS and WLS disagree)
ds <- d[d$educ4 == "Some college", ]
f5 <- feols(lnw ~ D + z1 + z2 + z3, data = ds, weights = ~PERWT, cluster = ~SERIAL)
add("fixest_somecoll_wls_crhh", coef(f5)[["D"]], se(f5)[["D"]], "fixest CR1 SERIAL, educ4 == Some college")
f6 <- feols(lnw ~ D + z1 + z2 + z3, data = ds, cluster = ~SERIAL)
add("fixest_somecoll_ols_crhh", coef(f6)[["D"]], se(f6)[["D"]], "fixest CR1 SERIAL, educ4 == Some college")
f7 <- feols(hw ~ D + z1 + z2 + z3, data = ds, weights = ~PERWT, cluster = ~SERIAL)
add("fixest_somecoll_lev_wls_crhh", coef(f7)[["D"]], se(f7)[["D"]], "fixest CR1 SERIAL, educ4 == Some college, levels")
rm(f5, f6, f7, ds); invisible(gc())

# 2. replicate design (SDR, 80 replicates, scale 4/80, centred at the full-sample estimate)
des <- svrepdesign(data = d[, c("lnw", "hw", "D", "z1", "z2", "z3", "educ4", "cell", "PERWT", rw)],
                   weights = ~PERWT, repweights = "REPWTP[0-9]+", type = "successive-difference",
                   mse = TRUE, combined.weights = TRUE)
cat("scale:", des$scale, " rscales[1]:", des$rscales[1], " degf:", degf(des), "\n")
stopifnot(abs(des$scale - 4 / 80) < 1e-12, degf(des) == 79)
m <- svymean(~D, des)
add("svymean_D", as.numeric(coef(m))[1], sqrt(as.numeric(vcov(m)))[1], "svymean")

# 3. withReplicates with the normal equations (all replicate weights kept)
y <- d$lnw
Xh <- model.matrix(~ D + z1 + z2 + z3 + educ4, d)
jD <- which(colnames(Xh) == "D")
th <- withReplicates(des, function(w, data) {
  b <- solve(crossprod(Xh, w * Xh), crossprod(Xh, w * y))
  b[jD]
})
add("wr_headline_log", as.numeric(coef(th))[1], sqrt(as.numeric(vcov(th)))[1], "withReplicates(normal equations)")
Zc <- cbind(D = d$D, z1 = d$z1, z2 = d$z2, z3 = d$z3)
cellv <- d$cell
th2 <- withReplicates(des, function(w, data) {
  sw <- rowsum(w, cellv)
  idx <- match(cellv, as.numeric(rownames(sw)))
  mz <- rowsum(w * Zc, cellv) / as.vector(sw)
  my <- rowsum(w * y, cellv) / as.vector(sw)
  Zt <- Zc - mz[idx, , drop = FALSE]
  yt <- y - my[idx]
  b <- solve(crossprod(Zt, w * Zt), crossprod(Zt, w * yt))
  b[1]
})
add("wr_cellfe_log", as.numeric(coef(th2))[1], sqrt(as.numeric(vcov(th2)))[1], "withReplicates(within-cell WLS)")
rm(Xh, Zc); invisible(gc())
# 3b. the same replicate route on the some-college subset (subset() of a replicate design keeps the
# domain's rows with all 80 replicate weights; the function receives the subset's weights and data)
des_s <- subset(des, educ4 == "Some college")
th3 <- withReplicates(des_s, function(w, data) {
  Xs <- cbind(1, data$D, data$z1, data$z2, data$z3)
  b <- solve(crossprod(Xs, w * Xs), crossprod(Xs, w * data$lnw))
  b[2]
})
add("wr_somecoll_log", as.numeric(coef(th3))[1], sqrt(as.numeric(vcov(th3)))[1], "withReplicates(normal equations, educ4 == Some college)")
th4 <- withReplicates(des_s, function(w, data) {
  Xs <- cbind(1, data$D, data$z1, data$z2, data$z3)
  b <- solve(crossprod(Xs, w * Xs), crossprod(Xs, w * data$hw))
  b[2]
})
add("wr_somecoll_levels", as.numeric(coef(th4))[1], sqrt(as.numeric(vcov(th4)))[1], "withReplicates(normal equations, educ4 == Some college, levels)")
rm(des_s, th3, th4); invisible(gc())

# 4. svyglm, the usual route (drops records with non-positive replicate weights inside glm.fit)
fit_glm <- function(formula, name) {
  g <- suppressWarnings(svyglm(formula, design = des))
  add(name, coef(g)[["D"]], sqrt(diag(vcov(g)))[["D"]], "svyglm")
  rm(g); invisible(gc())
}
fit_glm(lnw ~ D, "svyglm_raw_log")
fit_glm(lnw ~ D + z1 + z2 + z3 + educ4, "svyglm_headline_log")
fit_glm(hw ~ D + z1 + z2 + z3 + educ4, "svyglm_headline_levels")
cat("wrote", out_file, "\n")
