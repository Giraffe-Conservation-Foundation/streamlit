import pandas as pd
from ecoscope.io.earthranger import EarthRangerIO
from datetime import datetime
import getpass

# Get credentials
print("EarthRanger Login")
username = input("Username: ")
password = getpass.getpass("Password: ")

# Connect to EarthRanger
print('\nConnecting to EarthRanger...')
er_io = EarthRangerIO(
    server='https://twiga.pamdas.org',
    username=username,
    password=password
)

print('Fetching monitoring events...')
# Get events
gdf_events = er_io.get_events(
    event_category='monitoring',
    include_details=True,
    include_notes=True,
    max_results=10000
)

print(f'Total events fetched: {len(gdf_events)}')

# Convert to DataFrame
df = pd.DataFrame(gdf_events.drop(columns='geometry', errors='ignore'))

print(f'Event types found: {df["event_type"].unique() if "event_type" in df.columns else "No event_type column"}')

# Filter for unit_update event_type
if 'event_type' in df.columns:
    df_unit = df[df['event_type'] == 'unit_update'].copy()
    print(f'\nUnit update events: {len(df_unit)}')
    
    if len(df_unit) > 0:
        # Show sample of event_details to understand structure
        print("\nSample event_details structure:")
        if 'event_details' in df_unit.columns:
            first_details = df_unit.iloc[0]['event_details']
            if isinstance(first_details, dict):
                print(f"Keys in event_details: {list(first_details.keys())}")
        
        # Export to CSV
        output_file = 'unitupdate_events_export.csv'
        df_unit.to_csv(output_file, index=False)
        print(f'\n✅ Exported {len(df_unit)} events to: {output_file}')
        print(f'Columns: {list(df_unit.columns)}')
    else:
        print("\n⚠️ No unitupdate events found")
else:
    print("\n❌ No event_type column in data")
