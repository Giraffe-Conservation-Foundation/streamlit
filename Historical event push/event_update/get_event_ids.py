#!/usr/bin/env python3
"""
Helper Script: Get Event IDs from EarthRanger
==============================================

Retrieve event IDs for events you want to update.
Useful for finding UUIDs of previously uploaded events.

Usage:
    python get_event_ids.py

Requirements:
    pip install ecoscope-release pandas

Author: Giraffe Conservation Foundation
Date: February 2026
"""

import pandas as pd
import getpass
from datetime import datetime
from ecoscope.io import EarthRangerIO

def main():
    """Get event IDs from EarthRanger"""
    print("🦒 EarthRanger Event ID Retrieval Tool")
    print("=" * 50)
    
    # Get credentials
    print("\n🔐 EarthRanger Credentials")
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")
    
    # Connect
    print("\n🔐 Connecting to EarthRanger...")
    try:
        er_io = EarthRangerIO(
            server="https://twiga.pamdas.org",
            username=username,
            password=password
        )
        print("✅ Connected successfully!")
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        return
    
    # Get event types first
    print("\n📋 Fetching event types...")
    event_types = er_io.get_event_types()
    
    print("\nAvailable event types (first 20):")
    print(event_types[['id', 'value', 'display']].head(20).to_string(index=False))
    
    # Ask for event type
    print("\n" + "=" * 50)
    event_type_input = input("Enter event type UUID (or press Enter to get all events): ").strip()
    
    event_type_list = [event_type_input] if event_type_input else None
    
    # Date range
    since_str = input("Start date (YYYY-MM-DD) [default: 2024-01-01]: ").strip()
    since = since_str if since_str else "2024-01-01"
    
    until_str = input("End date (YYYY-MM-DD) [default: today]: ").strip()
    until = until_str if until_str else datetime.now().strftime("%Y-%m-%d")
    
    # Get events
    print(f"\n🔍 Fetching events from {since} to {until}...")
    try:
        events = er_io.get_events(
            event_type=event_type_list,
            since=since,
            until=until,
            include_details=True
        )
        
        if events.empty:
            print("❌ No events found matching criteria")
            return
        
        print(f"✅ Found {len(events)} event(s)!")
        
        # Show preview
        print("\n📊 Preview of events:")
        preview_cols = []
        if 'title' in events.columns:
            preview_cols.append('title')
        if 'time' in events.columns:
            preview_cols.append('time')
        if 'event_type' in events.columns:
            preview_cols.append('event_type')
        
        if preview_cols:
            print(events[preview_cols].head(10).to_string())
        
        # Extract event details if present
        if 'event_details' in events.columns:
            # Try to expand event_details
            try:
                details_df = pd.json_normalize(events['event_details'])
                for col in details_df.columns:
                    events[f'detail_{col}'] = details_df[col]
            except:
                pass
        
        # Save to CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"event_ids_export_{timestamp}.csv"
        
        # Select useful columns for export
        export_cols = [events.index.name] if events.index.name else []
        export_cols.extend([col for col in ['title', 'time', 'event_type', 'state', 'priority'] if col in events.columns])
        export_cols.extend([col for col in events.columns if col.startswith('detail_')])
        
        # Reset index to get event_id as column
        events_export = events.reset_index()
        if 'id' in events_export.columns:
            events_export.rename(columns={'id': 'event_id'}, inplace=True)
        
        # Save
        export_cols_available = [col for col in export_cols if col in events_export.columns]
        if not export_cols_available:
            events_export.to_csv(output_file, index=False)
        else:
            events_export[export_cols_available].to_csv(output_file, index=False)
        
        print(f"\n💾 Event IDs saved to: {output_file}")
        print(f"📊 Total events: {len(events)}")
        
        print("\n📝 Next Steps:")
        print("1. Open the CSV file")
        print("2. Copy the event_id(s) you want to update")
        print("3. Create your update CSV with event_id and fields to update")
        print("4. Run update_events.py")
        
    except Exception as e:
        print(f"❌ Error fetching events: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
