# 6-Month Post-Tagging Dashboard

## Overview
The 6-Month Post-Tagging Dashboard is designed to monitor tagged giraffe subjects for 6 months following their deployment start date. This dashboard provides comprehensive tracking and analysis capabilities for post-deployment monitoring.

## Features

### 🔐 Authentication
- Uses the same EarthRanger login credentials (username/password) as other dashboards
- Secure connection to https://twiga.pamdas.org
- Session-based authentication with automatic reconnection

### 📊 Filtering Capabilities
- **Date Range Filter**: Filter subjects by deployment start date range
- **Country Filter**: Filter by country (extracted from subject group second section of underscore-delimited name)
- **Real-time Filtering**: Results update automatically when filters change

### 📍 Last Location Information
- **Subject Table**: Displays all subjects matching filter criteria
- **Location Data**: Shows last known latitude, longitude, and timestamp
- **Device Information**: Includes device ID and collar model information
- **Fix Type**: Indicates the type of location fix (GPS, ARGOS, etc.)

### 🗺️ Movement Tracking
- **6-Month Analysis**: Tracks movement from deployment start to 6 months post-deployment
- **Interactive Map**: Plotly-based interactive map with zoom and pan capabilities
- **Movement Tracks**: Shows complete movement paths for each subject
- **Start/End Markers**: 
  - Green markers indicate deployment start locations
  - Red markers show end positions (6 months or last known location)
- **Multi-Subject Support**: Can display multiple subjects simultaneously with different colors

### ⚡ Performance Optimization
- **Efficient Loading**: Table loads first, map generation requires user action
- **Caching**: Data is cached for 30 minutes to improve performance
- **Progress Indicators**: Shows loading progress for long operations
- **Batch Processing**: Efficiently handles multiple subjects

## Technical Implementation

### Data Sources
- **EarthRanger API**: Primary data source via Ecoscope integration
- **Subject Data**: Fetches all subjects with deployment information
- **Observation Data**: Retrieves GPS tracks and location fixes
- **Deployment Data**: Gets collar deployment start/end dates

### Key Functions

#### `get_all_subjects(er_io)`
- Fetches all subjects from EarthRanger
- Extracts country information from subject_subtype
- Retrieves deployment information for each subject
- Returns filtered DataFrame with deployment data

#### `extract_country_from_subtype(subject_subtype)`
- Parses subject_subtype to extract country code
- Format: "giraffe_[COUNTRY]_[AGE]" → extracts COUNTRY
- Example: "giraffe_nam_adult" → "NAM"

#### `get_subject_last_locations(er_io, subject_ids)`
- Retrieves most recent location data for subjects
- Looks back 7 days to ensure recent data availability
- Returns coordinates, timestamp, and fix type information

#### `load_movement_data_for_subject(er_io, subject_id, deployment_start)`
- Loads 6 months of movement data from deployment start
- Handles date calculations using relativedelta
- Returns sorted observation data for map visualization

#### `create_movement_map(movement_data, subjects_info)`
- Creates interactive Plotly map with movement tracks
- Uses organization color palette for visual consistency
- Adds start (green) and end (red) position markers
- Includes hover information and legend

### UI Components
- **Organization Branding**: Uses GCF color palette (#DB580F, #3E0000, etc.)
- **Responsive Design**: Works on different screen sizes
- **Progress Indicators**: Shows loading status for long operations
- **Error Handling**: Graceful error handling with user-friendly messages

## Usage Instructions

### 1. Authentication
1. Navigate to the "6-Month Post-Tagging" page
2. Enter your EarthRanger username and password
3. Click "Connect to EarthRanger"

### 2. Filter Subjects
1. Use the sidebar to set date range filters
2. Select countries of interest
3. The subject count will update automatically

### 3. View Last Locations
1. The table automatically loads with filtered subjects
2. Review last known positions and fix times
3. Check device status and collar information

### 4. Generate Movement Map
1. Click "Generate 6-Month Movement Map" button
2. Wait for data loading (progress bar will show status)
3. Interact with the map using zoom and pan controls
4. Review movement summary statistics

## Performance Considerations

### Loading Times
- **Subject List**: ~5-10 seconds for initial load
- **Last Locations**: ~1-2 seconds per subject
- **Movement Data**: ~5-10 seconds per subject for 6 months of data

### Recommendations
- Filter to specific countries to reduce data volume
- Limit to 10 or fewer subjects for map generation
- Use date range filters to focus on recent deployments

### Caching
- Subject data cached for 30 minutes
- Location data cached for 30 minutes
- Movement data loaded fresh each time (due to variability)

## Error Handling
- **Authentication Errors**: Clear messages for login failures
- **API Errors**: Graceful handling of EarthRanger API issues
- **Data Errors**: Warning messages for subjects with missing data
- **Network Errors**: Retry suggestions and connection guidance

## Dependencies
- **streamlit**: Web framework
- **pandas**: Data manipulation
- **plotly**: Interactive visualizations
- **ecoscope**: EarthRanger integration
- **requests**: HTTP requests
- **dateutil**: Date calculations
- **numpy**: Numerical operations

## Color Palette
- Primary Orange: #DB580F
- Dark Red: #3E0000
- Light Gray: #CCCCCC
- Medium Gray: #999999
- Earth Tones: #8B4513, #D2691E, #CD853F, #F4A460

## Future Enhancements
- Export capabilities for data and maps
- Additional statistical analysis
- Comparison tools between subjects
- Integration with other dashboard data
- Advanced filtering options (age, sex, etc.)

## Support
For technical issues or feature requests, contact the development team or refer to the main project documentation.