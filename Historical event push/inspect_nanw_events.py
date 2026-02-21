#!/usr/bin/env python3
"""
NANW Event Structure Inspector
===============================

Pulls actual giraffe_nw_monitoring0 events from EarthRanger to inspect structure.

Usage:
    python inspect_nanw_events.py

Requirements:
    pip install pandas requests ecoscope
"""

import pandas as pd
import json
import getpass
from ecoscope.io.earthranger import EarthRangerIO
from pandas import json_normalize

def main():
    print("🦒 NANW Event Structure Inspector")
    print("=" * 60)
    
    # Get credentials
    username = input("👤 EarthRanger Username: ")
    password = getpass.getpass("🔑 EarthRanger Password: ")
    
    # Connect to EarthRanger
    try:
        print("\n🔐 Connecting to EarthRanger...")
        er = EarthRangerIO(
            server="https://twiga.pamdas.org",
            username=username,
            password=password
        )
        print("✅ Connected successfully!")
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        return
    
    # Pull events
    try:
        print("\n📥 Fetching giraffe_nw_monitoring0 events...")
        event_cat = "monitoring_nanw"
        event_type = "giraffe_nw_monitoring0"
        since = "2024-01-01T00:00:00Z"
        until = "2026-12-31T23:59:59Z"
        
        events = er.get_events(
            event_category=event_cat,
            since=since,
            until=until,
            include_details=True,
            include_notes=False
        )
        
        if events.empty:
            print("⚠️ No events found. Trying alternative event type 'giraffe_nw_monitoring'...")
            event_type = "giraffe_nw_monitoring"
            events = er.get_events(
                event_category=event_cat,
                since=since,
                until=until,
                include_details=True,
                include_notes=False
            )
        
        print(f"✅ Found {len(events)} events")
        
        if events.empty:
            print("❌ No events found for either event type.")
            return
        
        # Convert to dict for inspection
        events_dict = events.to_dict(orient="records")
        
        # Show first event in full detail
        print("\n" + "=" * 60)
        print("📦 FIRST EVENT - FULL STRUCTURE:")
        print("=" * 60)
        print(json.dumps(events_dict[0], indent=2, default=str))
        
        # Show flattened structure
        print("\n" + "=" * 60)
        print("📋 FLATTENED EVENT STRUCTURE (EVENT-LEVEL):")
        print("=" * 60)
        flat = json_normalize(events_dict)
        print("\nAvailable columns:")
        for col in sorted(flat.columns):
            print(f"  - {col}")
        
        # Show sample data for key columns
        print("\n" + "=" * 60)
        print("📊 SAMPLE DATA (First 3 events):")
        print("=" * 60)
        
        # Show important columns
        key_cols = [col for col in flat.columns if 
                   col.startswith('event_details.') or 
                   col in ['id', 'event_type', 'time', 'location.latitude', 'location.longitude']]
        
        if key_cols:
            print(flat[key_cols].head(3).to_string())
        else:
            print(flat.head(3).to_string())
        
        # Explode and flatten Herd structure (like dashboard does)
        print("\n" + "=" * 60)
        print("📋 EXPLODED HERD STRUCTURE (INDIVIDUAL-LEVEL):")
        print("=" * 60)
        
        try:
            # Explode the Herd array
            events_df = pd.DataFrame(events_dict)
            if 'event_details' in events_df.columns:
                # Check if Herd exists
                has_herd = events_df['event_details'].apply(lambda x: isinstance(x, dict) and 'Herd' in x).any()
                
                if has_herd:
                    # Normalize to get event_details columns
                    flat_with_herd = json_normalize(events_dict)
                    
                    # Explode the Herd array
                    exploded = flat_with_herd.explode("event_details.Herd").reset_index(drop=True)
                    
                    # Normalize the individual Herd members
                    if "event_details.Herd" in exploded.columns:
                        herd_df = json_normalize(exploded["event_details.Herd"])
                        
                        # Combine event data with individual herd member data
                        exploded_final = pd.concat([
                            exploded.drop(columns="event_details.Herd"), 
                            herd_df
                        ], axis=1)
                        
                        print(f"\n✅ Successfully exploded Herd structure!")
                        print(f"Total individuals: {len(exploded_final)}")
                        print(f"\nIndividual giraffe columns:")
                        individual_cols = [col for col in exploded_final.columns if col in herd_df.columns]
                        for col in sorted(individual_cols):
                            print(f"  - {col}")
                        
                        print("\n📊 SAMPLE EXPLODED DATA (First 5 individuals):")
                        # Show all columns with individual data
                        display_cols = [col for col in exploded_final.columns if 
                                       col.startswith('giraffe_') or 
                                       col in ['id', 'time', 'location.latitude', 'location.longitude',
                                              'event_details.herd_size', 'event_details.herd_notes',
                                              'event_details.river_system']]
                        
                        if display_cols:
                            print(exploded_final[display_cols].head(5).to_string())
                        else:
                            print(exploded_final.head(5).to_string())
                        
                        # Save exploded CSV
                        csv_exploded = "nanw_events_exploded.csv"
                        exploded_final.to_csv(csv_exploded, index=False)
                        print(f"\n💾 Saved exploded data to: {csv_exploded}")
                    else:
                        print("⚠️ No event_details.Herd column found after initial flatten")
                else:
                    print("⚠️ No Herd field found in event_details")
        except Exception as e:
            print(f"⚠️ Could not explode Herd structure: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Check for Herd structure
        print("\n" + "=" * 60)
        print("🔍 HERD STRUCTURE ANALYSIS:")
        print("=" * 60)
        
        if 'event_details' in events_dict[0]:
            event_details = events_dict[0]['event_details']
            print(f"\nEvent details keys: {list(event_details.keys())}")
            
            if 'Herd' in event_details:
                print(f"\n✅ 'Herd' field found!")
                print(f"Type: {type(event_details['Herd'])}")
                print(f"Length: {len(event_details['Herd']) if isinstance(event_details['Herd'], list) else 'N/A'}")
                
                if isinstance(event_details['Herd'], list) and len(event_details['Herd']) > 0:
                    print(f"\n📋 First Herd member structure:")
                    print(json.dumps(event_details['Herd'][0], indent=2, default=str))
                    
                    print(f"\n📋 Herd member fields:")
                    for key in event_details['Herd'][0].keys():
                        print(f"  - {key}")
            else:
                print("\n⚠️ No 'Herd' field found in event_details")
                print("Available event_details fields:")
                for key, value in event_details.items():
                    print(f"  - {key}: {type(value).__name__}")
        
        # Save full sample to JSON file
        output_file = "nanw_event_sample.json"
        with open(output_file, 'w') as f:
            json.dump(events_dict[:5], f, indent=2, default=str)
        print(f"\n💾 Saved first 5 events to: {output_file}")
        
        # Save flattened CSV
        csv_file = "nanw_events_flattened.csv"
        flat.to_csv(csv_file, index=False)
        print(f"💾 Saved flattened data to: {csv_file}")
        
        print("\n✅ Inspection complete!")
        
    except Exception as e:
        print(f"❌ Error fetching events: {str(e)}")
        import traceback
        traceback.print_exc()
        return

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
