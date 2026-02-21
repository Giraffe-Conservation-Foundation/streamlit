# EarthRanger Event Update Tool

Update existing events in EarthRanger using the ecoscope library.

## Features

- ✅ Update event details fields (status, sample_type, etc.)
- ✅ Update event metadata (priority, state, title)
- ✅ Update event locations
- ✅ Batch updates from CSV
- ✅ Dry-run preview mode
- ✅ Detailed results logging

## Installation

```bash
pip install ecoscope-release pandas
```

## Quick Start - Test with Single Event

### Step 1: Get Your Event ID

First, you need the UUID of the event you want to update. You can find this by:
- Looking in EarthRanger (the event URL contains the UUID)
- Checking your original upload results
- Using the EarthRanger API to search for events

### Step 2: Prepare CSV File

Edit `single_event_test.csv` and replace `PASTE-YOUR-EVENT-UUID-HERE` with your actual event UUID:

```csv
event_id,detail_status
abc123-def456-ghi789,processed
```

### Step 3: Run Test Update

```bash
python update_events.py
```

When prompted:
1. Enter path to your CSV file: `single_event_test.csv`
2. Choose preview mode first: `y` (to see what will happen)
3. Enter your EarthRanger credentials

### Step 4: Run Actual Update

Once you're happy with the preview, run again with preview mode: `n`

## CSV Format

### Required Column
- `event_id` - The UUID of the event to update

### Optional Columns

#### Event Details (custom fields)
Prefix any column with `detail_` to update event_details fields:

- `detail_status` - Sample status (e.g., "collected", "processed", "analyzed")
- `detail_sample_type` - Type of sample (e.g., "blood", "tissue", "hair")
- `detail_notes` - Additional notes
- `detail_<any_field>` - Any custom field in your event schema

#### Event Metadata
Standard event fields:

- `priority` - Priority level (integer, e.g., 200, 300)
- `state` - Event state ("new", "active", "resolved", "false")
- `title` - Event title

#### Location
Update event location:

- `latitude` - Latitude coordinate
- `longitude` - Longitude coordinate

## Examples

### Example 1: Update Sample Status Only

```csv
event_id,detail_status
abc-123,processed
def-456,analyzed
ghi-789,processed
```

### Example 2: Update Multiple Fields

```csv
event_id,detail_status,detail_sample_type,priority,state
abc-123,processed,blood,300,active
def-456,analyzed,tissue,200,resolved
```

### Example 3: Update Status and Location

```csv
event_id,detail_status,latitude,longitude
abc-123,processed,-2.5,38.5
```

### Example 4: Full Update (like template)

```csv
event_id,detail_status,detail_sample_type,priority,state,title
abc-123,processed,blood,300,active,Biological Sample - Processed
```

## Common Use Cases

### Change Biosample Status from "collected" to "processed"

1. Export your biosample events with their UUIDs
2. Create CSV with two columns: `event_id` and `detail_status`
3. Set `detail_status` to "processed" for all rows
4. Run the update script

### Bulk Location Corrections

1. Prepare CSV with: `event_id`, `latitude`, `longitude`
2. Run in preview mode first
3. Verify changes
4. Run actual update

### Update Event States

1. Create CSV with: `event_id`, `state`
2. Set state to "resolved" for completed events
3. Run update

## Output

The script generates a results file: `update_results_YYYYMMDD_HHMMSS.csv`

This contains:
- `event_id` - Event that was updated
- `success` - True/False
- `error` - Error message if failed

## Tips

1. **Always test first**: Use preview mode (y) to see what will happen
2. **Start small**: Test with 1 event before bulk updates
3. **Keep backups**: Save your original data before bulk updates
4. **Check results**: Review the results CSV after each run
5. **Event IDs are critical**: Make sure you have the correct UUIDs

## Troubleshooting

### "Failed to connect"
- Check your username and password
- Verify server URL in script (default: twiga.pamdas.org)

### "Failed to update event"
- Verify the event UUID is correct
- Check that you have permission to edit the event
- Ensure field names match your event schema

### "CSV must have 'event_id' column"
- Your CSV needs at least the `event_id` column

## Finding Event IDs

### Method 1: From EarthRanger UI
1. Open the event in EarthRanger
2. Look at the URL - the UUID is in the path
3. Example: `.../event/abc-123-def-456/` → UUID is `abc-123-def-456`

### Method 2: Export from Previous Upload
If you saved results from your original upload, the event IDs are there.

### Method 3: Query EarthRanger
Use ecoscope to get events:

```python
from ecoscope.io import EarthRangerIO

er_io = EarthRangerIO(server="https://twiga.pamdas.org", username="...", password="...")

# Get events by type
events = er_io.get_events(
    event_type=["your-event-type-uuid"],
    since="2024-01-01",
    until="2025-12-31"
)

# Save event IDs
events[['title', 'time']].to_csv('event_ids.csv')
```

## Support

For issues or questions, contact the Giraffe Conservation Foundation data team.
