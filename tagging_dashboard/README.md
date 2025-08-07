# Tagging Dashboard

Monitor newly tagged giraffes by month and country, including their initial movement patterns and veterinary records.

## Features

### 🏷️ Tagged Giraffe Tracking
- Select month and country to view giraffes tagged during that period
- Automatic parsing of subject groups in format: `COUNTRY_sitename`
- Display list of subjects with tagging dates and sites

### 📍 Movement Analysis
- Track movement patterns for the first week after tagging
- Interactive map showing movement tracks for each tagged giraffe
- Movement statistics including:
  - Total number of location points
  - Estimated total distance traveled
  - Maximum single movement distance
  - First and last location timestamps

### 💉 Veterinary Records
- View immobilization events (event_category=veterinary, event_type=immob)
- Detailed event information including:
  - Date and time of immobilization
  - Subject information
  - Event notes and details
  - Drug administration records
  - Reported by information

### 🗺️ Interactive Visualizations
- Color-coded movement tracks for each giraffe
- Hover information with timestamps and coordinates
- Zoom and pan capabilities for detailed examination

## Usage

1. **Authentication**: Enter your EarthRanger API token
2. **Select Period**: Choose the month when giraffes were tagged
3. **Select Country**: Pick from available countries (extracted from subject group names)
4. **View Results**: 
   - See list of tagged giraffes
   - Analyze movement patterns (click "Analyze Movement Patterns")
   - View veterinary records (click "Load Veterinary Records")

## Subject Group Format

The dashboard expects subject groups to be named in the format:
```
COUNTRYCODE_sitename
```

Examples:
- `KE_Maasai_Mara`
- `UG_Murchison`
- `TZ_Ruaha`

## API Requirements

- EarthRanger API access with Bearer token authentication
- Access to the following endpoints:
  - `/subjectgroups/` - For country/site information
  - `/subjects/` - For giraffe subject data
  - `/observations/` - For movement tracking
  - `/events/` - For veterinary records

## Dependencies

- streamlit
- pandas
- requests
- plotly
- python-dateutil
