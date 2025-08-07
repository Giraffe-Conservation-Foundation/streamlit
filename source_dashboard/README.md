# Source Dashboard

A Streamlit-based dashboard for monitoring and analyzing EarthRanger tracking device sources.

## Features

### 🔐 Authentication
- Secure login with EarthRanger API token
- Connects to Twiga EarthRanger instance (https://twiga.pamdas.org)
- Automatic session management

### 📍 Location Tracking
- View latest positions of tracking devices
- Interactive map visualization with color-coded sources
- Support for multiple source selection and comparison

### 📊 Activity Analysis
- 7-day location transmission charts
- Daily location count visualization by source
- Provider-based filtering for tracking devices

### ⚠️ Inactive Source Monitoring
- Identify sources not reporting for >90 days
- Filter by sources attached to subjects
- Provider breakdown of inactive sources

## Requirements

### Python Dependencies
```
streamlit
pandas
requests
plotly
```

### EarthRanger Access
- Valid EarthRanger API token with appropriate permissions
- Access to the Twiga EarthRanger instance (https://twiga.pamdas.org)

## Usage

### Authentication

**API Token** (Only authentication method):
- Generate an API token from the Twiga EarthRanger instance
- Enter the token in the authentication form
   - Use your regular EarthRanger login credentials
   - Provides access to additional features like subject-source relationships

### Dashboard Sections

1. **Source Selection**:
   - Filter by manufacturer/provider
   - Multi-select tracking devices
   - Color-coded visualization

2. **Latest Locations**:
   - Real-time position data
   - Interactive map with source markers
   - Coordinate display with timestamps

3. **Activity Charts**:
   - 7-day transmission history
   - Daily location count trends
   - Comparative analysis across sources

4. **Inactive Analysis**:
   - Sources with >90 days no transmission
   - Subject-attached source filtering
   - Provider-based breakdowns

## Configuration

The dashboard connects to EarthRanger APIs and uses caching for performance:
- Source data cached for 1 hour
- Real-time location queries
- Optimized for multiple source monitoring

## Integration

This dashboard integrates with the Twiga Tools ecosystem:
- Consistent UI/UX with other tools
- Logo and branding alignment  
- Session state management
- Responsive design

## Data Sources

- **EarthRanger API**: Source metadata, locations, observations
- **EcoPope Library**: Subject-source relationships, advanced queries
- **Plotly**: Interactive visualizations and mapping