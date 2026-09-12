## verify.R -- R `survey` oracle for the ch3lab hand-coded SDR (CONTRACT section 6).
##
## Order of operations:
##   1. python build.py            (writes _scratch/verify_targets.json)
##   2. Rscript verify.R           (this file; writes _scratch/verify_R.json)
##   3. python build.py            (records the comparison in artifacts/manifest.json)
##
##   "C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe" verify.R
##
## Independent of build.py by construction: R reads the two IPUMS parquet files
## itself, applies the universe filter itself, joins the person replicate weights
## itself, and lets `survey` compute the SDR variance. Only the list of states and
## pairs to check comes from build.py.

options(survey.lonely.psu = "fail", warn = 1)
suppressPackageStartupMessages({
  library(arrow)
  library(dplyr)
  library(survey)
  library(jsonlite)
})

args <- commandArgs(trailingOnly = FALSE)
self <- sub("^--file=", "", args[grep("^--file=", args)])
here <- if (length(self)) dirname(normalizePath(self)) else getwd()
ipums <- normalizePath(file.path(here, "..", "..", ".."))
data_path <- file.path(ipums, "analysis", "usa", "acs", "part_2020_2024.parquet")
repwt_path <- file.path(ipums, "analysis", "usa", "acs_repwt", "part_2020_2024.parquet")

tg <- fromJSON(file.path(here, "_scratch", "verify_targets.json"))
states <- as.integer(tg$states)
pairs <- tg$pairs                     # matrix, one row per pair of FIPS codes
smp <- as.integer(tg$sample)
amin <- as.integer(tg$age_min)
amax <- as.integer(tg$age_max)
n_reps <- as.integer(tg$n_reps)
## Second table (pass 2): the same estimand for adults 55-64 in a few named states.
extra <- tg$extra
xstates <- if (is.null(extra)) integer(0) else as.integer(extra$states)
all_states <- sort(union(states, xstates))

t0 <- Sys.time()

## Universe: civilian noninstitutionalized adults 19-64 (see build.py):
## drop institutional group quarters (GQ = 3) and the Armed Forces (EMPSTATD 13-15).
d <- open_dataset(data_path) |>
  filter(SAMPLE == smp, STATEFIP %in% all_states, AGE >= amin, AGE <= amax, GQ != 3L) |>
  select(SAMPLE, SERIAL, PERNUM, STATEFIP, AGE, EMPSTATD, PERWT, uninsured) |>
  collect()
d <- d[is.na(d$EMPSTATD) | !(d$EMPSTATD %in% c(13, 14, 15)), ]
stopifnot(!anyNA(d$uninsured))

serials <- unique(d$SERIAL)
rw <- open_dataset(repwt_path) |>
  filter(SAMPLE == smp, SERIAL %in% serials) |>
  select(SAMPLE, SERIAL, PERNUM, starts_with("REPWTP")) |>
  collect()

for (k in c("SAMPLE", "SERIAL", "PERNUM")) {
  d[[k]] <- as.numeric(d[[k]])
  rw[[k]] <- as.numeric(rw[[k]])
}
rep_cols <- sprintf("REPWTP%d", seq_len(n_reps))
stopifnot(all(rep_cols %in% names(rw)))
x <- merge(as.data.frame(d), as.data.frame(rw), by = c("SAMPLE", "SERIAL", "PERNUM"))
stopifnot(nrow(x) == nrow(d))                         # every universe person has replicates
x <- x[order(x$STATEFIP, x$SERIAL, x$PERNUM), ]
x$uninsured <- as.numeric(x$uninsured)
for (k in rep_cols) x[[k]] <- as.numeric(x[[k]])
t_read <- as.numeric(difftime(Sys.time(), t0, units = "secs"))

## Two equivalent declarations of ACS successive-difference replication.
des_sdr <- svrepdesign(data = x, weights = ~PERWT, repweights = x[, rep_cols],
                       type = "successive-difference", combined.weights = TRUE, mse = TRUE)
des_oth <- svrepdesign(data = x, weights = ~PERWT, repweights = x[, rep_cols],
                       type = "other", scale = 4 / n_reps, rscales = rep(1, n_reps),
                       combined.weights = TRUE, mse = TRUE)

b_sdr <- svyby(~uninsured, ~STATEFIP, des_sdr, svymean, covmat = TRUE)
b_oth <- svyby(~uninsured, ~STATEFIP, des_oth, svymean, covmat = TRUE)
est <- coef(b_sdr)
se_sdr <- SE(b_sdr)
se_oth <- SE(b_oth)
V <- vcov(b_sdr)
names(se_sdr) <- names(est)
names(se_oth) <- names(est)

## The second table: a domain of the same replicate design (subset() keeps every replicate).
extra_out <- NULL
if (!is.null(extra)) {
  des_old <- subset(des_sdr, AGE >= as.integer(extra$age_min) & AGE <= as.integer(extra$age_max)
                    & STATEFIP %in% xstates)
  b_old <- svyby(~uninsured, ~STATEFIP, des_old, svymean, covmat = TRUE)
  est_o <- coef(b_old)
  se_o <- SE(b_old)
  names(se_o) <- names(est_o)
  xpairs <- extra$pairs
  extra_out <- list(
    age_min = as.integer(extra$age_min), age_max = as.integer(extra$age_max),
    states = lapply(names(est_o), function(s) {
      list(fips = as.integer(s),
           n = sum(x$STATEFIP == as.integer(s) & x$AGE >= as.integer(extra$age_min) & x$AGE <= as.integer(extra$age_max)),
           estimate = unname(est_o[s]), se_successive_difference = unname(se_o[s]))
    }),
    pairs = lapply(seq_len(nrow(xpairs)), function(i) {
      a <- as.character(xpairs[i, 1]); b <- as.character(xpairs[i, 2])
      ct <- svycontrast(b_old, setNames(c(1, -1), c(a, b)))
      list(a = as.integer(a), b = as.integer(b), diff = as.numeric(coef(ct))[1], se_diff = as.numeric(SE(ct))[1])
    }))
}

## Restrict the main comparison to the main target states (the extra states were read only
## for the second table).
keep <- names(est) %in% as.character(states)
est <- est[keep]; se_sdr <- se_sdr[keep]; se_oth <- se_oth[keep]

per_state <- lapply(names(est), function(s) {
  list(fips = as.integer(s),
       n = sum(x$STATEFIP == as.integer(s)),
       estimate = unname(est[s]),
       se_successive_difference = unname(se_sdr[s]),
       se_other_scale_4_80 = unname(se_oth[s]))
})

pair_rows <- lapply(seq_len(nrow(pairs)), function(i) {
  a <- as.character(pairs[i, 1])
  b <- as.character(pairs[i, 2])
  ct <- svycontrast(b_sdr, setNames(c(1, -1), c(a, b)))
  list(a = as.integer(a), b = as.integer(b),
       diff = as.numeric(coef(ct))[1],
       se_diff = as.numeric(SE(ct))[1],            # SE() on a contrast is a 1 x 1 matrix
       se_diff_from_vcov = as.numeric(sqrt(V[a, a] + V[b, b] - 2 * V[a, b])),
       cov_ab = as.numeric(V[a, b]))
})

out <- list(
  engine = paste0("R ", getRversion(), ", survey ", as.character(packageVersion("survey")),
                  ", arrow ", as.character(packageVersion("arrow"))),
  call = "svrepdesign(weights=~PERWT, repweights=REPWTP1-80, type='successive-difference', combined.weights=TRUE, mse=TRUE); svyby(~uninsured, ~STATEFIP, svymean, covmat=TRUE)",
  rows = nrow(x),
  scale = des_sdr$scale,
  rscales_unique = unique(des_sdr$rscales),
  mse = des_sdr$mse,
  degf = degf(des_sdr),
  states = per_state,
  pairs = pair_rows,
  extra = extra_out,
  seconds_read = round(t_read, 1),
  seconds_total = round(as.numeric(difftime(Sys.time(), t0, units = "secs")), 1)
)
write_json(out, file.path(here, "_scratch", "verify_R.json"),
           auto_unbox = TRUE, digits = NA, pretty = TRUE)
cat(sprintf("verify.R: %d rows, %d states, %d pairs, scale=%.4f, degf=%d, %.1fs\n",
            nrow(x), length(est), nrow(pairs), des_sdr$scale, degf(des_sdr), out$seconds_total))
