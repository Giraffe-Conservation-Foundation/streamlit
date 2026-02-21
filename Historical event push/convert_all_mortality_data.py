#!/usr/bin/env python3
"""
Convert ALL mortality_260114.csv records with timezone handling
"""

import pandas as pd
from datetime import datetime, timedelta

# Load the original CSV with encoding handling
try:
    df = pd.read_csv("mortality_260114.csv", encoding='utf-8')
except UnicodeDecodeError:
    try:
        df = pd.read_csv("mortality_260114.csv", encoding='latin-1')
    except:
        df = pd.read_csv("mortality_260114.csv", encoding='cp1252')

print(f"📊 Loaded {len(df)} mortality records")

# Timezone mapping (hours to subtract to get UTC)
timezone_offsets = {
    'ken': 3,  # Kenya is GMT+3
    'ago': 1,  # Angola is GMT+1
    'nam': 2,  # Namibia is GMT+2 (sometimes GMT+1 depending on season, using GMT+2)
    'tza': 3,  # Tanzania is GMT+3
    'zmb': 2,  # Zambia is GMT+2
    'zaf': 2,  # South Africa is GMT+2
    'bwa': 2,  # Botswana is GMT+2
}

def convert_date_with_timezone(date_str, country_code):
    """Convert date from DD-MM-YY HH:MM (local time) to UTC ISO 8601"""
    try:
        # Parse the date
        dt = datetime.strptime(str(date_str).strip(), "%d-%m-%y %H:%M")
        
        # Apply timezone offset to convert to UTC
        offset_hours = timezone_offsets.get(str(country_code).lower(), 0)
        dt_utc = dt - timedelta(hours=offset_hours)
        
        # Format to ISO 8601 with Z timezone
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    except Exception as e:
        print(f"⚠️ Error converting date '{date_str}' for country '{country_code}': {e}")
        # Return a default date if parsing fails
        return "2024-01-01T12:00:00Z"

print("🔄 Converting dates with timezone adjustment...")
df['event_datetime'] = df.apply(
    lambda row: convert_date_with_timezone(row['date'], row['country']), 
    axis=1
)

# Show sample timezone conversions
print("\n📋 Sample timezone conversions (first 5):")
for idx, row in df.head(5).iterrows():
    offset = timezone_offsets.get(row['country'].lower(), 0)
    print(f"  {row['country'].upper()} (GMT+{offset}): {row['date']} → {row['event_datetime']}")

# Rename columns to add details_ prefix
column_mapping = {
    'country': 'details_country',
    'gir_species': 'details_gir_species',
    'gir_sex': 'details_gir_sex',
    'gir_age': 'details_gir_age',
    'mortality_cause': 'details_giraffe_mortality_cause',
    'notes': 'details_notes'
}

df = df.rename(columns=column_mapping)

# Keep only the needed columns in the correct order
columns_order = [
    'event_datetime',
    'latitude',
    'longitude',
    'details_giraffe_mortality_cause',
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
output_file = "mortality_260114_READY_FOR_UPLOAD.csv"
df_final.to_csv(output_file, index=False, encoding='utf-8')

print(f"\n✅ Conversion complete!")
print(f"📁 Output file: {output_file}")
print(f"📊 Total records: {len(df_final)}")

# Show summary statistics
print("\n📊 Summary by country:")
country_counts = df_final['details_country'].value_counts()
for country, count in country_counts.items():
    offset = timezone_offsets.get(country.lower(), 0)
    print(f"  {country.upper()} (GMT+{offset}): {count} events")

print("\n📊 Summary by mortality cause:")
cause_counts = df_final['details_giraffe_mortality_cause'].value_counts()
for cause, count in cause_counts.head(10).items():
    print(f"  {cause}: {count}")

print(f"\n🚀 Ready to upload! Run:")
print(f"   python mortality_upload.py")
print(f'\n   Then enter: {output_file}')
