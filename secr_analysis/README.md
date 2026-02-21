# SECR Population Analysis

Spatially-Explicit Capture-Recapture (SECR) and Bailey's Triple Catch analysis for population estimation.

## Overview

This module provides tools for estimating wildlife population size using:

1. **SECR Analysis** - Spatially-explicit capture-recapture with detection functions
2. **Bailey's Triple Catch** - Residents-only population estimation for short-term surveys

## Features

### 🎲 Demo Mode
- Synthetic data generation for testing
- Adjustable parameters (population size, detection probability, spatial scale)
- Educational tool for understanding SECR

### 📂 Wildbook Integration
- Upload Encounter Annotation Export from Wildbook/GiraffeSpotter
- Automatic coordinate transformation (WGS84 → UTM)
- Spatial matching of photo-ID to locations

### 🦒 Bailey's Triple Catch (Residents-Only)
- **Classify** individuals as residents (2+ captures) vs transients (1 capture)
- **Estimate** resident population using Chapman's estimator
- **Add** transients for total population
- **Ideal for:** Short surveys (3-7 days) with transient movement

### 🌐 EarthRanger Integration
- Download patrol GPS tracks as survey effort
- Spatial overlay of encounters and patrol routes
- Complete field-to-analysis workflow

## Required Data

### For Basic SECR:
- Wildbook Encounter Annotation Export with:
  - `Name0.value` (Individual ID)
  - `Encounter.locationID` (Survey location)
  - `Encounter.latitude` / `Encounter.longitude`

### For Bailey's Analysis:
- Wildbook export (as above) PLUS:
  - `Encounter.verbatimEventDate` (Survey date)
  - At least 3 survey dates
  - Multiple encounters per individual

### For Full Workflow:
- EarthRanger credentials
- Patrol data from survey dates
- Wildbook encounter data

## Bailey's Triple Catch Method

### The Approach

```
Step 1: Classify Individuals
├── Residents: Seen 2+ times (likely local)
└── Transients: Seen once (likely passing through)

Step 2: Apply Chapman's Estimator (residents only)
├── Use first 3 survey days
├── Calculate marked population (M)
├── Count recaptures on day 3
└── Estimate resident population with SE

Step 3: Total Population
└── Resident estimate + Transient count = Total
```

### When to Use

✅ **Use Bailey's when:**
- Short survey duration (3-10 days)
- Known transient movement through area
- Interest in resident vs transient dynamics
- Multiple survey occasions per day

❌ **Don't use when:**
- Survey duration > 2 weeks (use multi-session SECR instead)
- No transient movement expected
- Only 1-2 survey occasions

### Assumptions

1. **Closed population** during survey (no births/deaths/migration)
2. **Equal catchability** within resident and transient classes
3. **Perfect identification** (photo-ID is reliable)
4. **Residents correctly classified** (2+ captures = resident)

## Installation

```bash
# Core dependencies
pip install streamlit pandas numpy scipy matplotlib geopandas shapely

# For EarthRanger integration
pip install ecoscope-release

# For Wildbook API (optional)
pip install requests
```

## Usage

### Quick Demo

1. Launch the SECR Analysis page from Twiga Tools
2. Select "🎲 Demo with Synthetic Data"
3. Adjust simulation parameters
4. Click "Generate & Analyze"
5. View results and visualizations

### Bailey's Analysis

1. Select "🦒 Bailey's Triple Catch"
2. Enter EarthRanger credentials (optional - for patrol data)
3. Enter Wildbook credentials OR upload export file
4. Ensure data covers at least 3 survey dates
5. Click "Run Bailey's Triple Catch Analysis"
6. Download results (JSON/CSV)

### Wildbook SECR

1. Select "📂 Upload Wildbook Export File"
2. Upload Encounter Annotation Export
3. Select appropriate UTM zone
4. Set state space buffer
5. Run SECR analysis
6. View detection function, capture patterns, and population estimate

## Output

### Bailey's Results
- Population estimate (N̂) with standard error
- 95% confidence interval
- Resident vs transient classification
- Sample statistics (per day)
- Recapture patterns
- Chapman estimator breakdown

### SECR Results
- Population estimate (N̂) with SE and CI
- Density (individuals/km²)
- Detection function parameters (g₀, σ)
- Capture history visualization
- Detection probability curve
- State space map

## Interpretation

### Coefficient of Variation (CV)
- **CV < 20%**: Excellent precision
- **CV 20-30%**: Good precision
- **CV > 30%**: Consider more sampling effort

### Detection Parameters
- **g₀**: Baseline detection probability (higher = easier to detect)
- **σ (sigma)**: Spatial scale in meters (larger = wider home ranges)

### Improving Estimates
1. Increase number of survey locations
2. Increase survey duration
3. Revisit same locations multiple times
4. Ensure good spatial coverage of study area

## Files

- `app.py` - Main Streamlit dashboard
- `secr_workflow.py` - SECR analysis classes and functions
- `bailey_analysis.py` - Bailey's Triple Catch implementation
- `residents_only_analysis_parameterized.R` - Original R implementation (reference)

## References

### SECR
- Borchers & Efford (2008). Spatially explicit maximum likelihood methods for capture-recapture studies. *Biometrics* 64:377-385.
- Efford (2004). Density estimation in live-trapping studies. *Oikos* 106:598-610.

### Bailey's Method
- Bailey (1951). On estimating the size of mobile populations. *Biometrika* 38:293-306.
- Chapman (1951). Some properties of the hypergeometric distribution. *Univ. California Pub. Statistics* 1:131-160.
- Seber (1982). *The Estimation of Animal Abundance and Related Parameters*. 2nd ed.

### Software
- **R `secr` package**: https://CRAN.R-project.org/package=secr
- **ecoscope**: https://github.com/wildlife-dynamics/ecoscope
- **Wildbook**: https://docs.wildbook.org

## Support

For questions or issues:
- Check the built-in help text (ℹ️ icons)
- Review the expandable "How to Interpret" sections
- Contact: courtney@giraffeconservation.org

## License

MIT License - Giraffe Conservation Foundation 2026
