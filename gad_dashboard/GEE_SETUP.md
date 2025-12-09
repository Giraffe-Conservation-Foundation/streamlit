# Quick Start: Google Earth Engine Setup

## Why GEE for BII?

✅ **No local storage** - BII dataset is ~several GB, GEE handles it in the cloud
✅ **Always up-to-date** - No need to re-download datasets
✅ **Fast queries** - Optimized for spatial point extraction
✅ **Multiple resolutions** - 1km and 8km available
✅ **Detailed metrics** - Get BII for mammals, birds, reptiles, plants separately
✅ **Free** - Google Earth Engine is free for research/conservation use

## One-Time Setup (5 minutes)

### Step 1: Install Earth Engine API
```bash
pip install earthengine-api
```

### Step 2: Authenticate
```bash
earthengine authenticate
```

This will:
1. Open your web browser
2. Ask you to sign in with a Google account
3. Generate an authentication token
4. Save credentials locally

**Note**: You need a Google account (free Gmail account works fine)

### Step 3: Verify Installation
```bash
earthengine user info
```

You should see your email address and project details.

## Using BII in the App

Once authenticated, the app will automatically:
1. Connect to Google Earth Engine when you click "Auto-Populate"
2. Extract BII values at your coordinates (8km resolution by default)
3. Return detailed metrics:
   - **BII All** - Overall biodiversity intactness (0-1)
   - **BII Mammals** - Mammal intactness
   - **BII Birds** - Bird intactness
   - **BII Reptiles** - Reptile intactness
   - **BII Plants** - Plant intactness
   - **Land Use** - Primary, Secondary, Cropland, Pasture, etc.
   - **Land Use Intensity** - How intensively the land is used

4. Convert BII All (0-1) to Connectivity Rank (1-5):
   - 0.8-1.0 → Rank 5 (Very High)
   - 0.6-0.8 → Rank 4 (High)
   - 0.4-0.6 → Rank 3 (Moderate)
   - 0.2-0.4 → Rank 2 (Low)
   - 0.0-0.2 → Rank 1 (Very Low)

## Troubleshooting

### "Earth Engine not authenticated"
Run: `earthengine authenticate --force`

### "ImportError: No module named 'ee'"
Run: `pip install earthengine-api`

### Slow queries
- Normal - GEE queries take 2-5 seconds per point
- Using 8km resolution (faster than 1km)
- Results are cached for 1 hour

### Rate limits
- GEE has generous rate limits
- You can query hundreds of points per session
- If you hit limits, wait 5 minutes

### Authentication expired
Re-run: `earthengine authenticate`

## BII Dataset Information

**Source**: Biodiversity Intactness Index from Natural History Museum London
**GEE Asset**: `projects/earthengine-legacy/assets/projects/sat-io/open-datasets/BII/`
**Reference**: [BII on Awesome GEE Community Datasets](https://samapriya.github.io/awesome-gee-community-datasets/projects/bii/)

**What is BII?**
- Measures average abundance of species compared to undisturbed habitat
- Scale: 0 (completely degraded) to 1 (pristine)
- Accounts for land use and land use intensity
- Available globally at 1km and 8km resolution

**Why 8km for translocation assessment?**
- Faster queries (good for point-based analysis)
- Appropriate scale for landscape connectivity
- Regional-level planning (protected area suitability)
- Can switch to 1km if needed (just change `resolution='1km'` in code)

## Advanced: Custom BII Queries

If you want to customize the BII extraction, edit `get_bii_from_gee()` function:

```python
# Switch to 1km resolution
bii_data = get_bii_from_gee(lat, lon, resolution='1km')

# Access specific metrics
bii_mammals = bii_data['bii_mammals']
bii_birds = bii_data['bii_birds']
land_use = bii_data['land_use']
```

## Cost

**Free!** Google Earth Engine is free for:
- Research
- Education
- Non-profit conservation work

Commercial use requires registration but is also available.

## Next Steps

After BII integration works, you could add:
1. **Habitat suitability** - Species-specific rasters from GEE
2. **Human footprint** - Global Human Modification dataset
3. **Climate data** - Precipitation, temperature from GEE
4. **Vegetation indices** - NDVI, EVI from GEE
5. **Protected area boundaries** - WDPA is also on GEE!

All available through the same GEE API - no local storage needed! 🌍
