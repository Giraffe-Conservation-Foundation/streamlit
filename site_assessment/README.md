# 🌍 Site Assessment Dashboard

Evaluate potential giraffe translocation sites using satellite imagery and environmental data.

## Overview

The Site Assessment tool helps GCF staff and partners quickly evaluate habitat suitability for giraffe translocations using real-time satellite data. It analyzes vegetation health (NDVI) from Sentinel-2 imagery to provide preliminary site assessments.

## Features

### 📍 Multiple Site Definition Methods
- **Interactive Map Drawing**: Draw polygons directly on a map
- **Shapefile Upload**: Import existing GIS data
- **Coordinate Entry**: Manually specify polygon vertices

### 🛰️ Satellite Data Analysis
- **Sentinel-2 Imagery**: 10m resolution satellite data
- **NDVI Calculation**: Normalized Difference Vegetation Index
- **Cloud Filtering**: Automatic selection of clear imagery (<20% cloud cover)
- **Temporal Analysis**: Assess vegetation over custom time periods

### 📊 Comprehensive Results
- **Suitability Rating**: Optimal, Suitable, Marginal, or Poor
- **Statistical Analysis**: Mean, standard deviation, min/max NDVI
- **Spatial Visualization**: Heatmaps showing vegetation distribution
- **Distribution Charts**: Histograms of NDVI values

### 📥 Export Capabilities
- JSON reports with full assessment details
- CSV data for further analysis
- Timestamped results for record-keeping

## NDVI Thresholds for Giraffe Habitat

| Rating | NDVI Range | Description | Recommendation |
|--------|-----------|-------------|----------------|
| ✅ Optimal | 0.5 - 1.0 | Dense vegetation | Highly suitable |
| ✔️ Suitable | 0.3 - 0.5 | Moderate vegetation | Suitable with field verification |
| ⚠️ Marginal | 0.2 - 0.3 | Sparse vegetation | Requires careful evaluation |
| ❌ Poor | 0.0 - 0.2 | Little/no vegetation | Not recommended |

## How to Use

### 1. Define Your Site
Navigate to the **"Define Site"** tab and choose a method:

**Interactive Drawing:**
```
1. Click on map to start drawing
2. Click additional points to create polygon
3. Double-click to complete
```

**Shapefile Upload:**
```
1. Prepare a zip file containing .shp, .shx, .dbf files
2. Click "Upload Shapefile"
3. Select your .zip file
```

**Manual Coordinates:**
```
1. Enter coordinates one per line
2. Format: latitude, longitude
3. Example:
   -19.5, 13.5
   -19.5, 14.0
   -20.0, 14.0
   -20.0, 13.5
4. Click "Create Polygon"
```

### 2. Configure Settings
In the sidebar:
- Set analysis date range (default: last 90 days)
- Optionally customize NDVI thresholds

### 3. Run Analysis
- Switch to **"Analysis Results"** tab
- Click **"Run Assessment"**
- Wait for satellite data processing (typically 10-30 seconds)

### 4. Review Results
Examine:
- Overall suitability rating and recommendation
- NDVI statistics (mean, range, distribution)
- Spatial heatmap showing vegetation patterns
- Additional factors to consider for translocation

### 5. Export
Download results in JSON or CSV format for documentation.

## Data Sources

- **Satellite Data**: Sentinel-2 L2A (ESA)
- **Platform**: Microsoft Planetary Computer
- **Resolution**: 10 meters
- **Update Frequency**: Every 5 days
- **Coverage**: Global

## Important Considerations

### ⚠️ This is a Preliminary Assessment Tool

**What it provides:**
- Quick vegetation health assessment
- Objective, data-driven initial screening
- Baseline habitat quality metrics

**What it does NOT replace:**
- Comprehensive field surveys
- Browse species identification
- Water availability assessment
- Predator/prey population surveys
- Community consultations
- Legal/administrative reviews

### Best Practices

1. **Seasonal Analysis**: Run assessments for both wet and dry seasons
2. **Temporal Trends**: Compare multiple time periods to understand vegetation dynamics
3. **Reference Sites**: Compare candidate sites with known successful giraffe habitat
4. **Field Verification**: Always follow up with on-ground surveys
5. **Local Knowledge**: Integrate with local expertise and traditional ecological knowledge

### Comprehensive Translocation Assessment Checklist

Before any translocation, assess:

**Environmental:**
- ✅ Vegetation type and density (this tool)
- ⬜ Browse species diversity and availability
- ⬜ Water sources (permanent and seasonal)
- ⬜ Annual rainfall patterns (>400mm preferred)
- ⬜ Temperature ranges
- ⬜ Terrain and topography

**Ecological:**
- ⬜ Predator populations (lions, hyenas)
- ⬜ Prey base assessment
- ⬜ Disease prevalence
- ⬜ Existing herbivore populations
- ⬜ Carrying capacity estimates
- ⬜ Landscape connectivity

**Management:**
- ⬜ Protected area status
- ⬜ Anti-poaching infrastructure
- ⬜ Monitoring capabilities
- ⬜ Human-wildlife conflict history
- ⬜ Community support
- ⬜ Legal permissions

## Technical Details

### Satellite Data Processing

The tool uses the STAC (SpatioTemporal Asset Catalog) API to access Sentinel-2 imagery:

```python
# NDVI Calculation
NDVI = (NIR - Red) / (NIR + Red)

# Using Sentinel-2 bands:
# NIR = Band 8 (842nm)
# Red = Band 4 (665nm)
```

### API Configuration

For production use with real satellite data, configure Microsoft Planetary Computer:

1. Sign up at https://planetarycomputer.microsoft.com/
2. Get API key (currently free for research use)
3. Install required packages (see requirements.txt)
4. Configure authentication

## Troubleshooting

### "No suitable satellite imagery found"
- Try a different date range
- Area may have persistent cloud cover
- Check if coordinates are in valid range

### "Polygon won't create"
- Ensure at least 3 coordinate points
- Check coordinate format: `latitude, longitude`
- Verify latitude: -90 to 90, longitude: -180 to 180

### "Error reading shapefile"
- Ensure .zip contains .shp, .shx, and .dbf files
- Check coordinate reference system (should be geographic)
- Try exporting from GIS software as WGS84

### Map won't load
- Check internet connection
- Refresh the page
- Try a different browser

## Future Enhancements

Planned features:
- 🌧️ Precipitation data integration
- 🌡️ Temperature analysis
- 💧 Water source detection
- 📅 Multi-year temporal analysis
- 🤖 AI-powered site recommendations
- 📱 Mobile-responsive design
- 🗺️ Integration with EarthRanger
- 📊 Batch assessment of multiple sites

## Related Tools

- **Translocation Dashboard**: Track completed translocations
- **Post-Tagging Dashboard**: Monitor individual animals
- **Unit Monitoring**: Track population dynamics

## Support

For questions, issues, or feature requests:
- Contact: GCF Data Team
- Documentation: See main Twiga Tools README
- Training: Available upon request

## Version History

- **v1.0** (November 2025): Initial release
  - Interactive map drawing
  - Shapefile upload support
  - NDVI analysis from Sentinel-2
  - Export functionality

## Citation

When using this tool in reports or publications, please cite:

```
Giraffe Conservation Foundation (2025). Site Assessment Tool for Giraffe Translocation.
Twiga Tools Suite. https://github.com/Giraffe-Conservation-Foundation
```

## License

Part of the GCF Twiga Tools suite. For internal GCF use and authorized partners.
