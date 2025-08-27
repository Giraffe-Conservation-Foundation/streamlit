# Unit Monitoring Historical Event Push

## Overview
This folder contains scripts for uploading historical unit monitoring events to EarthRanger.

**Purpose**: Upload historical data for tracking unit deployments, maintenance, battery changes, and other unit-related activities.

**Event Type**: 
- `event_category`: "unit_monitoring"
- `event_type`: "unit_update"

## Files in this Directory

### `unit_monitoring_upload.py`
Main script for uploading historical unit monitoring events.

**Features**:
- CSV template generation
- Data validation and error checking  
- Batch upload to EarthRanger API
- Failed event logging and retry capability
- Progress tracking and detailed reporting

**Event Structure**:
```json
{
  "event_category": "unit_monitoring",
  "event_type": "unit_update", 
  "event_details": {
    "unitupdate_unitid": "TAIL-ST1386",
    "unitupdate_action": "deployment",
    "unitupdate_country": "NAM",
    "unitupdate_notes": "Initial deployment in conservancy",
    "unitupdate_subjectid": "subject-uuid-123"
  },
  "location": {
    "latitude": -22.5,
    "longitude": 17.1
  },
  "time": "2024-01-15T10:30:00Z"
}
```

## Usage Instructions

### 1. Generate CSV Template
```bash
python unit_monitoring_upload.py
# Select option 1 to generate template
```

### 2. Fill in Your Data
Open the generated CSV template and add your unit monitoring events:

| Column | Description | Required | Example |
|--------|-------------|----------|---------|
| unit_id | Tracking unit identifier | Yes | TAIL-ST1386 |
| action | Type of action | Yes | deployment, maintenance, battery_change, retrieval |
| country | Country code | Yes | NAM, BWA, ZAF, KEN, TZA |
| notes | Event description | Yes | Initial deployment in conservancy |
| subject_id | Associated subject UUID | No | subject-uuid-123 |
| latitude | Event latitude | No | -22.5 |
| longitude | Event longitude | No | 17.1 |
| date_time | Event timestamp | Yes | 2024-01-15 10:30:00 |
- **name** (optional): Username of the person who recorded this event (maps to user.username field in EarthRanger)

### 3. Upload Historical Data
```bash
python unit_monitoring_upload.py
# Select option 2 to upload from CSV
# Provide path to your filled CSV file
# Enter EarthRanger credentials when prompted
```

## Action Types

The script supports these standard action types:
- **deployment**: Initial unit deployment
- **maintenance**: General maintenance activities
- **battery_change**: Battery replacement/maintenance
- **retrieval**: Unit retrieval/removal
- **other**: Other unit-related activities

## Data Validation

The script validates:
- ✅ Required fields (unit_id, action, country, notes, date_time)
- ✅ Date format validation
- ✅ Coordinate range validation (if provided)
- ✅ Data type checking
- ✅ Empty field detection

## Output Files

- **Template**: `unit_monitoring_template_YYYYMMDD.csv`
- **Failed Events**: `failed_unit_monitoring_upload_YYYYMMDD_HHMMSS.json`
- **Log File**: `unit_monitoring_upload_YYYYMMDD.log`

## Error Handling

If events fail to upload:
1. Check the failed events JSON file for specific error details
2. Review and correct the data issues
3. Re-run the upload with the corrected data
4. The script includes rate limiting to avoid API throttling

## Example CSV Data

```csv
unit_id,action,country,notes,subject_id,latitude,longitude,date_time
TAIL-ST1386,deployment,NAM,Initial deployment in conservancy,subject-uuid-123,-22.5,17.1,2024-01-15 10:30:00
TAIL-ST1387,maintenance,BWA,Battery replacement completed,subject-uuid-124,-24.2,21.4,2024-02-20 14:15:00
TAIL-ST1388,battery_change,ZAF,Routine battery maintenance,,-26.0,28.0,2024-03-10 09:00:00
TAIL-ST1389,retrieval,KEN,Unit retrieved for repairs,subject-uuid-125,-1.3,36.8,2024-04-05 16:45:00
```

## Integration with Other Tools

This script is designed to work alongside:
- **Source Dashboard**: View uploaded unit monitoring events
- **Tagging Dashboard**: Cross-reference with animal tagging events
- **ER Backup Tool**: Include unit monitoring events in data backups

## Troubleshooting

**Common Issues**:
1. **Authentication Failed**: Check username/password and server URL
2. **Event Type Not Found**: Verify unit_update event type exists in EarthRanger
3. **Invalid Coordinates**: Ensure latitude (-90 to 90) and longitude (-180 to 180) ranges
4. **Date Format Errors**: Use YYYY-MM-DD HH:MM:SS format
5. **Missing Required Fields**: Ensure unit_id, action, country, notes, and date_time are provided

**Need Help?**
- Check the log file for detailed error messages
- Review failed events JSON for specific API errors
- Verify your CSV data matches the template format

---
*Created: August 2025*  
*Author: Giraffe Conservation Foundation*  
*Purpose: Historical unit monitoring event upload to EarthRanger*
