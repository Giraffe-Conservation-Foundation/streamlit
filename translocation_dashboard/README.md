# Translocation Dashboard

## Overview
The Translocation Dashboard provides comprehensive monitoring and analysis of giraffe translocation events from EarthRanger. It specifically targets veterinary events categorized as "translocation" to give conservationists insights into translocation activities.

## Features

### 🔐 Authentication
- Secure EarthRanger username/password authentication via ecoscope
- Direct connection to https://twiga.pamdas.org

### 📅 Date Filtering
- Customizable date range selection
- Default view shows last year of data
- Real-time data refresh capabilities

### 📊 Analytics & Visualizations
- **Summary Statistics**: Total events, location data availability, date range metrics
- **Time-based Analysis**: Monthly and yearly event trends
- **Event Status Tracking**: Distribution of event states
- **Geographic Mapping**: Interactive map showing translocation locations
- **Detailed Event Information**: Expandable view with comprehensive event details

### 📋 Data Display
- Summary table with key event information
- Detailed expandable cards for each event
- Event details including notes, coordinates, and metadata
- Export-ready data formats

## Technical Details

### API Integration
- **Event Category Filter**: `event_category == 'translocation'`
- **Data Source**: EarthRanger via ecoscope package
- **Caching**: 30-minute cache for performance optimization

### Data Processing
- Automatic date/time parsing and formatting
- Geographic coordinate extraction from location data
- Event state and priority analysis
- Monthly and yearly aggregations

### Visualizations
- **Bar Charts**: Monthly and yearly event trends
- **Pie Charts**: Event status distribution and yearly breakdown
- **Interactive Maps**: Plotly Mapbox integration for location visualization
- **Data Tables**: Sortable and filterable event summaries

## Usage

1. **Authentication**: Enter your EarthRanger username and password
2. **Date Selection**: Choose your desired date range for analysis
3. **Data Exploration**: Review summary statistics and visualizations
4. **Detailed Analysis**: Expand individual events for comprehensive details
5. **Geographic Analysis**: Use the interactive map to explore event locations

## File Structure
```
translocation_dashboard/
├── app.py              # Main dashboard application
└── README.md           # This documentation file

pages/
└── 7_🚁_Translocation_Dashboard.py  # Streamlit page integration
```

## Dependencies
- streamlit>=1.28.0
- pandas>=1.5.0
- geopandas>=0.13.0
- plotly>=5.10.0
- ecoscope>=1.0.0

## Event Data Structure
The dashboard processes events with the following key fields (via ecoscope):
- `id`: Unique event identifier
- `time`: Event timestamp
- `event_category`: Must be "translocation"
- `state`: Event status (new, active, resolved, etc.)
- `priority`: Event priority level
- `geometry`: Geographic coordinates (converted to latitude/longitude)
- `event_details`: Additional event metadata
- `notes`: Associated notes and comments

## Security
- Username/password credentials are handled securely through ecoscope
- No persistent storage of authentication credentials
- HTTPS communication with EarthRanger API via ecoscope
