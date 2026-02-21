# QUICK START - Test with 1 Event

Follow these steps to test updating a single event:

## Option 1: Interactive Test (Easiest!)

Run the quick test script that walks you through everything:

```bash
cd "g:\My Drive\Data management\streamlit\Historical event push\event_update"
python quick_test.py
```

You'll be prompted for:
1. The event UUID you want to update
2. What fields to update (status, sample_type, etc.)
3. Your EarthRanger credentials

Then it updates the event immediately!

---

## Option 2: CSV Method (For Batch Later)

### Step 1: Find Your Event ID

If you don't have an event UUID yet, run:

```bash
python get_event_ids.py
```

This will:
- Show you all your events
- Export them with their UUIDs
- Save to a CSV file

### Step 2: Create Test CSV

Edit `single_event_test.csv` and replace the placeholder:

```csv
event_id,detail_status
YOUR-ACTUAL-EVENT-UUID-HERE,processed
```

Example with real UUID:
```csv
event_id,detail_status
c8a7b9e2-3f4d-4e8a-9c1b-2d5f6a7e8b9c,processed
```

### Step 3: Run Preview

```bash
python update_events.py
```

- Enter file path: `single_event_test.csv`
- Preview only: `y` (YES for first test!)
- Enter your credentials

This shows you what WOULD be updated without making changes.

### Step 4: Run Actual Update

Run again with preview: `n` to actually update the event.

---

## Finding Your Event UUID

### From EarthRanger UI:
1. Open the event in EarthRanger
2. Look at the browser URL
3. The UUID is in the path like: `.../event/abc-123-def/...`

### From Upload Results:
If you saved results from when you uploaded, the event IDs are there.

### Using the Helper Script:
```bash
python get_event_ids.py
```

---

## What Can You Update?

### Event Details (custom fields in event_details):
- `detail_status` → Sample status (collected, processed, analyzed, etc.)
- `detail_sample_type` → Sample type (blood, tissue, hair, etc.)
- `detail_notes` → Any notes
- `detail_<any_field>` → Any other custom field

### Event Metadata:
- `priority` → Priority number (200, 300, etc.)
- `state` → Event state (new, active, resolved, false)
- `title` → Event title

### Location:
- `latitude` + `longitude` → Update location

---

## Example Test Scenarios

### Change status to "processed":
```csv
event_id,detail_status
abc-123,processed
```

### Change status and sample type:
```csv
event_id,detail_status,detail_sample_type
abc-123,processed,blood
```

### Full update:
```csv
event_id,detail_status,detail_sample_type,priority,state,title
abc-123,processed,blood,300,active,Biosample - Processed
```

---

## Troubleshooting

**Can't connect?**
- Check username/password
- Make sure you're connected to internet

**Update fails?**
- Verify the event UUID is correct (copy-paste it!)
- Check that you have permission to edit events
- Ensure the field names match your event schema

**Need help?**
Just read the full [README.md](README.md) for detailed documentation.

---

## After Your Test

Once you successfully update 1 event:
1. ✅ Check EarthRanger to see the change
2. 📝 Prepare a CSV with all events you want to update
3. 🚀 Run the batch update with confidence!

Good luck! 🦒
