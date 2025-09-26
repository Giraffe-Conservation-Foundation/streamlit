# Unit Check Dashboard

A simple monitoring dashboard for tracking device units, providing essential information for the last 7 days.

## Features

### 🔐 Authentication
- Secure login with EarthRanger username/password
- Session management for authenticated users

### 📡 Unit Selection
- Browse tracking devices by manufacturer
- **SpoorTrack is pre-selected as default manufacturer**
- Multi-select capability for monitoring multiple units simultaneously
- Shows unit model and status information

### 📊 7-Day Monitoring

#### Activity Chart
- Daily observation counts over the last 7 days
- Visual bar chart showing data transmission patterns
- Helps identify communication issues or device problems

#### Battery Monitoring
- Battery level tracking over time
- Automatic conversion from voltage to percentage
- Warning thresholds:
  - Red line at 20% (Low Battery)
  - Orange line at 50% (Medium Battery)

#### Location Mapping
- Interactive map showing unit movement
- Track lines connecting location points
- Hover information with timestamps
- Auto-centers on data points

### 📈 Summary Metrics
- **Total Observations**: Count of data points received
- **Last Update**: Hours since last data transmission
- **Daily Average**: Average observations per day

## Usage

1. **Login**: Enter your EarthRanger credentials
2. **Select Manufacturer**: Choose from available manufacturers (SpoorTrack selected by default)
3. **Select Units**: Choose one or more units to monitor
4. **View Data**: Switch between Activity, Battery, and Location tabs

## Technical Details

### Data Sources
- EarthRanger API via ecoscope library
- Cached data for performance (30 min for sources, 15 min for observations)
- 7-day lookback period for all analyses

### Visualization
- Plotly charts with organization color scheme
- Interactive maps using OpenStreetMap
- Responsive design for different screen sizes

### Error Handling
- Graceful handling of missing data
- Clear error messages for connection issues
- Fallback displays when no data is available

## Configuration

The dashboard uses these environment variables:
- `EARTHRANGER_SERVER`: EarthRanger server URL (defaults to https://twiga.pamdas.org)

## Dependencies

- streamlit
- pandas
- plotly
- ecoscope
- requests

## File Structure

```
unit_check_dashboard/
├── app.py          # Main dashboard application
└── README.md       # This documentation
```