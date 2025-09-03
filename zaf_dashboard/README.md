# ZAF Dashboard

## Overview
The ZAF (South Africa) Dashboard provides comprehensive monitoring and analysis of giraffe conservation activities in South Africa through EarthRanger integration.

## Features

### 🔐 Authentication
- Secure EarthRanger username/password authentication via ecoscope
- Direct connection to https://twiga.pamdas.org

### 📅 Date Filtering
- Customizable date range selection
- Real-time data refresh capabilities
- Sidebar date range filter

### 📊 Analytics & Visualizations
- **Population Metrics**: Current population size, individuals seen, percentage coverage
- **Herd Analysis**: Herd count, average herd size statistics
- **Geographic Mapping**: Interactive map showing sighting locations
- **Temporal Analysis**: Monthly sighting trends and patterns
- **Demographic Breakdown**: Age and sex distribution charts
- **Individual Tracking**: List of giraffe individuals observed
- **AAG Integration**: Adopt A Giraffe program tracking

### 🗺️ Interactive Features
- Geographic sighting map with coordinates
- Monthly sighting trend visualization
- Age/sex demographic charts
- Searchable giraffe individual lists

## Data Sources

### Event Categories
- **Primary**: `monitoring_zaf` - South Africa monitoring events
- **Event Type**: `giraffe_survey_encounter_zaf` - ZAF-specific giraffe encounters

### Subject Groups
- **Simplified Dashboard**: Subject group dependencies removed for ZAF implementation
- **Direct Event Processing**: Uses event data directly without subject group mapping

## Configuration

### Simplified ZAF Dashboard
This dashboard has been simplified for ZAF usage:
- **Subject groups removed**: Not applicable for this site
- **AAG functionality removed**: Adopt A Giraffe program not used in ZAF
- **Simplified metrics**: Focuses on tracking sources and direct sighting data
- **Direct event processing**: Uses event data without subject group dependencies

## Usage

1. **Authentication**: Enter your EarthRanger credentials
2. **Date Selection**: Use the sidebar to select your date range
3. **Analysis**: Review the various metrics and visualizations
4. **Individual Tracking**: Check the lists of observed giraffe IDs
5. **Source Monitoring**: Monitor active tracking sources

## Technical Requirements

### Dependencies
- `streamlit` - Web application framework
- `pandas` - Data manipulation and analysis
- `plotly` - Interactive visualizations
- `ecoscope` - EarthRanger integration
- `python-dotenv` - Environment variable management (optional)

### API Access
- EarthRanger API access with valid credentials
- Access to the following endpoints:
  - `/subjects/` - For giraffe subject data
  - `/sources/` - For tracking device information
  - `/events/` - For survey encounter data

## Data Structure

### Expected Event Fields
- `event_category`: "monitoring_zaf"
- `event_type`: "giraffe_survey_encounter_zaf"
- `event_details.Herd`: Herd composition data
- `giraffe_id`: Individual giraffe identifier
- `giraffe_age`: Age classification
- `giraffe_sex`: Sex classification
- `location.latitude/longitude`: Geographic coordinates

## Troubleshooting

### Common Issues

1. **No Data Displayed**:
   - Verify event category and type names
   - Check subject group IDs
   - Confirm date range has data

2. **Authentication Errors**:
   - Verify EarthRanger credentials
   - Check server URL configuration
   - Ensure API access permissions

3. **Missing Visualizations**:
   - Check data field availability
   - Verify column mapping in rename_map
   - Review event detail structure

### Getting Help
For technical support or questions about the ZAF Dashboard:
- Contact: courtney@giraffeconservation.org
- Include error messages and steps to reproduce issues

## License

This project is for conservation research purposes. Please ensure compliance with your organization's data handling policies and local regulations regarding wildlife research data.

---

**🦒 Giraffe Conservation Foundation - ZAF Monitoring Dashboard**  
*Supporting South African giraffe conservation through data-driven insights*
