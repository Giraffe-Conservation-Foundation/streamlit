# Mortality Event Historical Upload

Upload historical mortality events to EarthRanger for display in the Mortality Dashboard.

## Quick Start

### 1. Prepare Your CSV File

Use the template `mortality_events_template.csv` as a starting point. Your CSV should have:

**Required Columns:**
- `event_datetime` - ISO format timestamp (e.g., `2024-01-15T10:30:00Z`)

**Location Columns (optional but recommended):**
- `latitude` - Decimal degrees (e.g., `-15.123456`)
- `longitude` - Decimal degrees (e.g., `28.456789`)

**Detail Columns (all start with `details_`):**
- `details_mortality_cause` - **IMPORTANT**: Type and cause (see format below)
- `details_gir_species` - Species name (e.g., `Giraffa giraffa`)
- `details_gir_sex` - Sex (`Male`, `Female`, `Unknown`)
- `details_gir_age` - Age class (`Adult`, `Juvenile`, `Sub-adult`, `Elderly`, `Calf`)
- `details_country` - Country ISO code (e.g., `NAM`, `ZAF`, `BWA`)
- `details_individual_id` - Unique identifier for the individual (e.g., `G001_NAM_2024`)
- `details_location_name` - Location description (e.g., `Etosha National Park`)
- `details_notes` - Additional notes or observations

### 2. Mortality Cause Format

The `details_mortality_cause` field must follow this format: `{type}_{cause}`

**Natural Causes:**
- `natural_predation` - Death by predator
- `natural_disease` - Disease-related death
- `natural_starvation` - Death from starvation
- `natural_old_age` - Natural death from old age
- `natural_drought` - Death related to drought conditions
- `natural_unknown` - Natural death, unknown specific cause

**Unnatural Causes:**
- `unnatural_vehicle_collision` - Hit by vehicle
- `unnatural_poaching` - Poaching incident
- `unnatural_immobilisation` - Complications during immobilization/capture
- `unnatural_wire_snare` - Snare/trap related death
- `unnatural_human_conflict` - Human-wildlife conflict
- `unnatural_unknown` - Unnatural death, unknown specific cause

**Unknown:**
- `Unknown` - When mortality cause is completely unknown

### 3. Run the Upload Script

```bash
python mortality_upload.py
```

The script will:
1. Prompt for your CSV file path
2. Show a preview of your data
3. Validate mortality cause formats
4. Ask for EarthRanger credentials
5. Upload events one by one with progress tracking
6. Generate a report of successful/failed uploads

## Example CSV Format

```csv
serial_number,event_datetime,latitude,longitude,details_mortality_cause,details_gir_species,details_gir_sex,details_gir_age,details_country,details_individual_id,details_location_name,details_notes
1,2024-01-15T10:30:00Z,-15.123456,28.456789,natural_predation,Giraffa giraffa,Female,Adult,NAM,G001_NAM_2024,Etosha National Park,Lion predation - carcass found near waterhole
2,2024-02-20T14:15:00Z,-16.234567,29.567890,natural_disease,Giraffa giraffa,Male,Juvenile,NAM,G002_NAM_2024,Caprivi Strip,Suspected anthrax - no trauma observed
3,2024-03-05T09:45:00Z,-17.345678,30.678901,natural_old_age,Giraffa camelopardalis,Male,Elderly,ZAF,G003_ZAF_2024,Kruger National Park,Natural death - elderly individual found near rest site
```

## Event Structure

Events are uploaded with:
- **Event Type:** `mortality` (changed from `giraffe_mortality` to support all wildlife)
- **Event Category:** `veterinary`
- **Priority:** 300 (High)
- **State:** `new`

## Viewing Your Data

After upload, view your events in the **Mortality Dashboard**:
- URL: https://twiga.pamdas.org (login required)
- Navigate to the Mortality Dashboard
- Filter by date range, country, species, or mortality type
- View maps, charts, and detailed event information

## Dashboard Features

The dashboard parses your `mortality_cause` field to provide:
- **Natural vs Unnatural** classification
- **Cause breakdown** (predation, disease, vehicle collision, etc.)
- **Geographic distribution** by country
- **Species analysis**
- **Sex and age demographics**
- **Temporal trends** (monthly, yearly)

## Troubleshooting

### Invalid Mortality Cause Format
If you see warnings about invalid mortality causes:
1. Check that each cause follows the `{type}_{cause}` pattern
2. Use `Unknown` for completely unknown causes
3. Ensure no typos (e.g., `natual_` instead of `natural_`)

### Authentication Failed
- Verify your EarthRanger credentials
- Ensure you have permission to create events
- Check that the server URL is correct (`https://twiga.pamdas.org`)

### Upload Failures
- Review the `failed_mortality_upload_{timestamp}.json` file
- Common issues: invalid datetime format, missing required fields
- Fix issues in your CSV and re-run the script

### Events Not Appearing in Dashboard
- Ensure `event_type` is set to `mortality` (not `giraffe_mortality`)
- Check that events fall within your selected date range
- Verify that filters aren't excluding your events
- Refresh the dashboard data

## Requirements

```bash
pip install pandas requests
```

## Files

- `mortality_upload.py` - Main upload script
- `mortality_events_template.csv` - CSV template with examples
- `MORTALITY_UPLOAD_README.md` - This documentation

## Notes

- The dashboard now uses generic `mortality` event type (changed from `giraffe_mortality`)
- All detail fields are optional except `event_datetime`
- Use ISO 8601 datetime format with timezone (recommended: `Z` for UTC)
- Coordinates of 0,0 will be stored but won't display on maps
- Failed uploads are saved for retry

## Support

For issues or questions, contact the development team or refer to the main Historical Event Push documentation.
