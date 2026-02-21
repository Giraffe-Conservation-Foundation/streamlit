#!/usr/bin/env Rscript
# Residents-Only Mark-Recapture Analysis - Parameterized Version
# Usage: Rscript residents_only_analysis_parameterized.R <data_directory>

library(tidyverse)
library(jsonlite)

# Parse command line arguments
args <- commandArgs(trailingOnly = TRUE)

if (length(args) == 0) {
  # Default to current directory structure
  data_dir <- "secr_data_central_tuli"
} else {
  data_dir <- args[1]
}

# Validate directory exists
if (!dir.exists(data_dir)) {
  cat("Error: Directory", data_dir, "does not exist\n")
  quit(status = 1)
}

cat("======================================================================\n")
cat("RESIDENTS-ONLY MARK-RECAPTURE ANALYSIS\n")
cat("======================================================================\n\n")
cat("Data directory:", data_dir, "\n\n")

# Construct file paths
captures_file <- file.path(data_dir, "spatial_captures.csv")
ch_file <- file.path(data_dir, "capture_history.csv")
output_file <- file.path(data_dir, "residents_only_results.json")

# Check files exist
if (!file.exists(captures_file)) {
  cat("Error: spatial_captures.csv not found in", data_dir, "\n")
  quit(status = 1)
}
if (!file.exists(ch_file)) {
  cat("Error: capture_history.csv not found in", data_dir, "\n")
  quit(status = 1)
}

# Load data
captures <- read_csv(captures_file, show_col_types = FALSE)
ch <- read_csv(ch_file, show_col_types = FALSE)

# Convert dates
captures <- captures %>%
  mutate(date = as.Date(date))

unique_dates <- sort(unique(captures$date))

cat("Total individuals in dataset:", nrow(ch), "\n")
cat("Total encounters:", nrow(captures), "\n")
cat("Survey dates:", paste(unique_dates, collapse=", "), "\n\n")

# Identify residents (seen 2+ times across all occasions)
residents <- ch %>%
  filter(total_captures >= 2)

transients <- ch %>%
  filter(total_captures == 1)

cat("======================================================================\n")
cat("FILTERING TRANSIENTS\n")
cat("======================================================================\n\n")

cat("Capture frequency distribution:\n")
for (i in 1:max(ch$total_captures)) {
  n <- sum(ch$total_captures == i)
  pct <- round(100 * n / nrow(ch), 1)
  cat("  ", i, "capture(s):", n, "individuals (", pct, "%)\n", sep="")
}
cat("\n")

cat("Classification:\n")
cat("  Residents (2+ captures):", nrow(residents), "individuals\n")
cat("  Transients (1 capture):", nrow(transients), "individuals\n\n")

# Filter encounters to residents only
resident_ids <- residents$individual_id
resident_captures <- captures %>%
  filter(individual_id %in% resident_ids)

cat("Filtered dataset:\n")
cat("  Residents:", length(resident_ids), "individuals\n")
cat("  Encounters:", nrow(resident_captures), "\n\n")

# Bailey's Triple Catch on residents (first 3 days)
cat("======================================================================\n")
cat("BAILEY'S TRIPLE CATCH (Residents Only)\n")
cat("======================================================================\n\n")

# Get individuals per day
day1_ids <- resident_captures %>%
  filter(date == unique_dates[1]) %>%
  pull(individual_id) %>%
  unique()

day2_ids <- resident_captures %>%
  filter(date == unique_dates[2]) %>%
  pull(individual_id) %>%
  unique()

day3_ids <- resident_captures %>%
  filter(date == unique_dates[3]) %>%
  pull(individual_id) %>%
  unique()

# Calculate statistics
n1 <- length(day1_ids)
n2 <- length(day2_ids)
n3 <- length(day3_ids)
m12 <- length(intersect(day1_ids, day2_ids))
m13 <- length(intersect(day1_ids, day3_ids))
m23 <- length(intersect(day2_ids, day3_ids))
m123 <- length(intersect(intersect(day1_ids, day2_ids), day3_ids))

cat("Sample statistics (residents only):\n")
cat("  Day 1 (", as.character(unique_dates[1]), "): ", n1, " individuals\n", sep="")
cat("  Day 2 (", as.character(unique_dates[2]), "): ", n2, " individuals\n", sep="")
cat("  Day 3 (", as.character(unique_dates[3]), "): ", n3, " individuals\n", sep="")
cat("  Recaptures 1&2:", m12, "\n")
cat("  Recaptures 1&3:", m13, "\n")
cat("  Recaptures 2&3:", m23, "\n")
cat("  All 3 days:", m123, "\n\n")

# Chapman's estimator for closed population
if (m23 > 0) {
  M <- n1 + n2 - m12  # Number marked by end of day 2
  n <- n3             # Sample size day 3
  m <- m23            # Recaptures on day 3
  
  # Chapman's estimator
  N_chapman <- ((M + 1) * (n + 1)) / (m + 1) - 1
  
  # Standard error (Seber 1982)
  se_chapman <- sqrt(((M + 1) * (n + 1) * (M - m) * (n - m)) / 
                     ((m + 1)^2 * (m + 2)))
  
  # 95% confidence interval (normal approximation)
  ci_lower <- N_chapman - 1.96 * se_chapman
  ci_upper <- N_chapman + 1.96 * se_chapman
  
  cat("Chapman's estimator (residents only):\n")
  cat("  N =", round(N_chapman, 1), "\n")
  cat("  SE =", round(se_chapman, 1), "\n")
  cat("  95% CI: (", round(ci_lower, 1), ",", round(ci_upper, 1), ")\n\n")
  
  # Add back transients for total population estimate
  N_total <- N_chapman + nrow(transients)
  
  cat("======================================================================\n")
  cat("TOTAL POPULATION ESTIMATE\n")
  cat("======================================================================\n\n")
  
  cat("Approach: Core residents + transients\n\n")
  cat("  Resident estimate:", round(N_chapman, 1), "\n")
  cat("  Transient count:", nrow(transients), "\n")
  cat("  Total estimate: N =", round(N_total, 1), "\n\n")
  
  # Save results
  results <- list(
    location = basename(data_dir),
    method = "Bailey Triple Catch - Residents Only",
    approach = "residents_only",
    total_individuals = nrow(ch),
    residents = nrow(residents),
    transients = nrow(transients),
    sample_statistics = list(
      n1 = n1,
      n2 = n2,
      n3 = n3,
      m12 = m12,
      m13 = m13,
      m23 = m23,
      m123 = m123
    ),
    resident_estimate = list(
      N = round(N_chapman, 1),
      SE = round(se_chapman, 1),
      CI_lower = round(ci_lower, 1),
      CI_upper = round(ci_upper, 1)
    ),
    total_estimate = list(
      N = round(N_total, 1),
      note = "Residents + all transients"
    )
  )
  
  write_json(results, output_file, auto_unbox = TRUE, pretty = TRUE)
  
  cat("✓ Results saved to", output_file, "\n\n")
  
  cat("======================================================================\n")
  
} else {
  cat("⚠ No recaptures between days 2 and 3 among residents\n")
  cat("Cannot calculate population estimate\n")
  quit(status = 1)
}
