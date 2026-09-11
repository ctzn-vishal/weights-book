# extract_brfss.R -- pull the BRFSS 2024 weighting chain out of the raw CDC file.
#
# Why R: the raw file is an R data frame (readRDS); pyreadr cannot read it
# (LibrdataError: unable to convert string to the requested encoding).
#
# Input : C:/Users/Vishal Singh/Box/BRFSS/BRFSS_2026/raw/2024.rds
#         (LLCP 2024 public file, 457,670 rows x 301 columns). CDC names are
#         lower-cased and the leading "_" becomes "x": _STRWT -> xstrwt,
#         _RAWRAKE -> xrawrake, _WT2RAKE -> xwt2rake, _LLCPWT2 -> xllcpwt2,
#         _LLCPWT -> xllcpwt, _DUALUSE -> xdualuse, _DUALCOR -> xdualcor.
# Output: _data/brfss2024_weights.parquet  (only the columns below; stays in Box)
#         _data/brfss2024_labels.csv       (CDC variable labels, for the notes)
# Run   : "C:/Program Files/R/R-4.6.1/bin/x64/Rscript.exe" extract_brfss.R

suppressPackageStartupMessages(library(arrow))

args <- commandArgs(trailingOnly = FALSE)
here <- dirname(normalizePath(sub("^--file=", "", args[grep("^--file=", args)])))
raw  <- "C:/Users/Vishal Singh/Box/BRFSS/BRFSS_2026/raw/2024.rds"

x <- readRDS(raw)
stopifnot(nrow(x) == 457670L)

keep <- c(
  # record identification and interview timing
  "xstate", "fmonth", "imonth", "iday", "iyear", "dispcode", "seqno", "qstver", "qstlang",
  # design and the weighting chain
  "xststr", "xpsu", "xstrwt", "xrawrake", "xwt2rake", "xdualuse", "xdualcor",
  "xllcpwt2", "xllcpwt",
  # landline-frame screener and phone counts
  "ctelenm1", "pvtresd1", "colghous", "celphon1", "ladult1", "numadult",
  "numhhol4", "numphon4",
  # cell-frame screener
  "cellfon5", "cadult1", "pvtresd3", "cclghous", "cstate1", "landline", "hhadult",
  # cell phones for personal use (both frames)
  "cpdemo1c",
  # outcome
  "menthlth", "xment14d",
  # raking-margin inputs and demographics
  "sexvar", "xsex", "xageg5yr", "xage_g", "xage65yr", "xage80",
  "ximprace", "xracegr3", "xhispanc", "educa", "xeducag", "marital", "renthom1",
  "xmetstat", "xurbstat", "mscode"
)
miss <- setdiff(keep, names(x))
if (length(miss)) stop("columns not in raw file: ", paste(miss, collapse = ", "))

lab_of <- function(k) {
  l <- attr(x[[k]], "label")
  if (is.null(l)) "" else paste(as.character(l), collapse = " ")
}
labs <- data.frame(column = keep, label = vapply(keep, lab_of, ""), stringsAsFactors = FALSE)

y <- x[, keep]
y[] <- lapply(y, function(z) { attributes(z) <- NULL; z })
y$iyear <- as.integer(y$iyear)

dir.create(file.path(here, "_data"), showWarnings = FALSE)
write_parquet(y, file.path(here, "_data", "brfss2024_weights.parquet"))
write.csv(labs, file.path(here, "_data", "brfss2024_labels.csv"), row.names = FALSE)

cat("rows", nrow(y), "cols", ncol(y), "\n")
cat("md5(raw)", unname(tools::md5sum(raw)), "\n")
