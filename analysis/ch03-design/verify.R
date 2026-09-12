# verify.R -- R survey 4.5 oracle for Chapter 3 (key ch3).
#   "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe" verify.R
# Re-derives the analytic flags independently from the parquet files (it does not
# read build.py output) and writes _scratch/verify_R_results.csv, which build.py
# folds into artifacts/manifest.json -> validation.
# The global default stays survey.lonely.psu = "fail"; other rules are set only
# inside clearly marked local blocks and restored immediately.

options(survey.lonely.psu = "fail")
suppressPackageStartupMessages({
  library(survey)
  library(arrow)
})

here <- "C:/Users/Vishal Singh/Box/ipums/book/chapters/ch03-design"
out <- data.frame(check = character(), value = character(), stringsAsFactors = FALSE)
add <- function(k, v) {
  out[nrow(out) + 1, ] <<- list(k, if (is.character(v)) v else sprintf("%.17g", as.numeric(v)))
}
with_rule <- function(rule, expr) {
  old <- options(survey.lonely.psu = rule)
  on.exit(options(old))
  force(expr)
}
stamp <- function(tag) message(format(Sys.time(), "%H:%M:%S"), "  ", tag)

# ---------------------------------------------------------------- NHANES Aug 2021-Aug 2023
stamp("NHANES read")
nh <- as.data.frame(read_parquet(
  "C:/Users/Vishal Singh/Box/NHANES/data/processed/nhanes_analysis.parquet",
  col_select = c("SEQN", "CYCLE_YEAR", "SDMVSTRA", "SDMVPSU", "WTMEC2YR", "RIDAGEYR",
                 "RIDEXPRG", "BPQ020", "BPQ150", "BPXOSY1", "BPXOSY2", "BPXOSY3",
                 "BPXODI1", "BPXODI2", "BPXODI3")))
nh <- nh[nh$CYCLE_YEAR == 2021 & !is.na(nh$WTMEC2YR) & nh$WTMEC2YR > 0, ]
sbp <- rowMeans(nh[, c("BPXOSY1", "BPXOSY2", "BPXOSY3")], na.rm = TRUE)
dbp <- rowMeans(nh[, c("BPXODI1", "BPXODI2", "BPXODI3")], na.rm = TRUE)
valid <- !is.nan(sbp) & !is.nan(dbp)
preg <- !is.na(nh$RIDEXPRG) & startsWith(nh$RIDEXPRG, "Yes")
med <- !is.na(nh$BPQ150) & nh$BPQ150 == "Yes"
nh$htn <- as.numeric((valid & (sbp >= 130 | dbp >= 80)) | med)
nh$analytic <- nh$RIDAGEYR >= 18 & !preg & valid
nh$aware <- as.numeric(!is.na(nh$BPQ020) & nh$BPQ020 == "Yes")
nh$aware_known <- !is.na(nh$BPQ020) & nh$BPQ020 %in% c("Yes", "No")
nh$agegrp <- cut(nh$RIDAGEYR, c(-Inf, 39, 59, Inf), labels = c("18-39", "40-59", "60+"))

des <- svydesign(ids = ~SDMVPSU, strata = ~SDMVSTRA, weights = ~WTMEC2YR, nest = TRUE, data = nh)
dA <- subset(des, analytic)
m <- svymean(~htn, dA, deff = "replace")
add("nhanes_prev_n", sum(nh$analytic))
add("nhanes_prev_est", coef(m))
add("nhanes_prev_se", SE(m))
add("nhanes_prev_deff", deff(m))
add("nhanes_prev_df", degf(dA))

dS <- svystandardize(dA, by = ~agegrp, over = ~1,
                     population = c(85671821, 72816615, 45363752))
ma <- svymean(~htn, dS)
add("nhanes_prev_adj_est", coef(ma))
add("nhanes_prev_adj_se", SE(ma))

dW <- subset(des, analytic & htn == 1 & aware_known)
mw <- svymean(~aware, dW, deff = "replace")
add("nhanes_aware_est", coef(mw))
add("nhanes_aware_se", SE(mw))
add("nhanes_aware_deff", deff(mw))
stamp("NHANES done")

# ---------------------------------------------------------------- NHIS 2023 sample adults
nhis <- as.data.frame(read_parquet(
  "C:/Users/Vishal Singh/Box/ipums/analysis/nhis/nhis_core/part_2015_2024.parquet",
  col_select = c("YEAR", "STRATA", "PSU", "SAMPWEIGHT", "ASTATFLG", "HYPERTENEV",
                 "DELAYCOST", "HINOTCOVE", "HEALTH", "AGE", "REGION", "female")))
ad <- nhis[nhis$YEAR == 2023 & !is.na(nhis$ASTATFLG) & nhis$ASTATFLG == 1, ]
ad$hyp <- ifelse(ad$HYPERTENEV %in% 2, 1, ifelse(ad$HYPERTENEV %in% 1, 0, NA))
delay <- ifelse(ad$DELAYCOST %in% 2, 1, ifelse(ad$DELAYCOST %in% 1, 0, NA))
ad$delay0 <- ifelse(is.na(delay), 0, delay)
ad$sparse <- ad$HINOTCOVE %in% 2 & ad$HEALTH %in% 5 & !is.na(delay)
ad$psu_key <- paste(ad$YEAR, ad$STRATA, ad$PSU, sep = "_")   # composite key, per year

dN <- svydesign(ids = ~psu_key, strata = ~STRATA, weights = ~SAMPWEIGHT, nest = TRUE, data = ad)
mh <- svymean(~hyp, dN, na.rm = TRUE, deff = "replace")
add("nhis_hyp_est", coef(mh))
add("nhis_hyp_se", SE(mh))
add("nhis_hyp_deff", deff(mh))
add("nhis_df", degf(dN))

dSp <- subset(dN, sparse)
add("nhis_sparse_n", sum(ad$sparse))
add("nhis_sparse_se", SE(svymean(~delay0, dSp)))
add("nhis_sparse_total_se", SE(svytotal(~delay0, dSp)))
add("nhis_sparse_df", degf(dSp))

sub <- ad[ad$sparse, ]
dF <- svydesign(ids = ~psu_key, strata = ~STRATA, weights = ~SAMPWEIGHT, nest = TRUE, data = sub)
msg <- tryCatch({ svymean(~delay0, dF); "no error" }, error = function(e) conditionMessage(e))
add("nhis_subset_fail_errors", as.numeric(msg != "no error"))
add("nhis_subset_fail_message", msg)
for (rule in c("certainty", "remove", "adjust", "average")) {
  with_rule(rule, {
    add(paste0("nhis_subset_", rule, "_se"), SE(svymean(~delay0, dF)))
    add(paste0("nhis_subset_", rule, "_total_se"), SE(svytotal(~delay0, dF)))
  })
}
# Group contrasts in one sample: uninsured share among sample adults 18-64, Northeast minus
# Midwest (regions share no PSU) and ages 18-29 minus 30-44 (the two age groups share PSUs, so
# the covariance matters). svyby(covmat = TRUE) keeps the covariance; svycontrast uses it.
ad$unins <- ifelse(ad$HINOTCOVE %in% 2, 1, ifelse(ad$HINOTCOVE %in% 1, 0, NA))
ad$wa <- ad$AGE >= 18 & ad$AGE <= 64 & !is.na(ad$unins)
dN <- svydesign(ids = ~psu_key, strata = ~STRATA, weights = ~SAMPWEIGHT, nest = TRUE, data = ad)
dWA <- subset(dN, wa)
mu <- svymean(~unins, dWA)
add("nhis_unins_wa_est", coef(mu))
add("nhis_unins_wa_se", SE(mu))
by_reg <- svyby(~unins, ~REGION, dWA, svymean, covmat = TRUE)
ct <- svycontrast(by_reg, c("1" = 1, "2" = -1))
add("nhis_ne_mw_diff", coef(ct))
add("nhis_ne_mw_se", SE(ct))
add("nhis_ne_mw_df", degf(subset(dWA, REGION %in% c(1, 2))))
by_sex <- svyby(~unins, ~female, dWA, svymean, covmat = TRUE)
cs <- svycontrast(by_sex, c("0" = 1, "1" = -1))          # men minus women
add("nhis_sex_diff", coef(cs))
add("nhis_sex_se", SE(cs))
stamp("NHIS done")

# ---------------------------------------------------------------- BRFSS 2024
br <- as.data.frame(read_parquet(
  "C:/Users/Vishal Singh/Box/BRFSS/BRFSS_2026/cleaned/brfss_multi_rec.parquet",
  col_select = c("iyear", "xststr", "xpsu", "xllcpwt", "xrfhlth")))
b <- br[br$iyear == 2024, ]
rm(br)
b$fp <- ifelse(b$xrfhlth %in% 2, 1, ifelse(b$xrfhlth %in% 1, 0, NA))
stamp("BRFSS read")
# One respondent per PSU: ids = ~1 is exactly that design, with integer unit ids.
# (nest = TRUE would call interaction() over every stratum x PSU-code combination,
# 2,393 x 43,913 levels, and a 457,670-level cluster factor makes every
# per-stratum rowsum() rebuild the level set; check.strata = TRUE would tabulate
# respondents x strata.) All rows stay in the design: na.rm = TRUE then estimates
# the non-missing domain with the full design's PSU counts, as build.py does.
dB <- svydesign(ids = ~1, strata = ~xststr, weights = ~xllcpwt, check.strata = FALSE, data = b)
add("brfss_df", degf(dB))
stamp("BRFSS design")
msg <- tryCatch({ svymean(~fp, dB, na.rm = TRUE); "no error" }, error = function(e) conditionMessage(e))
add("brfss_fail_errors", as.numeric(msg != "no error"))
add("brfss_fail_message", msg)
stamp("BRFSS fail check")
with_rule("adjust", {
  mb <- svymean(~fp, dB, na.rm = TRUE, deff = "replace")
  add("brfss_fp_est", coef(mb))
  add("brfss_fp_se", SE(mb))
  add("brfss_fp_deff", deff(mb))
})
stamp("BRFSS done")

add("r_version", R.version.string)
add("survey_version", as.character(packageVersion("survey")))
write.csv(out, file.path(here, "_scratch", "verify_R_results.csv"), row.names = FALSE)
cat("verify.R wrote", nrow(out), "checks\n")
