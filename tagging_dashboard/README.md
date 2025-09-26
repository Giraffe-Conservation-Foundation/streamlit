# Post-Tagging Dashboard

Monitor giraffe locations during the first 2 days after collar deployment/tagging to verify successful activation and track initial movement patterns.

## Features

### 📡 Deployment Verification
- Select date range when collars were deployed
- Automatically identifies subjects with collar deployments (via assigned_range)
- Tracks first 48 hours of location data post-deployment

### 📍 2-Day Location Tracking
- Interactive map showing deployment locations and movement tracks
- Color-coded tracks for each deployed giraffe
- Deployment start markers with timestamps
- Real-time verification of collar activation

### ⏱️ Timeline Visualization
- Data collection timeline over 48-hour period
- Hours since deployment tracking
- Visual indicators for 24 and 48-hour marks
- Identify data transmission patterns

### � Movement Analysis
- Summary statistics for first 2 days:
  - Number of locations recorded
  - Time span of data collection
  - Approximate distance traveled
  - Movement area estimation
- Early detection of potential collar issues

### 🗺️ Interactive Map Features
- Deployment start locations marked with stars
- Movement tracks with hover information
- Auto-centering on deployment area
- Coordinate details and timestamps

## Usage

1. **Authentication**: Enter your EarthRanger username and password
2. **Select Date Range**: Choose the period when collars were deployed (default: last 30 days)
3. **View Deployments**: See summary of collar deployments in selected period
4. **Analyze Movement**: 
   - Interactive map with deployment locations and tracks
   - Timeline showing data collection patterns
   - Movement summary statistics
   - Detailed location data export

## How It Works

The dashboard:
1. Queries subjects with `assigned_range` dates within selected period
2. For each deployment, retrieves location data for 48 hours post-deployment
3. Creates visualizations to verify collar activation and movement patterns
4. Provides early warning for potential collar issues

## Use Cases

- **Deployment Verification**: Confirm collars activated successfully after deployment
- **Movement Validation**: Verify giraffes are moving normally post-deployment
- **Data Quality Check**: Identify transmission issues or collar malfunctions early
- **Field Team Support**: Provide immediate feedback on deployment success

## Authentication

Uses EcoScope EarthRangerIO with username/password authentication to:
- Access subject data and deployment information
- Retrieve location observations for specified time periods
- Ensure secure connection to EarthRanger API

## Dependencies

- streamlit
- pandas  
- ecoscope (EarthRangerIO)
- plotly
- numpy
- datetime
