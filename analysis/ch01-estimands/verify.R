# verify.R -- independent R `survey` check of Chapter 1's replicate-weight results.
#
#   Rscript verify.R <out.csv>
#
# Reads CPS ASEC survey year 2022 (calendar-year 2021 income) and its 160 SDR person
# replicate weights, and recomputes the child poverty shares (official and SPM), the
# child official-minus-SPM gap, and the 65+ SPM share with
# survey::svrepdesign(type = "successive-difference", mse = TRUE): scale 4/160,
# variance centred on the full-sample estimate, df = 159. build.py calls this script
# (when R is present) and records the comparison in artifacts/manifest.json.
options(survey.lonely.psu = "fail", warn = 1)
suppressPackageStartupMessages({
  library(arrow)
  library(survey)
})

args <- commandArgs(trailingOnly = TRUE)
out <- if (length(args) >= 1) args[[1]] else "verify_r.csv"
root <- "C:/Users/Vishal Singh/Box/ipums/analysis/cps"
yr <- 2022L

read_year <- function(path, cols) {
  if (requireNamespace("dplyr", quietly = TRUE)) {
    ds <- arrow::open_dataset(path)
    x <- dplyr::collect(dplyr::select(dplyr::filter(ds, YEAR == yr), dplyr::all_of(cols)))
  } else {
    x <- arrow::read_parquet(path, col_select = cols)
    x <- x[x$YEAR == yr, ]
  }
  as.data.frame(x)
}

p <- read_year(file.path(root, "cps_asec", "part_2020_2025.parquet"),
               c("YEAR", "SERIAL", "PERNUM", "AGE", "ASECWT", "POVERTY", "SPMPOV"))
r <- read_year(file.path(root, "cps_asec_repwt", "part_2020_2025.parquet"),
               c("YEAR", "SERIAL", "PERNUM", paste0("REPWTP", 1:160)))
d <- merge(p, r, by = c("YEAR", "SERIAL", "PERNUM"), sort = TRUE)
stopifnot(nrow(d) == nrow(p), nrow(d) == nrow(r))

d$poor_off <- ifelse(is.na(d$POVERTY), NA_real_, as.numeric(d$POVERTY == 10))
d$poor_spm <- ifelse(is.na(d$SPMPOV), NA_real_, as.numeric(d$SPMPOV == 1))

des <- svrepdesign(data = d, weights = ~ASECWT, repweights = "REPWTP[0-9]+",
                   type = "successive-difference", mse = TRUE)
stopifnot(abs(des$scale - 4 / 160) < 1e-12, ncol(des$repweights) == 160)
dfree <- degf(des)

res <- list()
add <- function(name, est, se, n) {
  res[[length(res) + 1]] <<- data.frame(check = name, estimate = est, se = se, n = n, df = dfree)
}

m1 <- svymean(~poor_off, subset(des, AGE < 18 & !is.na(POVERTY)))
add("pov_off_child_2021", coef(m1)[[1]], SE(m1)[[1]], sum(d$AGE < 18 & !is.na(d$POVERTY)))
m2 <- svymean(~poor_spm, subset(des, AGE < 18))
add("pov_spm_child_2021", coef(m2)[[1]], SE(m2)[[1]], sum(d$AGE < 18))
m3 <- svymean(~poor_spm, subset(des, AGE >= 65))
add("pov_spm_65_2021", coef(m3)[[1]], SE(m3)[[1]], sum(d$AGE >= 65))
gap <- withReplicates(des, function(w, data) {
  k <- data$AGE < 18
  o <- k & !is.na(data$POVERTY)
  sum(w[o] * data$poor_off[o]) / sum(w[o]) - sum(w[k] * data$poor_spm[k]) / sum(w[k])
})
add("pov_gap_child_2021", coef(gap)[[1]], SE(gap)[[1]], sum(d$AGE < 18))

out_df <- do.call(rbind, res)
out_df$r_version <- R.version.string
out_df$survey_version <- as.character(packageVersion("survey"))
write.csv(out_df, out, row.names = FALSE)
print(out_df, digits = 12)
