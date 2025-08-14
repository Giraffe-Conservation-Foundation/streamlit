# EarthRanger Historical Event Upload Tools
**Giraffe Conservation Foundation - Genetic Dashboard Integration**

## Overview
This folder contains tools for bulk uploading historical biological sample events to EarthRanger from CSV files.

## Working Solution ✅

### Direct API Upload (Recommended)
**File:** `direct_api_upload.py`

**Description:** Direct REST API integration with EarthRanger that bypasses ecoscope dependencies.

**Usage:**
```bash
python direct_api_upload.py
```

**Requirements:**
- Python 3.x
- pandas
- requests

**Features:**
- Direct OAuth authentication with EarthRanger
- Robust error handling and progress tracking
- Detailed upload reports
- No external dependencies beyond standard libraries

## Alternative Solution

### JSON Export for Manual Import
**File:** `export_for_earthranger.py`

**Description:** Exports CSV data to properly formatted JSON for manual import through EarthRanger web interface.

**Usage:**
```bash
python export_for_earthranger.py
```

## Data Files

### CSV Template
**File:** `comprehensive_biological_sample_template.csv`
- Template showing the expected CSV format
- Matches genetic dashboard output table structure

### Sample Data
**File:** `comprehensive_biological_sample_250813.csv` 
- Real data file with 151 biological sample events
- Demonstrates proper datetime format: `YYYY-MM-DDTHH:MM:SSZ`

## CSV Format Requirements

### Required Columns
- `event_datetime`: ISO format datetime (`2024-01-01T12:00:00Z`)
- `latitude`: Decimal degrees (optional, set to 0 if unknown)
- `longitude`: Decimal degrees (optional, set to 0 if unknown)

### Detail Columns (all optional)
All columns starting with `details_` will be mapped to event details:
- `details_girsam_iso`: Country ISO code
- `details_girsam_site`: Collection site
- `details_girsam_origin`: Sample origin
- `details_girsam_age`: Animal age
- `details_girsam_sex`: Animal sex
- `details_girsam_type`: Sample type
- `details_girsam_smpid`: Sample ID
- `details_girsam_subid`: Subject ID
- `details_girsam_status`: Sample status
- `details_girsam_species`: Species name
- `details_girsam_notes`: Notes
- `details_girsam_smpid2`: Alternative sample ID

## Success Metrics
- ✅ **Tested**: Successfully uploaded 151 events via direct API
- ✅ **Reliable**: Bypasses ecoscope compatibility issues
- ✅ **Fast**: Direct API calls with progress tracking
- ✅ **Robust**: Comprehensive error handling and reporting

## Next Steps
1. Use `direct_api_upload.py` for future bulk uploads
2. Ensure CSV files follow the datetime format: `YYYY-MM-DDTHH:MM:SSZ`
3. Test uploads with small batches first
4. Review upload reports for any failed events

## Support
For issues or questions, refer to the field reference guide or contact the development team.
