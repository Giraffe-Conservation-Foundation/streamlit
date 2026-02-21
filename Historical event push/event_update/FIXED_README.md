# Event Update Script - FIXED & WORKING VERSION

## 🎉 What Was Fixed

The main issue was that `ecoscope.io.EarthRangerIO.patch_event()` either doesn't exist or doesn't work reliably. The script now uses the **direct EarthRanger REST API** for PATCH operations, which is proven and reliable.

### Changes Made:
1. **Direct API Access**: Uses `requests.patch()` to update events via EarthRanger's REST API
2. **OAuth2 Authentication**: Properly authenticates and gets access token 
3. **Hybrid Approach**: Uses ecoscope for reading events (which works) and direct API for updating
4. **Better Error Handling**: Shows API response codes and error messages

## 📋 Requirements

```bash
pip install ecoscope-release pandas requests
```

## 🚀 Quick Start - Test with ONE Event

### Step 1: Get an Event ID

You need the UUID of an event you want to update. You can:
- Look in EarthRanger (URL contains the UUID)
- Export event IDs from a previous upload
- Use the included `get_event_ids.py` script

### Step 2: Edit the Test CSV

Edit `single_event_test.csv`:
```csv
event_id,detail_girsam_status
1b6d83dc-f936-49a3-a37a-16c348ddb8bf,processed
```

Replace the event_id with your actual event UUID, and set the field you want to update.

### Step 3: Run Test Script

```bash
python test_update.py
```

Or for interactive mode:
```bash
python quick_test.py
```

Enter your EarthRanger credentials when prompted.

## 📊 CSV Format Guide

### Required Column
- `event_id` - UUID of the event to update (REQUIRED)

### Event Details Fields (custom nested fields)

**Option 1: Use `detail_` prefix**
```csv
event_id,detail_status,detail_sample_type
abc-123,processed,blood
```

**Option 2: Use known prefixes directly** (no `detail_` needed)
```csv
event_id,girsam_status,girsam_smpid,girsam_notes
abc-123,processed,GCF-001,Updated after lab work
```

Recognized prefixes that go into event_details automatically:
- `girsam_*` - All GIRSAM fields
- `unit_*` - Unit-related fields  
- `deployment_*` - Deployment fields
- `sample_*` - Sample fields

### Event Metadata (top-level fields)
```csv
event_id,priority,state,title
abc-123,300,active,Updated Title
```

### Location Updates
```csv
event_id,latitude,longitude
abc-123,-2.5,38.5
```

### Combined Update Example
```csv
event_id,girsam_status,girsam_notes,priority,state
abc-123,processed,Lab analysis complete,300,active
def-456,analyzed,Sequencing done,200,resolved
```

## 🎯 Common Use Cases

### Update GIRSAM Status for Multiple Events

1. Create CSV:
```csv
event_id,girsam_status
abc-123,processed
def-456,processed
ghi-789,analyzed
```

2. Run:
```bash
python update_events.py
```

3. Enter the CSV path when prompted
4. Choose preview mode first (y) to verify
5. Run again without preview (n) to apply changes

### Update Event States in Bulk

```csv
event_id,state
abc-123,resolved
def-456,resolved
ghi-789,false
```

### Add Notes to Events

```csv
event_id,girsam_notes
abc-123,Sample received at lab on 2026-01-15
def-456,Sequencing completed successfully
```

## 🔧 How It Works

1. **Authentication**: Gets OAuth2 token from EarthRanger
2. **Fetch Current Data**: Uses ecoscope to get existing event data
3. **Merge Event Details**: Combines existing event_details with your updates (doesn't overwrite other fields)
4. **PATCH Request**: Sends update via REST API
5. **Verification**: Fetches event again to confirm changes
6. **Results**: Saves detailed results to CSV file

## ✅ Success Output Example

```
🦒 EarthRanger Event Update Tool
==================================================
📁 Enter path to CSV file with updates: updates.csv

🔍 Preview only (no changes)? (y/n): n

🔐 EarthRanger Credentials
Username: your_username
Password: ********

🔐 Connecting to EarthRanger...
✅ Connected successfully!

📂 Loading CSV file: updates.csv
📊 Found 3 event(s) to update

📝 Updating event abc-123...
  🔍 Fetching current event data to merge event_details...
  📋 Current event_details: {'girsam_smpid': 'GCF-001', 'girsam_status': 'collected'}
  ✨ Merged event_details: {'girsam_smpid': 'GCF-001', 'girsam_status': 'processed'}
  📤 Sending PATCH request to API...
  🔍 Verifying update...
  ✓ Current event_details after update: {'girsam_smpid': 'GCF-001', 'girsam_status': 'processed'}
✅ Successfully updated event abc-123
Progress: 1/3 (1 successful, 0 failed)

[... continues for other events ...]

==================================================
📊 UPDATE SUMMARY
==================================================
✅ Successful: 3
❌ Failed: 0
📈 Total: 3

💾 Results saved to: update_results_20260213_143022.csv
```

## 📝 Results File

Each run creates a timestamped results file: `update_results_YYYYMMDD_HHMMSS.csv`

Contents:
```csv
event_id,success,error
abc-123,True,
def-456,True,
ghi-789,False,API returned 404: Event not found
```

## 🐛 Troubleshooting

### "Authentication failed: 401"
- Check username/password
- Verify you have access to twiga.pamdas.org
- Make sure your account has permission to edit events

### "API returned 404: Not Found"
- Event UUID is incorrect
- Event doesn't exist
- Double-check the event_id in your CSV

### "API returned 403: Forbidden"
- Your account doesn't have permission to edit this event
- Check with your system administrator

### "Could not fetch current event"
- Event exists but can't be read
- Continues with update anyway, but may overwrite other event_details

### Connection hangs or times out
- Check your internet connection
- Verify server URL (default: https://twiga.pamdas.org)
- Try again - temporary network issue

## 📚 Additional Scripts

- **`update_events.py`** - Main batch update script (use this for production)
- **`quick_test.py`** - Interactive single event test (good for first-time testing)  
- **`test_update.py`** - Non-interactive test using single_event_test.csv
- **`get_event_ids.py`** - Helper to export event IDs from EarthRanger

## 💡 Tips

1. **Always test first**: Use preview mode or `single_event_test.csv` before bulk updates
2. **Keep backups**: Save your original event data before making changes
3. **Check results**: Review the results CSV file after each run
4. **One field at a time**: When learning, update one field type first (e.g., just status)
5. **Event_details merges**: New fields are added to existing event_details, not replaced

## 🔒 Security

- Credentials are never saved
- Use `getpass` for password input (not visible on screen)
- OAuth2 tokens are temporary and session-specific

## 📧 Support

For issues or questions:
- Check the [README.md](README.md) for general usage
- Review [QUICKSTART.md](QUICKSTART.md) for step-by-step guide
- Contact GCF data team for EarthRanger access issues

---

**Last Updated**: February 13, 2026  
**Version**: 2.0 (Direct API)  
**Status**: ✅ TESTED & WORKING
