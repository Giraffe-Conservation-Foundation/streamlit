#!/usr/bin/env python3
"""
EarthRanger JSON Export Tool
===========================

Creates properly formatted JSON files for manual import into EarthRanger.

Usage:
    python export_for_earthranger.py

Requirements:
    pip install pandas

Author: Giraffe Conservation Foundation
Date: August 2025
"""

import pandas as pd
import json
import sys
import os
from datetime import datetime

def main():
    """Export CSV to EarthRanger-compatible JSON"""
    print("🦒 EarthRanger JSON Export Tool")
    print("=" * 40)
    
    # Get CSV file
    csv_file = input("📁 Enter path to CSV file: ").strip().strip('"')
    
    if not os.path.exists(csv_file):
        print(f"❌ File not found: {csv_file}")
        return
    
    # Load CSV
    try:
        print(f"📖 Loading CSV file: {csv_file}")
        df = pd.read_csv(csv_file)
        print(f"✅ Loaded {len(df)} rows")
    except Exception as e:
        print(f"❌ Error loading CSV: {str(e)}")
        return
    
    # Show preview
    print("\n📋 DATA PREVIEW:")
    print(df.head(3))
    
    # Convert to EarthRanger format
    events = []
    
    for index, row in df.iterrows():
        try:
            event = {
                'event_type': 'biological_sample',
                'title': 'Biological Sample',
                'time': str(row.get('event_datetime', '2024-01-01T12:00:00Z')),
                'state': 'new',
                'priority': 200,
                'is_collection': False,
                'event_details': {}
            }
            
            # Add location if available
            if (pd.notna(row.get('latitude')) and pd.notna(row.get('longitude')) and
                float(row.get('latitude', 0)) != 0 and float(row.get('longitude', 0)) != 0):
                event['location'] = {
                    'latitude': float(row['latitude']),
                    'longitude': float(row['longitude'])
                }
            
            # Add details
            for col in df.columns:
                if col.startswith('details_') and pd.notna(row[col]):
                    key = col.replace('details_', '')
                    event['event_details'][key] = str(row[col])
            
            events.append(event)
            
        except Exception as e:
            print(f"⚠️ Warning: Error processing row {index}: {str(e)}")
            continue
    
    # Save JSON file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"earthranger_events_{timestamp}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(events, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Successfully exported {len(events)} events")
    print(f"📄 JSON file saved: {output_file}")
    print(f"\n📋 Next steps:")
    print(f"   1. Open EarthRanger web interface")
    print(f"   2. Go to Events > Import")
    print(f"   3. Upload the JSON file: {output_file}")

if __name__ == "__main__":
    main()
