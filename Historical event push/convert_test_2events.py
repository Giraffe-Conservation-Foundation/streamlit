#!/usr/bin/env python3
"""
Convert first 2 mortality events for testing with timezone handling
"""

import pandas as pd
from datetime import datetime, timedelta

# Load the original CSV (try different encodings)
try:
    df = pd.read_csv("mortality_260114.csv", encoding='utf-8')
except UnicodeDecodeError:
    try:
        df = pd.read_csv("mortality_260114.csv", encoding='latin-1')
    except:
        df = pd.read_csv("mortality_260114.csv", encoding='cp1252')

# Take only first 2 rows for testing
df = df.head(2)

print(f"📊 Processing {len(df)} test records")
print("\nOriginal data:")
print(df[['date', 'country', 'gir_species', 'mortality_cause']].to_string())

# Timezone mapping (hours to subtract to get UTC)
timezone_offsets = {
    'ken': 3,  # Kenya is GMT+3
    'ago': 1,  # Angola is GMT+1
    'nam': 2,  # Namibia is GMT+2 (can vary)
    'tza': 3,  # Tanzania is GMT+3
    'zmb': 2,  # Zambia is GMT+2
    'zaf': 2,  # South Africa is GMT+2
    'bwa': 2,  # Botswana is GMT+2
}

def convert_date_with_timezone(date_str, country_code):
    """Convert date from DD-MM-YY HH:MM (local time) to UTC ISO 8601"""
    try:
        # Parse the date
        dt = datetime.strptime(date_str, "%d-%m-%y %H:%M")
        
        # Apply timezone offset to convert to UTC
        offset_hours = timezone_offsets.get(country_code.lower(), 0)
        dt_utc = dt - timedelta(hours=offset_hours)
        
        # Format to ISO 8601 with Z timezone
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    except Exception as e:
        print(f"⚠️ Error converting date '{date_str}': {e}")
        return date_str

print("\n🔄 Converting dates with timezone adjustment...")
df['event_datetime'] = df.apply(
    lambda row: convert_date_with_timezone(row['date'], row['country']), 
    axis=1
)

# Show timezone conversions
print("\nTimezone conversions:")
for idx, row in df.iterrows():
    print(f"  {row['country'].upper()}: {row['date']} (local) → {row['event_datetime']} (UTC)")

# Rename columns to add details_ prefix
column_mapping = {
    'country': 'details_country',
    'gir_species': 'details_gir_species',
    'gir_sex': 'details_gir_sex',
    'gir_age': 'details_gir_age',
    'mortality_cause': 'details_mortality_cause',
    'notes': 'details_notes'
}

df = df.rename(columns=column_mapping)

# Keep only the needed columns in the correct order
columns_order = [
    'event_datetime',
    'latitude',
    'longitude',
    'details_mortality_cause',
    'details_gir_species',
    'details_gir_sex',
    'details_gir_age',
    'details_country',
    'details_notes'
]

# Select only available columns
available_columns = [col for col in columns_order if col in df.columns]
df_final = df[available_columns]

# Save the converted file
output_file = "mortality_test_2events.csv"
df_final.to_csv(output_file, index=False)

print(f"\n✅ Conversion complete!")
print(f"📁 Saved to: {output_file}")
print(f"📊 Test records: {len(df_final)}")
print("\n📋 Preview of converted data:")
print(df_final.to_string())
print(f"\n🚀 Ready to upload! Run:")
print(f"   python mortality_upload.py")
print(f"\n   Then enter: {output_file}")
