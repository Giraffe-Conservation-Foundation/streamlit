#!/usr/bin/env Rscript
# =============================================================================
# Multi-Model Spatially Explicit Capture-Recapture (SECR) Analysis
# Uses Murray Efford's 'secr' package (CRAN) — no GitHub compilation needed
#
# Model comparison across:
#   - Detection functions : HN (half-normal), HR (hazard-rate), EX (exponential)
#   - Density            : D~1 (constant), D~habitat (if mask covariate supplied)
#   - g0 / lambda0       : constant, time (~t), behavioural response (~b)
#
# Usage:
#   Rscript secr_multi_model.R <data_directory> <output_directory> [models_json]
#
# data_directory must contain:
#   captures.csv  — Session, ID, Occasion, Detector  (secr capthist format)
#   traps.csv     — Detector, x, y                   (header row required)
#
# Optional:
#   mask.csv      — x, y [, habitat, ...]             (habitat mask covariates)
# =============================================================================

options(warn = 1)   # print warnings as they occur

# ----- 0. Package loading -----------------------------------------------------
invisible(tryCatch({
  suppressPackageStartupMessages({
    library(secr)
    library(jsonlite)
  })
  cat("✓ secr", as.character(packageVersion("secr")), "loaded\n")
  cat("✓ jsonlite loaded\n\n")
}, error = function(e) {
  cat("✗ ERROR: Missing required R packages\n")
  cat("  Error details:", conditionMessage(e), "\n\n")
  cat("  Fix: in R, run:\n")
  cat("    install.packages(c('secr', 'jsonlite'))\n\n")
  quit(status = 1)
}))

# ----- 1. Arguments -----------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 2) {
  cat("Usage: Rscript secr_multi_model.R <data_dir> <output_dir> [models_json]\n")
  quit(status = 1)
}

data_dir   <- args[1]
output_dir <- args[2]
models_arg <- if (length(args) >= 3) args[3] else NULL

dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

cat("=============================================================\n")
cat("SECR MULTI-MODEL ANALYSIS  (secr package, M. Efford et al.)\n")
cat("=============================================================\n\n")
cat("Data dir  :", data_dir,   "\n")
cat("Output dir:", output_dir, "\n\n")

# ----- 2. Load data -----------------------------------------------------------
cat("--- Loading data ---\n")

cap_file  <- file.path(data_dir, "captures.csv")
trap_file <- file.path(data_dir, "traps.csv")
mask_file <- file.path(data_dir, "mask.csv")

if (!file.exists(cap_file)) {
  cat("✗ captures.csv not found in", data_dir, "\n"); quit(status = 1)
}
if (!file.exists(trap_file)) {
  cat("✗ traps.csv not found in", data_dir, "\n"); quit(status = 1)
}

captures_df <- read.csv(cap_file, stringsAsFactors = FALSE)
traps_df    <- read.csv(trap_file, stringsAsFactors = FALSE)

cat("  captures: ", nrow(captures_df), "rows\n")
cat("  traps   : ", nrow(traps_df), "rows\n")

# Normalise column names (case-insensitive)
names(captures_df) <- tolower(names(captures_df))
names(traps_df)    <- tolower(names(traps_df))

# Expected captures cols: session, id, occasion, detector
required_cap <- c("session", "id", "occasion", "detector")
missing_cap  <- setdiff(required_cap, names(captures_df))
if (length(missing_cap) > 0) {
  cat("✗ captures.csv missing columns:", paste(missing_cap, collapse = ", "), "\n")
  quit(status = 1)
}

# Expected traps cols: detector, x, y
required_trap <- c("detector", "x", "y")
missing_trap  <- setdiff(required_trap, names(traps_df))
if (length(missing_trap) > 0) {
  cat("✗ traps.csv missing columns:", paste(missing_trap, collapse = ", "), "\n")
  quit(status = 1)
}

# Build secr traps object
trap_obj <- tryCatch(
  read.traps(data = traps_df[, c("x", "y")],
             detector = "proximity",
             row.names = as.character(traps_df$detector)),
  error = function(e) { cat("✗ Failed to create traps object:", conditionMessage(e), "\n"); quit(status = 1) }
)
cat("  ✓ traps object:", nrow(trap_obj), "detectors\n")

# Build capthist object
# secr::make.capthist expects a data frame: Session, ID, Occasion, Detector
cap_for_secr <- data.frame(
  Session  = as.character(captures_df$session),
  ID       = as.character(captures_df$id),
  Occasion = as.integer(captures_df$occasion),
  Detector = as.character(captures_df$detector),
  stringsAsFactors = FALSE
)

capthist <- tryCatch(
  make.capthist(captures = cap_for_secr, traps = trap_obj),
  error = function(e) { cat("✗ Failed to create capthist:", conditionMessage(e), "\n"); quit(status = 1) }
)

n_ind   <- nrow(capthist)
n_occ   <- ncol(capthist)
n_traps <- nrow(traps(capthist))
cat("  ✓ capthist:", n_ind, "individuals,", n_occ, "occasions,", n_traps, "detectors\n\n")

# Optional habitat mask
mask_obj <- NULL
has_habitat_covar <- FALSE

if (file.exists(mask_file)) {
  mask_df <- read.csv(mask_file, stringsAsFactors = FALSE)
  names(mask_df) <- tolower(names(mask_df))
  if (all(c("x", "y") %in% names(mask_df))) {
    mask_covars <- setdiff(names(mask_df), c("x", "y"))
    mask_obj <- tryCatch(
      make.mask(traps = trap_obj,
                buffer  = 5 * median(spacing(trap_obj)),
                type    = "traprect"),
      error = function(e) NULL
    )
    if (!is.null(mask_obj) && length(mask_covars) > 0) {
      has_habitat_covar <- TRUE
      cat("  ✓ Habitat mask with covariates:", paste(mask_covars, collapse = ", "), "\n\n")
    }
  }
}

# If no mask supplied, auto-build a rectangular mask with 4*sigma buffer
# sigma will be estimated; use a generous default buffer (spacing * 4)
if (is.null(mask_obj)) {
  buf_guess <- 4 * median(spacing(trap_obj))
  mask_obj <- make.mask(traps = trap_obj, buffer = buf_guess, type = "traprect")
  cat("  Auto mask: buffer =", round(buf_guess, 0), "m,", nrow(mask_obj), "pixels\n\n")
}

# ----- 3. Define model set ---------------------------------------------------
cat("--- Defining model set ---\n")

# Parse user-supplied model list (JSON array of objects) if provided
user_models <- NULL
if (!is.null(models_arg) && nchar(models_arg) > 2) {
  user_models <- tryCatch(fromJSON(models_arg), error = function(e) NULL)
}

# Default model set: one null model per detection function (fast)
# Full models (time/beh variants) can be added once null fits succeed
default_model_set <- list(
  list(label = "HN.null",   detectfn = "HN", D = ~1, g0 = ~1),
  list(label = "HR.null",   detectfn = "HR", D = ~1, g0 = ~1),
  list(label = "EX.null",   detectfn = "EX", D = ~1, g0 = ~1)
)

# Add habitat density models if mask covariate is available
if (has_habitat_covar) {
  extra_models <- lapply(c("HN", "HR", "EX"), function(df) {
    list(label = paste0(df, ".Dhabitat"), detectfn = df, D = ~habitat, g0 = ~1)
  })
  default_model_set <- c(default_model_set, extra_models)
}

model_set <- default_model_set
cat("  Models to fit:", length(model_set), "\n")
for (m in model_set) cat("   -", m$label, "\n")
cat("\n")

# ----- 4. Fit models ---------------------------------------------------------
cat("=============================================================\n")
cat("FITTING MODELS\n")
cat("=============================================================\n\n")

# Read transient count injected by Python (if present)
transient_file <- file.path(data_dir, "transients.txt")
n_transients   <- 0
if (file.exists(transient_file)) {
  n_transients <- as.integer(readLines(transient_file, n = 1))
  cat(sprintf("  Transients (seen once, added after SECR): %d\n\n", n_transients))
}

fitted_models <- list()
fit_results   <- list()

for (m in model_set) {
  label <- m$label
  cat(sprintf("  %-18s ... ", label))

  # Fit model — suppress warnings (convergence notes etc.) but catch errors
  fit <- tryCatch({
    suppressWarnings(
      secr.fit(
        capthist = capthist,
        model    = list(D = m$D, g0 = m$g0, sigma = ~1),
        mask     = mask_obj,
        detectfn = m$detectfn,
        trace    = FALSE,
        verify   = FALSE
      )
    )
  }, error = function(e) list(.__error__ = conditionMessage(e)))

  # Check for fit failure
  if (is.list(fit) && !is.null(fit$.__error__)) {
    cat("✗ FAILED:", fit$.__error__, "\n")
    next
  }
  if (!inherits(fit, "secr")) {
    # Print whatever is in the list to aid debugging
    fit_names <- names(fit)
    fit_msg   <- if (!is.null(fit_names)) paste(fit_names, collapse=", ") else "(unnamed)"
    fit_msg2  <- tryCatch(as.character(fit[[1]])[1], error=function(e) "")
    cat("\u2717 FAILED: not a secr object [", class(fit)[1], "] names:", fit_msg, "| first:", fit_msg2, "\n")
    next
  }

  # Extract AIC/AICc — AIC.secr returns a data frame with columns:
  # model, detectfn, npar, logLik, AIC, AICc
  aic_row <- tryCatch(
    AIC(fit),
    error = function(e) { cat("✗ AIC error:", conditionMessage(e), "\n"); NULL }
  )
  if (is.null(aic_row)) next

  fitted_models[[label]] <- fit
  fit_results[[label]] <- list(
    label    = label,
    detectfn = m$detectfn,
    D_model  = deparse(m$D),
    g0_model = deparse(m$g0),
    npar     = aic_row$npar[1],
    logLik   = aic_row$logLik[1],
    AIC      = aic_row$AIC[1],
    AICc     = aic_row$AICc[1]
  )

  cat(sprintf("✓  AICc = %9.2f  (logLik = %.2f, k = %d)\n",
              aic_row$AICc[1], aic_row$logLik[1], aic_row$npar[1]))
}

cat("\n")

if (length(fitted_models) == 0) {
  cat("✗ No models completed — check your input data.\n")
  quit(status = 1)
}

# ----- 5. Model comparison table ---------------------------------------------
cat("=============================================================\n")
cat("MODEL RANKING  (AICc)\n")
cat("=============================================================\n\n")

aic_rows <- do.call(rbind, lapply(fit_results, function(r) {
  data.frame(
    model    = r$label,
    detectfn = r$detectfn,
    D_model  = r$D_model,
    g0_model = r$g0_model,
    k        = r$npar,
    logLik   = r$logLik,
    AIC      = r$AIC,
    AICc     = r$AICc,
    stringsAsFactors = FALSE
  )
}))

aic_rows   <- aic_rows[order(aic_rows$AICc), ]
min_aicc   <- min(aic_rows$AICc)
aic_rows$deltaAICc <- aic_rows$AICc - min_aicc
aic_rows$weight    <- exp(-0.5 * aic_rows$deltaAICc) /
                      sum(exp(-0.5 * aic_rows$deltaAICc))
rownames(aic_rows) <- NULL

cat(sprintf("  %-20s  %-4s  %-8s  %-8s  %5s  %9s  %8s  %6s\n",
            "Model", "Det.", "D", "g0", "k", "AICc", "ΔAICc", "w"))
cat(strrep("-", 85), "\n")
for (i in seq_len(nrow(aic_rows))) {
  r <- aic_rows[i, ]
  cat(sprintf("  %-20s  %-4s  %-8s  %-8s  %5d  %9.2f  %8.2f  %6.4f\n",
              r$model, r$detectfn, r$D_model, r$g0_model,
              r$k, r$AICc, r$deltaAICc, r$weight))
}

best_label <- aic_rows[1, "model"]
cat("\n  >>> Best model:", best_label, "<<<\n\n")

# ----- 6. Parameter estimates from best model --------------------------------
cat("=============================================================\n")
cat("BEST MODEL ESTIMATES:", best_label, "\n")
cat("=============================================================\n\n")

best_fit <- fitted_models[[best_label]]

# Predicted parameter values on natural scale
pred <- predict(best_fit)
cat("  Detection parameters:\n")
print(pred)

# Derived abundance & density
cat("\n  Derived abundance (N) and density (D):\n")
derived_est <- tryCatch(derived(best_fit), error = function(e) NULL)
if (!is.null(derived_est)) print(derived_est)

# ----- 7. Population estimate ------------------------------------------------
cat("\n=============================================================\n")
cat("POPULATION ESTIMATE\n")
cat("=============================================================\n\n")

pop_est <- list(
  N_hat   = NA, N_lcl = NA, N_ucl = NA,
  D_hat   = NA, D_lcl = NA, D_ucl = NA,
  sigma   = NA, g0    = NA
)

# Method 1: region.N() — most reliable for abundance within mask
regN <- tryCatch(region.N(best_fit), error = function(e) {
  cat("  region.N() error:", conditionMessage(e), "\n"); NULL
})
if (!is.null(regN)) {
  cat("  region.N() result:\n"); print(regN)
  n_col   <- intersect(c("E.N",     "estimate"), colnames(regN))[1]
  lcl_col <- intersect(c("lcl.E.N", "lcl"),      colnames(regN))[1]
  ucl_col <- intersect(c("ucl.E.N", "ucl"),      colnames(regN))[1]
  if (!is.na(n_col))   pop_est$N_hat <- as.numeric(regN[1, n_col])
  if (!is.na(lcl_col)) pop_est$N_lcl <- as.numeric(regN[1, lcl_col])
  if (!is.na(ucl_col)) pop_est$N_ucl <- as.numeric(regN[1, ucl_col])
  cat("  N from region.N()\n")
} else {
  cat("  region.N() returned NULL, trying derived()\n")
}

# Method 2: derived() — fallback if region.N failed
if (is.na(pop_est$N_hat) && !is.null(derived_est) && "N" %in% rownames(derived_est)) {
  pop_est$N_hat <- derived_est["N", "estimate"]
  pop_est$N_lcl <- derived_est["N", "lcl"]
  pop_est$N_ucl <- derived_est["N", "ucl"]
  cat("  N from derived()\n")
}
if (!is.null(derived_est) && "D" %in% rownames(derived_est)) {
  pop_est$D_hat <- derived_est["D", "estimate"]
  pop_est$D_lcl <- derived_est["D", "lcl"]
  pop_est$D_ucl <- derived_est["D", "ucl"]
}

# Extract g0 and sigma from predictions
if (!is.null(pred)) {
  if ("g0"     %in% rownames(pred)) pop_est$g0    <- pred["g0",    "estimate"]
  if ("sigma"  %in% rownames(pred)) pop_est$sigma <- pred["sigma", "estimate"]
  if ("lambda0" %in% rownames(pred)) pop_est$g0   <- pred["lambda0","estimate"]
}

cat(sprintf("  N_hat=%s  N_lcl=%s  N_ucl=%s\n",
    ifelse(is.na(pop_est$N_hat), "NA", round(pop_est$N_hat, 1)),
    ifelse(is.na(pop_est$N_lcl), "NA", round(pop_est$N_lcl, 1)),
    ifelse(is.na(pop_est$N_ucl), "NA", round(pop_est$N_ucl, 1))))

# ----- 8. Model-averaged N ---------------------------------------------------
ma_n <- pop_est$N_hat  # default to best model
if (nrow(aic_rows) > 1) {
  cat("\n  Model-averaged N\u0302 (all models with weight > 0.001):\n")
  ma_vals <- sapply(aic_rows$model, function(lbl) {
    w  <- aic_rows[aic_rows$model == lbl, "weight"]
    fi <- fitted_models[[lbl]]
    if (is.null(fi)) return(0)
    rn <- tryCatch(region.N(fi), error = function(e) NULL)
    if (!is.null(rn) && "E.N" %in% colnames(rn)) return(w * rn[1, "E.N"])
    d <- tryCatch(derived(fi), error = function(e) NULL)
    if (!is.null(d) && "N" %in% rownames(d)) return(w * d["N", "estimate"])
    return(0)
  })
  ma_n <- sum(ma_vals)
  cat(sprintf("  Model-averaged N̂ = %.1f\n", ma_n))
}

# ----- 9. Export results to JSON & CSV ---------------------------------------
cat("\n=============================================================\n")
cat("EXPORTING RESULTS\n")
cat("=============================================================\n\n")

results_list <- list(
  timestamp        = as.character(Sys.time()),
  package          = paste("secr", as.character(packageVersion("secr"))),
  best_model       = best_label,
  models_fitted    = aic_rows$model,
  model_count      = nrow(aic_rows),
  n_individuals    = n_ind,
  n_occasions      = n_occ,
  n_detectors      = n_traps,
  total_captures   = sum(capthist),
  n_transients     = n_transients,
  population_estimate = pop_est,
  total_N_with_transients = ifelse(is.na(pop_est$N_hat), NA, pop_est$N_hat + n_transients),
  aic_table        = aic_rows,
  model_averaged_N = ma_n,
  model_averaged_N_total = ma_n + n_transients
)

cat(sprintf("  Resident N\u0302 (SECR)  : %.0f\n", ifelse(is.na(pop_est$N_hat), 0, pop_est$N_hat)))
cat(sprintf("  Transients added  : %d\n", n_transients))
cat(sprintf("  TOTAL estimate    : %.0f\n\n", ifelse(is.na(pop_est$N_hat), n_transients, pop_est$N_hat + n_transients)))

json_file <- file.path(output_dir, "secr_results.json")
writeLines(toJSON(results_list, pretty = TRUE, auto_unbox = TRUE), json_file)
cat("  JSON results :", json_file, "\n")

csv_file <- file.path(output_dir, "aic_table.csv")
write.csv(aic_rows, csv_file, row.names = FALSE)
cat("  AIC table CSV:", csv_file, "\n")

# Best model summary text
summary_file <- file.path(output_dir, "best_model_summary.txt")
sink(summary_file)
cat("BEST MODEL:", best_label, "\n\n")
cat("PREDICTED PARAMETERS:\n"); print(pred)
cat("\nDERIVED ESTIMATES:\n"); if (!is.null(derived_est)) print(derived_est)
cat("\nAIC TABLE:\n"); print(aic_rows)
sink()
cat("  Summary text :", summary_file, "\n")

cat("\n✓ SECR analysis complete!\n\n")
