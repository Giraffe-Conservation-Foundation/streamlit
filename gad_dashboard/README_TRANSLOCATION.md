# GAD Dashboard - Translocation Assessment Setup Guide

## Overview
The GAD Dashboard now includes a **Translocation Assessment** tool that ranks protected areas for giraffe reintroduction based on ecological, governance, and implementation criteria.

## Required Data Files

Place these files in the `gad_dashboard/` folder:

### 1. WDPA Protected Areas Data
- **File names**: `wdpa_polygons.shp` (with .shx, .dbf, .prj) OR `wdpa_polygons.gpkg`
- **File names**: `wdpa_points.shp` (with .shx, .dbf, .prj) OR `wdpa_points.gpkg`
- **Source**: [Protected Planet](https://www.protectedplanet.net/en/thematic-areas/wdpa)
- **What it does**: Auto-detects protected area names, sizes, governance types, and management authorities

### 2. Biodiversity Intactness Index (BII) - Google Earth Engine
- **No file needed** - Uses Google Earth Engine API
- **Source**: [BII on Google Earth Engine](https://samapriya.github.io/awesome-gee-community-datasets/projects/bii/)
- **Resolution**: 1km or 8km available
- **What it does**: Auto-populates landscape connectivity scores (1-5 scale) on-demand
- **Authentication**: Run `earthengine authenticate` in terminal once
- **Advantages**: No local storage needed, always up-to-date, includes detailed metrics (mammals, birds, reptiles, plants, land use)

### 3. World Bank Political Stability Data
- **No file needed** - Uses API
- **What it does**: Auto-populates political stability rankings from World Bank Governance Indicators
- **Install**: `pip install wbgapi`

### 4. Zotero Management Plans
- **No file needed** - Uses API
- **Configuration**: Add to `.streamlit/secrets.toml`:
  ```toml
  [zotero]
  library_id = "5485373"  # Your Zotero library ID
  api_key = "your_api_key"  # Optional for public libraries
  ```
- **What it does**: Auto-detects if giraffe management plans exist for a country

## Installation

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Authenticate Google Earth Engine** (one-time setup):
   ```bash
   earthengine authenticate
   ```
   This will open a browser for authentication. Follow the prompts.

3. **Place WDPA data files** in `gad_dashboard/` folder:
   ```
   gad_dashboard/
   ├── app.py
   ├── requirements.txt
   ├── wdpa_polygons.shp  (+ .shx, .dbf, .prj)
   └── wdpa_points.shp    (+ .shx, .dbf, .prj)
   ```
   Note: BII data is pulled from Google Earth Engine on-demand (no local file needed)

4. **Configure secrets** (optional, for Zotero):
   Create `.streamlit/secrets.toml` in parent directory

## Usage

### Auto-Population Workflow

1. **Enter coordinates** (latitude/longitude)
2. **Click "🔍 Auto-Populate from Coordinates"**
3. System will automatically fetch:
   - Protected area name and size (from WDPA)
   - Governance/management type (from WDPA)
   - Landscape connectivity score (from BII raster)
   - Political stability ranking (from World Bank API)
   - Management plan existence (from Zotero)

4. **Review and adjust** auto-populated values
5. **Add manual assessments** for:
   - Vegetation suitability (requires species-specific raster)
   - Threat level
   - Permit ease
   - Logistics
   - Stakeholder willingness

6. **Save assessment** to calculate suitability score

### Manual Entry (without data files)
The tool works without external data files - you'll just need to manually enter all criteria.

## Scoring Algorithm

**Total Score** = (Ecological × 40%) + (Governance × 30%) + (Implementation × 30%)

### Ecological (40%)
- Area size (larger is better)
- Vegetation suitability (1-5)
- Landscape connectivity/BII (1-5)
- Threat level (5=low threats is better)

### Governance (30%)
- Political stability (1-5)
- Management type (collaborative > mixed > government only)
- Has management plan (yes/no)
- Has monitoring program (yes/no)

### Implementation (30%)
- Permit accessibility (1-5)
- Transport/logistics ease (1-5)
- Stakeholder willingness (1-5)

## Data Sources

| Data Type | Source | Auto-Populate | Manual |
|-----------|--------|---------------|--------|
| Protected area name | WDPA shapefile | ✅ | ✅ |
| Area size | WDPA shapefile | ✅ | ✅ |
| Governance type | WDPA shapefile | ✅ | ✅ |
| Connectivity (BII) | Google Earth Engine | ✅ | ✅ |
| Political stability | World Bank API | ✅ | ✅ |
| Management plans | Zotero API | ✅ | ✅ |
| Vegetation suitability | Species raster* | ❌ | ✅ |
| Threats | Expert assessment | ❌ | ✅ |
| Permits | Expert assessment | ❌ | ✅ |
| Logistics | Expert assessment | ❌ | ✅ |
| Stakeholder support | Expert assessment | ❌ | ✅ |

*Future enhancement: Add species-specific habitat suitability rasters (could also use GEE)

## Troubleshooting

### WDPA files not loading
- Ensure files are named exactly: `wdpa_polygons.shp` and `wdpa_points.shp`
- Check that all shapefile components (.shp, .shx, .dbf, .prj) are present
- Alternative: Use GeoPackage format (.gpkg)

### Google Earth Engine not working
- Authenticate first: `earthengine authenticate`
- Check internet connection
- Verify credentials: `earthengine user info`
- If still issues, try: `earthengine authenticate --force`
- Note: GEE is free but requires a Google account

### World Bank API not working
- Install: `pip install wbgapi`
- Check internet connection
- Note: API may have rate limits

### Zotero API not working
- Verify library_id in secrets
- Check if library is public (no API key needed) or private (needs API key)
- Ensure 'giraffe' tag is used on relevant items

## Future Enhancements

- [ ] CSV import/export for batch assessment
- [ ] Database integration (PostgreSQL/PostGIS)
- [ ] Species-specific vegetation suitability rasters
- [ ] Interactive map with site ranking
- [ ] Report generation (PDF/Word)
- [ ] Multi-criteria decision analysis (MCDA) visualization
- [ ] Sensitivity analysis for weights

## Support

For questions or issues, contact the GCF data team.
