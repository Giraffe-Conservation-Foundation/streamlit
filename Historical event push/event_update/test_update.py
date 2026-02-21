#!/usr/bin/env python3
"""
Quick test script - non-interactive version
Update events from single_event_test.csv
"""

import pandas as pd
import sys
import os
from datetime import datetime
import getpass
import requests
from ecoscope.io import EarthRangerIO

# Configuration
CSV_FILE = "single_event_test.csv"
SERVER_URL = "https://twiga.pamdas.org"

def main():
    print("🦒 Quick Event Update Test")
    print("=" * 50)
    print(f"📂 Using CSV file: {CSV_FILE}\n")
    
    # Check if file exists
    if not os.path.exists(CSV_FILE):
        print(f"❌ File not found: {CSV_FILE}")
        return
    
    # Load and preview CSV
    df = pd.read_csv(CSV_FILE)
    print("📋 CSV Contents:")
    print(df)
    print()
    
    # Get credentials
    print("🔐 EarthRanger Credentials")
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")
    
    # Connect
    print("\n🔐 Connecting to EarthRanger...")
    try:
        er_io = EarthRangerIO(
            server=SERVER_URL,
            username=username,
            password=password
        )
        
        # Try to get authenticated session from ecoscope
        session = None
        if hasattr(er_io, 'erclient') and hasattr(er_io.erclient, 'session'):
            session = er_io.erclient.session
            print("✅ Using ecoscope's erclient.session")
        elif hasattr(er_io, 'client') and hasattr(er_io.client, 'session'):
            session = er_io.client.session
            print("✅ Using ecoscope's client.session")
        else:
            # Fallback: create our own authenticated session
            print("⚠️ Using fallback authentication")
            import requests
            session = requests.Session()
            # Get token
            auth_url = f"{SERVER_URL}/oauth2/token"
            auth_response = session.post(auth_url, data={
                'username': username,
                'password': password,
                'grant_type': 'password',
                'client_id': 'das_web_client'
            })
            if auth_response.status_code == 200:
                token = auth_response.json().get('access_token')
                session.headers.update({
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                })
            else:
                print(f"❌ Fallback auth failed: {auth_response.status_code}")
                return
            
        api_base = f"{SERVER_URL}/api/v1.0"
        print("✅ Connected successfully!\n")
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    # Process each event
    for idx, row in df.iterrows():
        event_id = row['event_id']
        print(f"📝 Processing event {event_id}...")
        
        # Build update data
        update_data = {}
        event_details = {}
        
        # Check all columns for updates
        for col in df.columns:
            if col == 'event_id':
                continue
            
            if pd.notna(row[col]):
                # Handle detail_ prefix
                if col.startswith('detail_'):
                    field_name = col.replace('detail_', '')
                    event_details[field_name] = row[col]
                    print(f"  - Will update event_details.{field_name} = {row[col]}")
                # Handle known prefixes (girsam_, unit_, etc.)
                elif any(col.startswith(p) for p in ['girsam_', 'unit_', 'deployment_', 'sample_']):
                    event_details[col] = row[col]
                    print(f"  - Will update event_details.{col} = {row[col]}")
                # Handle direct fields
                elif col in ['priority', 'state', 'title']:
                    update_data[col] = row[col]
                    print(f"  - Will update {col} = {row[col]}")
        
        if event_details:
            # Fetch current event to merge event_details
            print(f"  🔍 Fetching current event to merge event_details...")
            try:
                current_events = er_io.get_events(event_ids=[event_id])
                if not current_events.empty:
                    current_event = current_events.iloc[0]
                    existing_details = {}
                    if 'event_details' in current_event and current_event['event_details']:
                        existing_details = current_event['event_details']
                        print(f"  📋 Current event_details: {existing_details}")
                    
                    # Merge
                    merged_details = {**existing_details, **event_details}
                    update_data['event_details'] = merged_details
                    print(f"  ✨ Merged event_details: {merged_details}")
                else:
                    print(f"  ⚠️ Could not fetch current event")
                    update_data['event_details'] = event_details
            except Exception as e:
                print(f"  ⚠️ Error fetching event: {e}")
                update_data['event_details'] = event_details
        
        # Perform update
        try:
            print(f"  📤 Sending update...")
            url = f"{api_base}/activity/events/{event_id}"
            response = session.patch(url, json=update_data)
            
            if response.status_code not in [200, 204]:
                print(f"  ❌ API returned {response.status_code}: {response.text}")
                continue
            
            # Verify
            print(f"  🔍 Verifying update...")
            updated_events = er_io.get_events(event_ids=[event_id])
            if not updated_events.empty:
                updated_event = updated_events.iloc[0]
                if 'event_details' in updated_event:
                    print(f"  ✅ Current event_details after update:")
                    print(f"     {updated_event['event_details']}")
            
            print(f"✅ Successfully updated event {event_id}\n")
            
        except Exception as e:
            print(f"❌ Failed to update event {event_id}: {str(e)}\n")
            import traceback
            traceback.print_exc()
    
    print("=" * 50)
    print("✅ Test complete!")

if __name__ == "__main__":
    main()
