import pandas as pd
import getpass
from mortality_upload import MortalityEventUploader

# Load CSV
print("Loading CSV...")
try:
    df = pd.read_csv('mortality_260115_READY_FOR_UPLOAD.csv', encoding='utf-8')
except:
    df = pd.read_csv('mortality_260115_READY_FOR_UPLOAD.csv', encoding='latin-1')

# Extract rows 14-15 (index 13-14)
df_subset = df.iloc[13:15].copy()
print(f"\nRows to upload: {len(df_subset)}")
print("\nRow 14:")
print(f"  event_datetime: {df_subset.iloc[0]['event_datetime']}")
print("\nRow 15:")
print(f"  event_datetime: {df_subset.iloc[1]['event_datetime']}")

# Get credentials
print("\n🔐 EarthRanger Authentication")
username = input("Username: ")
password = getpass.getpass("Password: ")

# Create uploader
uploader = MortalityEventUploader()
uploader.server_url = 'https://twiga.pamdas.org'

if not uploader.authenticate(username, password):
    print("❌ Authentication failed")
    exit(1)

if not uploader.test_connection():
    print("❌ API connection test failed")
    exit(1)

print("✅ API connection successful!")

# Confirm
proceed = input(f"\n❓ Upload these 2 rows? (y/N): ").lower().strip()
if proceed != 'y':
    print("❌ Cancelled")
    exit(0)

# Upload
print("\n🚀 Uploading...")
successful = 0
failed = 0

for index, row in df_subset.iterrows():
    try:
        event_time = str(row.get('event_datetime', '2024-01-01T12:00:00Z'))
        if not event_time.endswith('Z') and '+' not in event_time:
            event_time = event_time + 'Z'
        
        event = {
            'event_type': 'giraffe_mortality',
            'event_category': 'veterinary',
            'title': 'Mortality Event',
            'time': event_time,
            'state': 'new',
            'priority': 300,
            'is_collection': False,
            'event_details': {}
        }
        
        # Add location
        if (pd.notna(row.get('latitude')) and pd.notna(row.get('longitude')) and
            float(row.get('latitude', 0)) != 0 and float(row.get('longitude', 0)) != 0):
            event['location'] = {
                'latitude': float(row['latitude']),
                'longitude': float(row['longitude'])
            }
        
        # Add details
        for col in df_subset.columns:
            if col.startswith('details_') and pd.notna(row[col]):
                key = col.replace('details_', '')
                if key == 'mortality_cause':
                    key = 'giraffe_mortality_cause'
                event['event_details'][key] = str(row[col])
        
        # Add giraffe_id
        if 'giraffe_id' in df_subset.columns and pd.notna(row['giraffe_id']):
            event['event_details']['giraffe_id'] = str(row['giraffe_id'])
        
        # Upload
        result = uploader.upload_event(event)
        
        if result['success']:
            successful += 1
            print(f"✅ Row {index + 1} uploaded successfully")
        else:
            failed += 1
            print(f"❌ Row {index + 1} failed: {result['error']}")
    
    except Exception as e:
        failed += 1
        print(f"❌ Row {index + 1} error: {str(e)}")

print(f"\n📊 Summary: {successful} successful, {failed} failed")
