# Event Update Script - Fixed Version

## What Was Fixed

### 1. **Correct API Parameter Format**
The `patch_event` method was being called with `events=update_data` but ecoscope's EarthRangerIO expects the update data to be unpacked as keyword arguments. Changed from:
```python
er_io.patch_event(event_id=event_id, events=update_data)
```
To:
```python
er_io.patch_event(event_id=event_id, **update_data)
```

### 2. **Support for Nested event_details Fields**
Added automatic detection of common event_details field prefixes so you no longer need to prefix columns with `detail_`. The script now recognizes these prefixes automatically:
- `girsam_*` (e.g., girsam_status, girsam_notes, girsam_smpid)
- `unit_*`
- `deployment_*`
- `sample_*`

### 3. **Verification After Update**
Added post-update verification that fetches the event again and displays the updated event_details to confirm the changes were applied.

## How to Use

### CSV Format for GIRSAM Status Updates

Create a CSV file with at least these columns:
- `event_id` (required) - The UUID of the event to update
- Any `girsam_*` fields you want to update

**Example CSV** (saved as `update_girsam_example.csv`):
```csv
event_id,girsam_status,girsam_notes
abc123-def456-789012,processed,Updated after lab analysis
def456-ghi789-012345,analyzed,Sample sequencing complete
```

### Supported Update Fields

#### Event Metadata (direct fields):
- `priority` - Event priority (integer, e.g., 200, 300)
- `state` - Event state (new/active/resolved/false)
- `title` - Event title
- `latitude`, `longitude` - Location update

#### Event Details (nested in event_details):
Any field that starts with:
- `girsam_*` - All GIRSAM fields (status, smpid, species, age, sex, etc.)
- `unit_*` - Unit-related fields
- `deployment_*` - Deployment-related fields
- `sample_*` - Sample-related fields
- `detail_*` - Generic detail fields (remove 'detail_' prefix)

### Running the Script

#### Option 1: Interactive Test (Single Event)
```bash
python quick_test.py
```
Best for testing one event at a time.

#### Option 2: Batch Update from CSV
```bash
python update_events.py
```
Then enter the path to your CSV file.

### Example Session
```
🦒 EarthRanger Event Update Tool
==================================================
📁 Enter path to CSV file with updates: update_girsam_example.csv

🔍 Preview only (no changes)? (y/n): n

🔐 EarthRanger Credentials
Username: your_username
Password: ********

🔐 Connecting to EarthRanger...
✅ Connected successfully!

📂 Loading CSV file: update_girsam_example.csv
📊 Found 2 event(s) to update

📝 Updating event abc123-def456-789012...
  🔍 Fetching current event data to merge event_details...
  📋 Current event_details: {'girsam_smpid': 'EI17027 GITi A', 'girsam_status': 'collected', ...}
  ✨ Merged event_details: {'girsam_smpid': 'EI17027 GITi A', 'girsam_status': 'processed', ...}
  🔍 Verifying update...
  ✓ Current event_details after update: {'girsam_smpid': 'EI17027 GITi A', 'girsam_status': 'processed', ...}
✅ Successfully updated event abc123-def456-789012
```

## Troubleshooting

### "Success but no update"
This should now be fixed! The script will:
1. Merge your updates with existing event_details (so other fields aren't lost)
2. Use the correct API format
3. Verify the update succeeded

### CSV Column Names
You can use these formats interchangeably:
- `girsam_status` ✓ (automatic)
- `detail_girsam_status` ✓ (also works)

### Checking Updates in EarthRanger
After running the script:
1. Look for the verification output showing the updated event_details
2. Check the event in EarthRanger web interface
3. The event's event_details should show your changes

## Files Updated
- `update_events.py` - Main batch update script
- `quick_test.py` - Interactive single-event tester
- `update_girsam_example.csv` - Example CSV template
