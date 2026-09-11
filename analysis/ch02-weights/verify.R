# verify.R -- independent R `survey` check of the Chapter 2 BRFSS design-based numbers.
#
# Re-derives, without importing anything from build.py:
#   1. FMD prevalence, Taylor SE, design df, and DEFF (with-replacement SRS reference)
#      under the final weight _LLCPWT
#   2. the same under the within-state 95th-percentile cap (state totals preserved)
# Writes _scratch/r_check.json, which build.py copies into manifest.validation.
#
# Target: adults in the 49 states and DC that released 2024 BRFSS data (no Tennessee);
# Guam, Puerto Rico, and the US Virgin Islands are excluded. Whole jurisdictions are
# dropped before the design is declared; strata nest within jurisdictions, so this removes
# whole strata and leaves the variance contribution of the remaining strata unchanged.
# Item nonresponse on MENTHLTH (77, 99, blank) is a domain: na.rm = TRUE subsets the
# declared design instead of deleting rows before declaring it.
#
# Lonely PSUs: the contract default survey.lonely.psu = "fail" is tried first and is
# EXPECTED to fail -- 109 strata in the analytic file hold exactly one respondent. The
# chapter then uses "adjust" (the rule in CDC's own 2024 R example: a singleton PSU is
# centred at the grand mean, which is conservative), with "remove" as a sensitivity check.
#
# Run: "C:/Program Files/R/R-4.6.1/bin/x64/Rscript.exe" verify.R

suppressPackageStartupMessages({
  library(arrow)
  library(survey)
})

args <- commandArgs(trailingOnly = FALSE)
here <- dirname(normalizePath(sub("^--file=", "", args[grep("^--file=", args)])))

d <- as.data.frame(read_parquet(
  file.path(here, "_data", "brfss2024_weights.parquet"),
  col_select = c("xstate", "xststr", "xpsu", "xllcpwt", "menthlth")
))
d <- d[d$xstate <= 56, ]
d$fmd <- ifelse(d$menthlth == 88, 0,
         ifelse(d$menthlth >= 1 & d$menthlth <= 30, as.numeric(d$menthlth >= 14), NA))

# within-state 95th-percentile cap, rescaled to preserve each state's weight total.
# quantile type 7 = linear interpolation (numpy's default).
cap <- ave(d$xllcpwt, d$xstate, FUN = function(z) quantile(z, 0.95, type = 7, names = FALSE))
wt <- pmin(d$xllcpwt, cap)
d$w_p95 <- wt * ave(d$xllcpwt, d$xstate, FUN = sum) / ave(wt, d$xstate, FUN = sum)

singletons <- sum(table(d$xststr) == 1)

# _PSU is the annual sequence number: every respondent is its own PSU. ids = ~1 declares
# exactly that (and is what CDC's 2024 R example uses); ids = ~xpsu with nest = TRUE gives the
# same variance but made survey 4.5 spend more than 20 CPU-minutes on PSU bookkeeping.
fit <- function(wname, lonely) {
  op <- options(survey.lonely.psu = lonely)
  on.exit(options(op))
  des <- svydesign(ids = ~1, strata = ~xststr, weights = as.formula(paste0("~", wname)),
                   data = d)
  r <- svymean(~fmd, des, na.rm = TRUE, deff = "replace")
  list(estimate = unname(coef(r)[1]), se = unname(SE(r)[1]),
       deff = unname(deff(r)[1]), df = degf(des),
       n = sum(!is.na(d$fmd)), strata = length(unique(d$xststr)))
}

fail_msg <- tryCatch({ fit("xllcpwt", "fail"); "no error" },
                     error = function(e) conditionMessage(e))
r_adj <- fit("xllcpwt", "adjust")
r_rem <- fit("xllcpwt", "remove")
r_p95 <- fit("w_p95", "adjust")

fmt <- function(tag, r) sprintf(
  '  "%s": {"estimate": %.12f, "se": %.12f, "deff": %.8f, "df": %d, "n": %d, "strata": %d}',
  tag, r$estimate, r$se, r$deff, as.integer(r$df), as.integer(r$n), as.integer(r$strata))
esc <- function(s) gsub('"', "'", gsub("[\r\n]+", " ", s))
out <- c("{",
         paste0('  "engine": "R ', R.version$major, ".", R.version$minor,
                ", survey ", as.character(packageVersion("survey")), '",'),
         sprintf('  "singleton_strata": %d,', as.integer(singletons)),
         sprintf('  "fail_rule_message": "%s",', esc(fail_msg)),
         paste0(fmt("fmd_final_adjust", r_adj), ","),
         paste0(fmt("fmd_final_remove", r_rem), ","),
         fmt("fmd_p95_adjust", r_p95),
         "}")
dir.create(file.path(here, "_scratch"), showWarnings = FALSE)
writeLines(out, file.path(here, "_scratch", "r_check.json"))
cat(out, sep = "\n")
