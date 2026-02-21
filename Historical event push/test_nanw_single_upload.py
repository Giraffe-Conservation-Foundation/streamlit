#!/usr/bin/env python3
"""
NANW Test Upload - Single Row
===============================

Test upload script for NANW monitoring events.
Converts GMT+2 timestamps to UTC and uploads one event for testing.

Usage:
    python test_nanw_single_upload.py

Requirements:
    pip install pandas requests
"""

import pandas as pd
import requests
import json
import sys
import os
from datetime import datetime, timedelta
import getpass

class NANWTestUploader:
    """Direct API uploader for NANW monitoring events"""
    
    def __init__(self, server_url="https://twiga.pamdas.org"):
        self.server_url = server_url
        self.api_base = f"{server_url}/api/v1.0"
        self.token_url = f"{server_url}/oauth2/token"
        self.access_token = None
        self.headers = {'Content-Type': 'application/json'}
    
    def authenticate(self, username, password):
        """Authenticate and get access token"""
        try:
            print("🔐 Authenticating with EarthRanger...")
            
            token_data = {
                'grant_type': 'password',
                'username': username,
                'password': password,
                'client_id': 'das_web_client'
            }
            
            response = requests.post(self.token_url, data=token_data)
            
            if response.status_code == 200:
                token_info = response.json()
                self.access_token = token_info['access_token']
                self.headers['Authorization'] = f'Bearer {self.access_token}'
                print("✅ Authentication successful!")
                return True
            else:
                print(f"❌ Authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Authentication error: {str(e)}")
            return False
    
    def test_connection(self):
        """Test the API connection"""
        try:
            url = f"{self.api_base}/activity/events"
            params = {'limit': 1}
            response = requests.get(url, headers=self.headers, params=params)
            return response.status_code == 200
        except:
            return False
    
    def upload_event(self, event_data):
        """Upload a single event"""
        try:
            url = f"{self.api_base}/activity/events"
            response = requests.post(url, headers=self.headers, data=json.dumps(event_data))
            
            if response.status_code in [200, 201]:
                return {'success': True, 'data': response.json()}
            else:
                return {'success': False, 'error': f"{response.status_code}: {response.text}"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

def convert_gmt2_to_utc(datetime_str):
    """Convert GMT+2 datetime string to UTC ISO format"""
    try:
        # Parse the datetime string (assuming format: YYYY-MM-DD HH:MM:SS)
        local_time = pd.to_datetime(datetime_str)
        
        # Subtract 2 hours to convert GMT+2 to UTC
        utc_time = local_time - timedelta(hours=2)
        
        # Format as ISO string with Z suffix
        return utc_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception as e:
        print(f"⚠️ Error converting time: {e}")
        return datetime_str

def parse_csv_to_events(df):
    """
    Parse CSV into NANW monitoring events with nested Herd structure.
    Groups rows by time/location into herd events.
    """
    events = []
    
    # Convert times from GMT+2 to UTC
    print("\n🕐 Converting timestamps from GMT+2 to UTC...")
    df['time_utc'] = df['time'].apply(convert_gmt2_to_utc)
    
    # Show conversion examples
    print(f"   Original (GMT+2): {df['time'].iloc[0]}")
    print(f"   Converted (UTC):  {df['time_utc'].iloc[0]}")
    
    # Group by time, latitude, longitude (one event per herd sighting)
    grouped = df.groupby(['time_utc', 'location.latitude', 'location.longitude'])
    
    for (evt_time, lat, lon), group in grouped:
        # Create herd-level event
        event = {
            'event_type': 'giraffe_nw_monitoring0',
            'event_category': 'monitoring_nanw',
            'title': 'NANW Giraffe Monitoring',
            'time': evt_time,
            'state': 'new',
            'priority': 200,
            'is_collection': False,
            'event_details': {
                'Herd': []  # Array of individual giraffe records
            }
        }
        
        # Add location if valid
        if pd.notna(lat) and pd.notna(lon) and float(lat) != 0 and float(lon) != 0:
            event['location'] = {
                'latitude': float(lat),
                'longitude': float(lon)
            }
        
        # Extract herd-level details from first row
        first_row = group.iloc[0]
        
        # Add herd-level details
        if pd.notna(first_row.get('event_details.herd_size')):
            event['event_details']['herd_size'] = int(first_row['event_details.herd_size'])
        if pd.notna(first_row.get('event_details.herd_notes')):
            event['event_details']['herd_notes'] = str(first_row['event_details.herd_notes'])
        if pd.notna(first_row.get('event_details.river_system')):
            event['event_details']['river_system'] = str(first_row['event_details.river_system'])
        if pd.notna(first_row.get('event_details.image_prefix')):
            event['event_details']['image_prefix'] = str(first_row['event_details.image_prefix'])
        
        # Process each individual giraffe in the herd
        for _, row in group.iterrows():
            individual = {}
            
            # Map individual giraffe fields
            if pd.notna(row.get('giraffe_id')):
                individual['giraffe_id'] = str(row['giraffe_id'])
            if pd.notna(row.get('giraffe_age')):
                individual['giraffe_age'] = str(row['giraffe_age'])
            if pd.notna(row.get('giraffe_sex')):
                individual['giraffe_sex'] = str(row['giraffe_sex'])
            if pd.notna(row.get('giraffe_left')):
                individual['giraffe_left'] = str(row['giraffe_left'])
            if pd.notna(row.get('giraffe_right')):
                individual['giraffe_right'] = str(row['giraffe_right'])
            if pd.notna(row.get('giraffe_notes')):
                individual['giraffe_notes'] = str(row['giraffe_notes'])
            
            # Add individual to Herd array
            if individual:  # Only add if there's data
                event['event_details']['Herd'].append(individual)
        
        events.append(event)
    
    return events

def main():
    """Main upload function"""
    print("🦒 NANW Test Upload - Single Event")
    print("=" * 60)
    print("Event Category: monitoring_nanw")
    print("Event Type: giraffe_nw_monitoring0")
    print("Timezone: Converting GMT+2 to UTC")
    print("=" * 60)
    
    # CSV file path
    csv_file = "G:\\My Drive\\Data management\\streamlit\\Historical event push\\nanw_events_historical_push_260107.csv"
    
    if not os.path.exists(csv_file):
        print(f"❌ File not found: {csv_file}")
        return
    
    # Load CSV
    try:
        print(f"\n📖 Loading CSV file...")
        df = pd.read_csv(csv_file)
        print(f"✅ Loaded {len(df)} total rows")
        print(f"📋 Columns: {', '.join(df.columns)}")
    except Exception as e:
        print(f"❌ Error loading CSV: {str(e)}")
        return
    
    # Show preview of first few rows
    print("\n📋 FIRST 3 ROWS PREVIEW:")
    print(df.head(3).to_string())
    
    # Ask which row to test
    print(f"\n" + "=" * 60)
    row_choice = input(f"Which row would you like to test? (1-{len(df)}, or press Enter for row 1): ").strip()
    
    if row_choice == "":
        row_num = 1
    else:
        try:
            row_num = int(row_choice)
            if row_num < 1 or row_num > len(df):
                print(f"❌ Invalid row number. Must be between 1 and {len(df)}")
                return
        except ValueError:
            print("❌ Invalid input. Using row 1.")
            row_num = 1
    
    # Get the test data - include all rows with same time/location as selected row
    test_row = df.iloc[row_num - 1]
    test_time = test_row['time']
    test_lat = test_row['location.latitude']
    test_lon = test_row['location.longitude']
    
    # Filter for all individuals in this herd (same time/location)
    test_df = df[(df['time'] == test_time) & 
                 (df['location.latitude'] == test_lat) & 
                 (df['location.longitude'] == test_lon)].copy()
    
    print(f"\n✅ Selected herd from row {row_num}")
    print(f"   Time: {test_time} (GMT+2)")
    print(f"   Location: {test_lat}, {test_lon}")
    print(f"   Herd size: {len(test_df)} individuals")
    
    # Parse into event
    print("\n🔄 Parsing test data into event structure...")
    try:
        events = parse_csv_to_events(test_df)
        
        if not events:
            print("❌ No events generated")
            return
        
        test_event = events[0]
        
        print(f"\n📦 TEST EVENT STRUCTURE:")
        print("=" * 60)
        print(json.dumps(test_event, indent=2, default=str))
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error parsing data: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    # Get credentials
    username = input("\n👤 EarthRanger Username: ")
    password = getpass.getpass("🔑 EarthRanger Password: ")
    
    # Initialize uploader
    uploader = NANWTestUploader()
    
    if not uploader.authenticate(username, password):
        return
    
    if not uploader.test_connection():
        print("❌ API connection test failed")
        return
    
    print("✅ API connection test successful!")
    
    # Confirm upload
    proceed = input(f"\n❓ Proceed with uploading this TEST event? (y/N): ").lower().strip()
    if proceed != 'y':
        print("❌ Upload cancelled")
        return
    
    # Upload event
    print(f"\n🚀 Uploading test event...")
    
    try:
        result = uploader.upload_event(test_event)
        
        if result['success']:
            print(f"\n✅ SUCCESS! Event uploaded successfully!")
            print(f"\n📦 Response from EarthRanger:")
            print(json.dumps(result['data'], indent=2, default=str))
        else:
            print(f"\n❌ FAILED: {result['error']}")
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
