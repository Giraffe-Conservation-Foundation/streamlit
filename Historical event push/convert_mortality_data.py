#!/usr/bin/env python3
"""
Convert mortality_260114.csv to the correct format for upload
"""

import pandas as pd
from datetime import datetime

# Load the original CSV
df = pd.read_csv("mortality_260114.csv")

print(f"📊 Loaded {len(df)} mortality records")

# Convert date format from DD-MM-YY HH:MM to ISO 8601
def convert_date(date_str):
    """Convert date from 22-07-25 8:47 to 2025-07-22T08:47:00Z"""
    try:
        # Parse the date
        dt = datetime.strptime(date_str, "%d-%m-%y %H:%M")
        # Format to ISO 8601 with Z timezone
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    except Exception as e:
        print(f"⚠️ Error converting date '{date_str}': {e}")
        return date_str

print("🔄 Converting date format...")
df['event_datetime'] = df['date'].apply(convert_date)

# Rename columns to add details_ prefix
column_mapping = {
    'country': 'details_country',
    'gir_species': 'details_gir_species',
    'gir_sex': 'details_gir_sex',
    'gir_age': 'details_gir_age',
    'mortality_cause': 'details_mortality_cause',
    'notes': 'details_notes'
}

print("📝 Renaming columns...")
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

# Remove rows with missing critical data (optional - uncomment if needed)
# df_final = df_final.dropna(subset=['event_datetime'])

# Save the converted file
output_file = "mortality_260114_converted.csv"
df_final.to_csv(output_file, index=False)

print(f"✅ Conversion complete!")
print(f"📁 Saved to: {output_file}")
print(f"📊 Records: {len(df_final)}")
print("\n🚀 Ready to upload! Run:")
print(f"   python mortality_upload.py")
print(f"\n   Then enter: {output_file}")
