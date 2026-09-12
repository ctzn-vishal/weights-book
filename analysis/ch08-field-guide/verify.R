# verify.R: R `survey` sentinel checks for Chapter 7 (CONTRACT section 6).
#
#   Rscript verify.R <box_root> <snippet_dir>
#
# Sources the chapter's R declaration snippets against the book's store, checks
# two documented failure modes (PSU nesting in NHIS, lonely PSUs in BRFSS), and
# checks survey's successive-difference constant on synthetic replicate weights.
# Prints one "tag|field|value" line per result; build.py parses them into
# manifest.validation and compares them with the Python (svy) results.
suppressMessages({
  library(survey)
  library(arrow)
})
args <- commandArgs(trailingOnly = TRUE)
box <- args[1]
snip <- args[2]
setwd(box)

clean <- function(x) gsub("[\r\n|]+", " ", x)
out <- function(tag, field, value) {
  cat(sprintf("%s|%s|%s\n", tag, field, clean(format(value, digits = 15))))
}
out("env", "R", R.version.string)
out("env", "survey", as.character(packageVersion("survey")))
out("env", "dplyr", requireNamespace("dplyr", quietly = TRUE))
options(survey.lonely.psu = "fail")

run_snip <- function(tag, file) {
  env <- new.env()
  t0 <- Sys.time()
  res <- tryCatch(source(file.path(snip, file), local = env)$value, error = function(e) e)
  if (inherits(res, "error")) {
    out(tag, "error", conditionMessage(res))
    return(invisible(NULL))
  }
  out(tag, "est", unname(coef(res)[1]))
  out(tag, "se", unname(SE(res)[1]))
  if (!is.null(env$des)) out(tag, "degf", degf(env$des))
  out(tag, "seconds", round(as.numeric(difftime(Sys.time(), t0, units = "secs")), 1))
}

# 1. NHIS 2024: PSU codes repeat across strata, so svydesign stops without nest = TRUE
d <- read_parquet("ipums/analysis/nhis/nhis_core/part_2015_2024.parquet",
                  col_select = c("YEAR", "STRATA", "PSU", "SAMPWEIGHT"))
d <- d[d$YEAR == 2024, ]
msg <- tryCatch({
  svydesign(ids = ~PSU, strata = ~STRATA, weights = ~SAMPWEIGHT, data = d)
  "no error"
}, error = function(e) conditionMessage(e))
out("nhis_nest", "message", msg)
run_snip("nhis", "nhis.R")

# 2. NHANES August 2021-August 2023
run_snip("nhanes", "nhanes.R")

# 3. BRFSS 2024: with the R default lonely.psu = "fail", the full-file design stops
b <- read_parquet("BRFSS/BRFSS_2026/cleaned/brfss_multi_rec.parquet",
                  col_select = c("iyear", "xststr", "xpsu", "xllcpwt", "Health"))
b <- b[b$iyear == 2024, ]
b$fairpoor <- as.numeric(b$Health == "Poor")
options(survey.lonely.psu = "fail")
msg <- tryCatch({
  des <- svydesign(ids = ~xpsu, strata = ~xststr, weights = ~xllcpwt, nest = TRUE, data = b)
  svymean(~fairpoor, des, na.rm = TRUE)
  "no error"
}, error = function(e) conditionMessage(e))
out("brfss_fail", "message", msg)
rm(b)
run_snip("brfss", "brfss.R")  # the snippet sets survey.lonely.psu = "adjust", as CDC's example does
options(survey.lonely.psu = "fail")

# 4. ATUS 2024, weights only
run_snip("atus", "atus.R")

# 5. CPS ASEC 2025, full replicate file
run_snip("asec", "asec.R")

# 5b. Weights-only comparators (added 2026-09-12): the same weighted shares with the
#     design variables dropped, for the "if you get it wrong" facts of NHANES and BRFSS.
d <- read_parquet("NHANES/data/processed/nhanes_analysis.parquet",
                  col_select = c("CYCLE_YEAR", "WTMEC2YR", "RIDAGEYR", "htn_measured"))
d <- d[d$CYCLE_YEAR == 2021 & d$RIDAGEYR >= 18 & d$WTMEC2YR > 0 & !is.na(d$htn_measured), ]
res <- svymean(~htn_measured, svydesign(ids = ~1, weights = ~WTMEC2YR, data = d))
out("nhanes_wonly", "est", unname(coef(res)[1]))
out("nhanes_wonly", "se", unname(SE(res)[1]))
b <- read_parquet("BRFSS/BRFSS_2026/cleaned/brfss_multi_rec.parquet",
                  col_select = c("iyear", "xllcpwt", "Health"))
b <- b[b$iyear == 2024 & !is.na(b$Health), ]
b$fairpoor <- as.numeric(b$Health == "Poor")
res <- svymean(~fairpoor, svydesign(ids = ~1, weights = ~xllcpwt, data = b))
out("brfss_wonly", "est", unname(coef(res)[1]))
out("brfss_wonly", "se", unname(SE(res)[1]))
rm(b, d)

# 6. Synthetic SDR frames: survey's successive-difference type applies 4/R with df = R - 1
set.seed(20260910)
for (R in c(80, 160)) {
  n <- 600
  s <- data.frame(y = rbinom(n, 1, 0.3), w = runif(n, 50, 150))
  for (r in 1:R) s[[paste0("REPWTP", r)]] <- s$w * sample(c(0.3, 1.7, 1), n, replace = TRUE)
  th <- sum(s$w * s$y) / sum(s$w)
  thr <- sapply(1:R, function(r) {
    wr <- s[[paste0("REPWTP", r)]]
    sum(wr * s$y) / sum(wr)
  })
  des <- svrepdesign(data = s, weights = ~w, repweights = "^REPWTP[0-9]+$",
                     type = "successive-difference", mse = TRUE)
  tag <- paste0("sdr", R)
  out(tag, "se_survey", unname(SE(svymean(~y, des))[1]))
  out(tag, "se_hand", sqrt(4 / R * sum((thr - th)^2)))
  out(tag, "scale", des$scale)
  out(tag, "degf", degf(des))
}
out("done", "ok", TRUE)
