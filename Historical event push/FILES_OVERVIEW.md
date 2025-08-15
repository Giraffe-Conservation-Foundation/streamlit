# Historical Event Upload - Files Overview

## Working Solutions ✅

### 1. `direct_api_upload.py` (Primary Tool)
**Purpose:** Direct REST API upload to EarthRanger  
**Status:** ✅ Working - Successfully tested with 151 events  
**Requirements:** pandas, requests  
**Features:**
- Direct OAuth authentication
- Progress tracking
- Comprehensive error handling
- Detailed upload reports
- Stores coordinates in both location and event_details

### 2. `upload_batch.py` (Command Line Version)
**Purpose:** Direct REST API upload with command line arguments  
**Status:** ✅ Working  
**Usage:** `python upload_batch.py <csv_file> [username] [password]`
**Features:** Same as direct_api_upload.py but supports automation

### 3. `export_for_earthranger.py` (Alternative)
**Purpose:** Export CSV to JSON for manual EarthRanger import  
**Status:** ✅ Working  
**Use case:** When API upload fails or for data review

### 4. `update_coordinates.py` (Maintenance Tool)
**Purpose:** Update existing events with correct coordinates from CSV  
**Status:** ✅ Working  
**Use case:** Fix coordinate mismatches in existing events

## Data Files

### 5. `comprehensive_biological_sample_template.csv`
**Purpose:** CSV template showing required format  
**Contains:** Sample data structure matching genetic dashboard output

### 6. `comprehensive_biological_sample_250813.csv`
**Purpose:** Real data file (151 biological sample events)  
**Format:** Proper datetime format (`YYYY-MM-DDTHH:MM:SSZ`)  
**Status:** ✅ Successfully uploaded to EarthRanger

## Documentation

### 7. `README.md`
**Purpose:** Main documentation and usage instructions  
**Updated:** Reflects working solutions and coordinate fixes

### 8. `FIELD_REFERENCE_GUIDE.md`
**Purpose:** Detailed description of CSV columns and EarthRanger field mappings

### 9. `FILES_OVERVIEW.md`
**Purpose:** This file - overview of all files in the folder

## Recommended Workflow
1. **Prepare CSV data** using the template format
2. **Use `direct_api_upload.py`** for interactive bulk uploads
3. **Use `upload_batch.py`** for automated/scripted uploads
4. **Review upload reports** for any failed events
5. **Use `update_coordinates.py`** if coordinate issues arise
6. **Use `export_for_earthranger.py`** as backup if API fails

## Success Metrics
- ✅ 151 historical events successfully uploaded
- ✅ Direct API integration working with coordinate fixes
- ✅ Proper datetime format established
- ✅ Field mapping confirmed with genetic dashboard
- ✅ Coordinate accuracy issues resolved
