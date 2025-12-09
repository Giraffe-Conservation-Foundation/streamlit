# CITES Trade Database Dashboard

This dashboard provides a live feed of CITES trade data for giraffe (*Giraffa camelopardalis*) from the Species+ API.

## Features

- **Live API Integration**: Fetches real-time data from the CITES Trade Database via Species+ API
- **Interactive Visualizations**: 
  - Trade volume trends over time
  - Trade by purpose (commercial, zoo, scientific, etc.)
  - Top exporting and importing countries
  - Trade by source type (wild, captive-bred, etc.)
- **Data Filtering**: Filter records by year, purpose, country, and trade term
- **Export Capability**: Download filtered data as CSV

## About CITES and Giraffe

In 2019, all giraffe species and subspecies were listed on **CITES Appendix II** (effective November 2020). This means:
- All international commercial trade must be authorized with proper permits
- Trade is monitored and reported to CITES
- Better data on giraffe trade patterns and volumes

## Data Source

- **API**: [Species+ API](https://api.speciesplus.net/)
- **Database**: [CITES Trade Database](https://trade.cites.org/)
- **Data Provider**: CITES Secretariat (based on reports from member countries)

## API Configuration

The dashboard uses the public Species+ API. For higher rate limits, you can add an API token to your Streamlit secrets:

```toml
# .streamlit/secrets.toml
[cites]
api_token = "your_token_here"
```

To get a token, register at [Species+](https://www.speciesplus.net/).

## Usage

1. Select the year range for trade data
2. Click "Fetch Latest Data" to retrieve records
3. Explore visualizations in the first tab
4. View and filter raw data in the second tab
5. Download filtered results as CSV

## Requirements

See `requirements.txt` for dependencies.
