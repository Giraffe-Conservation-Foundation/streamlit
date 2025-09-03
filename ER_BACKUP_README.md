# ER Backup Tool - SubjectSource Observations

## Overview

The ER Backup Tool has been enhanced with comprehensive SubjectSource Observations backup functionality, as requested. This tool now provides a complete backup solution for all EarthRanger data, with special focus on SubjectSource Observations - GPS tracking data specifically linked to subject-source pairs.

## New Features Added

### 🔗 SubjectSource Observations Backup
- **Primary Feature**: Complete backup of all subjectsource_observations data
- **Date Range Filtering**: Filter observations by start and end date
- **Batch Processing**: Handles large datasets efficiently by processing in batches
- **Source Details**: Includes detailed source information (device metadata)
- **Coordinate Extraction**: Extracts latitude/longitude from geometry data
- **Device Status**: Captures device status properties (battery, signal strength, etc.)

### 📍 Enhanced Data Coverage
The tool now backs up:
- **🔗 SubjectSource Observations** (NEW): GPS data linked to specific subject-source pairs
- **📍 General Observations**: All GPS tracking data from devices
- **👥 Subject Groups & Subjects**: Animal profiles and groupings
- **📡 Sources**: Tracking device information
- **📝 Events/Reports**: All event types (surveys, mortalities, vet procedures, etc.)

## Technical Implementation

### Key Functions Added

#### `backup_subjectsource_observations()`
```python
def backup_subjectsource_observations(username, password, server_url, start_date=None, end_date=None):
    """
    Backup subjectsource observations data specifically
    - Gets all subjectsources first
    - Processes in batches to avoid timeouts
    - Applies date range filtering
    - Extracts coordinates and device properties
    - Returns comprehensive DataFrame
    """
```

### Ecoscope Integration
The tool leverages the `ecoscope` library's `EarthRangerIO` class with these key methods:
- `get_subjectsources()`: Get all subject-source relationships
- `get_subjectsource_observations()`: Get GPS data for specific subjectsources
- Date filtering: `since` and `until` parameters
- Source details: `include_source_details=True`

### Batch Processing Logic
```python
# Process in smaller batches to avoid timeouts
batch_size = 10
for i in range(0, len(subjectsource_ids), batch_size):
    batch_ids = subjectsource_ids[i:i+batch_size]
    batch_obs = er_io.get_subjectsource_observations(
        subjectsource_ids=batch_ids,
        since=start_str,
        until=end_str,
        relocations=False,
        include_source_details=True
    )
```

## User Interface

### Authentication
- **Server**: `https://twiga.pamdas.org`
- **Username/Password**: EarthRanger credentials
- **Connection Testing**: Built-in connection verification

### Backup Configuration
- **✅ SubjectSource Observations** (recommended, new feature)
- **📍 General Observations** (legacy option)
- **📝 Events/Reports** (all event types)
- **👥 Subjects & Groups** (animal profiles)
- **📡 Sources** (device information)

### Date Range Selection
- **Start Date**: Default to 2024-01-01
- **End Date**: Default to current date
- **Validation**: Ensures start date ≤ end date

## Output Format

### CSV Files Generated
The tool creates a ZIP file containing:
- `YYYYMMDD_GCFbackup_ERsubjectsource_obs.csv` - SubjectSource observations (NEW)
- `YYYYMMDD_GCFbackup_ERobs.csv` - General observations
- `YYYYMMDD_GCFbackup_ERsub.csv` - Subjects
- `YYYYMMDD_GCFbackup_ERgrp.csv` - Subject groups
- `YYYYMMDD_GCFbackup_ERsrc.csv` - Sources
- `YYYYMMDD_GCFbackup_ERrepXXX.csv` - Events by type

### Data Columns
SubjectSource observations include:
- **Core Data**: `id`, `subjectsource_id`, `recorded_at`, `created_at`
- **Location**: `latitude`, `longitude` (extracted from geometry)
- **Device**: `device_*` columns (battery, signal, etc.)
- **Source Details**: `source__*` columns (when enabled)

## Usage Instructions

### 1. Access the Tool
- Navigate to http://localhost:8502 (or your Streamlit server)
- Click on "💾 ER Backup" in the sidebar

### 2. Authentication
- Enter your EarthRanger username and password
- Click "Login"
- Use "Test Connection" to verify

### 3. Configure Backup
- **Enable "🔗 Include SubjectSource Observations"** (recommended)
- Select additional data types as needed
- Set date range for observations and events

### 4. Execute Backup
- Click "🔄 Start Backup"
- Monitor progress bar and status messages
- Wait for completion (may take several minutes for large datasets)

### 5. Download Results
- Review data validation summary
- Click "📥 Download Backup ZIP"
- Extract CSV files as needed

## Performance & Limitations

### Optimizations
- **Caching**: 30-minute cache for repeated queries
- **Batch Processing**: Handles large datasets efficiently
- **Progress Tracking**: Real-time status updates
- **Error Handling**: Graceful handling of timeouts and failures

### Considerations
- **Large Datasets**: May take several minutes for extensive date ranges
- **Server Timeouts**: Uses batch processing to minimize timeout risk
- **Memory Usage**: Processes data in chunks to manage memory
- **Network**: Requires stable connection to EarthRanger server

## Error Handling

### Common Issues & Solutions
- **Authentication Failure**: Check username/password, verify server access
- **Timeout Errors**: Reduce date range, ensure stable network connection
- **Empty Results**: Check date range, verify data exists in EarthRanger
- **Memory Issues**: Process smaller date ranges, close other applications

### Validation Features
- **Data Validation**: Automatic validation of backup completeness
- **Record Counts**: Summary of records per data type
- **Status Indicators**: ✅ Success, ⚠️ Warning, ❌ Error messages

## Example Use Cases

### 1. Complete Data Backup
```
✅ SubjectSource Observations: Enable
✅ Events/Reports: Enable  
✅ Subjects & Groups: Enable
✅ Sources: Enable
Date Range: 2024-01-01 to 2025-09-02
```

### 2. GPS Data Only
```
✅ SubjectSource Observations: Enable
❌ Other options: Disable
Date Range: Last 30 days
```

### 3. Recent Activity
```
✅ SubjectSource Observations: Enable
✅ Events/Reports: Enable
Date Range: Last 7 days
```

## Integration with Existing Workflow

### Existing Features Maintained
- All original backup functionality preserved
- Subject groups processing with country/region filtering
- Event type categorization (survey, mortality, vet, etc.)
- Source and subject metadata backup

### New Additions
- SubjectSource observations as primary GPS data source
- Enhanced date filtering capabilities
- Improved batch processing for large datasets
- Better error handling and user feedback

## Future Enhancements

### Potential Improvements
- **Incremental Backup**: Only backup new/changed data
- **Automated Scheduling**: Regular backup execution
- **Cloud Storage**: Direct upload to cloud storage
- **Data Validation**: Advanced validation and quality checks
- **Export Formats**: Additional formats (Excel, GeoJSON, etc.)

## Support

For questions or issues with the ER Backup tool:
1. Check the validation summary for data quality issues
2. Review error messages for specific problems
3. Test connection if authentication fails
4. Contact: courtney@giraffeconservation.org

---

**Last Updated**: September 2, 2025  
**Version**: 2.0 - SubjectSource Observations Support  
**Author**: GCF Development Team
