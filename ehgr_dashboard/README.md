# EHGR Dashboard

## Overview
The EHGR (East and Horn of Africa Giraffe Research) Dashboard provides monitoring and analysis capabilities for giraffe survey encounters and population data in Namibia. This dashboard is designed to match the functionality of the ZAF Dashboard but focuses on Namibia-specific data.

## Features

### 🔐 Authentication
- Secure login using EarthRanger credentials
- Session management with logout functionality

### 📊 Key Metrics
- **Individuals seen**: Total count of individual giraffes observed
- **Herds seen**: Number of herd encounters recorded
- **Average herd size**: Mean size of giraffe herds observed

### 📍 Interactive Mapping
- Satellite view mapping of giraffe sightings
- Hover data showing encounter details
- Automatic centering and zoom based on data extent
- Support for both Mapbox (with token) and OpenStreetMap (free)

### 🧬 Age/Sex Analysis
- Breakdown of giraffe populations by age and sex
- Support for both individual and herd-level data
- Interactive bar charts for demographic analysis

### 📅 Date Filtering
- Sidebar date range selection
- Real-time filtering of all dashboard components
- Default date range based on available data

## Data Sources

### Event Categories
- **Event Category**: `monitoring_nam` (Namibia monitoring events)
- **Event Type**: `giraffe_survey_encounter_nam` (Namibia giraffe encounters)

### Data Fields
The dashboard processes the following data fields:
- Location coordinates (latitude/longitude)
- Encounter timestamps
- Herd size information
- Individual giraffe demographics (age, sex)
- Survey metadata and notes

## Technical Implementation

### Dependencies
- `streamlit` - Web application framework
- `pandas` - Data manipulation and analysis
- `plotly` - Interactive visualizations
- `ecoscope` - EarthRanger integration
- `python-dotenv` - Environment variable management

### Caching
- Data caching with 1-hour TTL for performance
- Separate caching for sources and event data
- Automatic cache invalidation on session changes

### Error Handling
- Graceful handling of missing data
- Clear error messages for data access issues
- Fallback displays when no data is available

## Configuration

### Environment Variables
- `EARTHRANGER_SERVER`: EarthRanger server URL (default: https://twiga.pamdas.org)
- `MAPBOX_TOKEN`: Optional Mapbox access token for satellite imagery

### Date Range
- Default range: July 1, 2024 to December 31, 2025
- Configurable date parameters in the `load_data()` function

## Usage

1. **Authentication**: Enter EarthRanger username and password
2. **Date Selection**: Use sidebar to select desired date range
3. **View Metrics**: Review summary statistics at the top
4. **Explore Map**: Interactive map shows all sighting locations
5. **Analyze Demographics**: Age/sex breakdown charts provide population insights
6. **Logout**: Use sidebar logout button to end session

## File Structure

```
ehgr_dashboard/
├── app.py          # Main dashboard application
└── README.md       # This documentation

pages/
└── 11_🦒_EHGR_Dashboard.py  # Streamlit page integration
```

## Troubleshooting

### No Data Available
If you see "No data available to display":
1. Verify event category `monitoring_nam` exists in EarthRanger
2. Confirm event type `giraffe_survey_encounter_nam` is correct
3. Check if data exists in the selected date range
4. Ensure proper authentication and permissions

### Authentication Issues
- Verify EarthRanger credentials are correct
- Check network connectivity to the EarthRanger server
- Ensure user has appropriate permissions for the data

### Performance Issues
- Data is cached for 1 hour to improve performance
- Large date ranges may take longer to load
- Consider narrowing date ranges for better performance

## Support

For technical issues or feature requests, please contact the development team or refer to the main Twiga Tools documentation.