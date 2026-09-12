# verify_gender.R -- R `survey` 4.5 sentinel for Chapter 5's gender example (gender_cells.py).
#   "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe" verify_gender.R
# Reads the shared Chapter 4-5 analytic cache (microdata, stays in Box) and writes
# _scratch/r_gender_check.json, which gender_cells.py folds into manifest.validation.
# Two checks: the PERWT-weighted female share (svymean) and the cell-fixed-effect coefficient on
# female with age, age^2 and WFH controls (withReplicates with the within-cell WLS normal equations,
# which keeps every replicate weight including the negative SDR entries; see ../ch04-regression/verify.R).
suppressPackageStartupMessages({ library(arrow); library(survey) })
options(survey.lonely.psu = "fail", digits = 12)
cache <- "C:/Users/Vishal Singh/Box/ipums/book/chapters/ch04-regression/_scratch/analytic_ch45.parquet"
out_dir <- "C:/Users/Vishal Singh/Box/ipums/book/chapters/ch05-hidden-weights/_scratch"
dir.create(out_dir, showWarnings = FALSE)
out_file <- file.path(out_dir, "r_gender_check.json")
rw <- paste0("REPWTP", 1:80)
d <- as.data.frame(read_parquet(cache, col_select = c("lnw", "D", "z1", "z2", "z3", "cell", "PERWT", rw)))
cat("rows:", nrow(d), "\n")
res <- character(0)
flush_json <- function() {
  writeLines(paste0('{"r_version": "', R.version.string, '", "survey": "', as.character(packageVersion("survey")),
                    '", "checks": [', paste(res, collapse = ", "), "]}"), out_file)
}
add <- function(name, est, se, method) {
  res <<- c(res, sprintf('{"check": "%s", "estimate": %.12g, "se": %.12g, "method": "%s"}', name, est, se, method))
  cat(sprintf("%-20s est = %.10f  se = %.10f  [%s]\n", name, est, se, method)); flush_json()
}
des <- svrepdesign(data = d, weights = ~PERWT, repweights = "REPWTP[0-9]+", type = "successive-difference",
                   mse = TRUE, combined.weights = TRUE)
stopifnot(abs(des$scale - 4 / 80) < 1e-12, degf(des) == 79)
m <- svymean(~z3, des)
add("svymean_female", as.numeric(coef(m))[1], sqrt(as.numeric(vcov(m)))[1], "svymean")
y <- d$lnw
Zc <- cbind(female = d$z3, z1 = d$z1, z2 = d$z2, wfh = d$D)
cellv <- d$cell
th <- withReplicates(des, function(w, data) {
  sw <- rowsum(w, cellv)
  idx <- match(cellv, as.numeric(rownames(sw)))
  mz <- rowsum(w * Zc, cellv) / as.vector(sw)
  my <- rowsum(w * y, cellv) / as.vector(sw)
  Zt <- Zc - mz[idx, , drop = FALSE]
  yt <- y - my[idx]
  b <- solve(crossprod(Zt, w * Zt), crossprod(Zt, w * yt))
  b[1]
})
add("wr_cellfe_female", as.numeric(coef(th))[1], sqrt(as.numeric(vcov(th)))[1], "withReplicates(within-cell WLS)")
cat("wrote", out_file, "\n")
