#!/usr/bin/env python3
"""
NANW Full Historical Data Upload
=================================

Uploads ALL historical NANW monitoring events to EarthRanger.
Event Category: monitoring_nanw
Event Type: giraffe_nw_monitoring0

Converts GMT+2 timestamps to UTC and processes all rows.

Usage:
    python nanw_full_upload.py

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
import time

class NANWFullUploader:
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
    print(f"   Sample: {df['time'].iloc[0]} (GMT+2) → {df['time_utc'].iloc[0]} (UTC)")
    
    # Group by time, latitude, longitude (one event per herd sighting)
    print(f"\n🔄 Grouping {len(df)} individuals into herd events...")
    grouped = df.groupby(['time_utc', 'location.latitude', 'location.longitude'])
    print(f"   Found {len(grouped)} unique herd events")
    
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
    print("🦒 NANW FULL HISTORICAL DATA UPLOAD")
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
    
    # Parse into events
    print("\n" + "=" * 60)
    try:
        events = parse_csv_to_events(df)
        print(f"\n✅ Parsed {len(events)} herd events from {len(df)} individual records")
    except Exception as e:
        print(f"❌ Error parsing data: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    # Show summary
    print("\n📊 UPLOAD SUMMARY:")
    print(f"   Total herd events to upload: {len(events)}")
    print(f"   Total individual giraffes: {len(df)}")
    print(f"   Average herd size: {len(df)/len(events):.1f}")
    
    # Get credentials
    print("\n" + "=" * 60)
    username = input("👤 EarthRanger Username: ")
    password = getpass.getpass("🔑 EarthRanger Password: ")
    
    # Initialize uploader
    uploader = NANWFullUploader()
    
    if not uploader.authenticate(username, password):
        return
    
    if not uploader.test_connection():
        print("❌ API connection test failed")
        return
    
    print("✅ API connection test successful!")
    
    # Final confirmation
    print("\n" + "=" * 60)
    print(f"⚠️  READY TO UPLOAD {len(events)} EVENTS")
    print("=" * 60)
    proceed = input(f"\n❓ Proceed with full upload? Type 'YES' to continue: ").strip()
    if proceed != 'YES':
        print("❌ Upload cancelled")
        return
    
    # Upload events
    print(f"\n🚀 Starting upload of {len(events)} herd events...")
    print("=" * 60)
    
    successful = 0
    failed = 0
    failed_events = []
    start_time = time.time()
    
    for index, event in enumerate(events, 1):
        try:
            result = uploader.upload_event(event)
            
            if result['success']:
                successful += 1
                herd_size = len(event['event_details'].get('Herd', []))
                
                # Progress update every 10 events
                if successful % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = successful / elapsed
                    remaining = (len(events) - successful) / rate if rate > 0 else 0
                    print(f"✅ {successful}/{len(events)} events uploaded ({successful/len(events)*100:.1f}%) - ETA: {remaining/60:.1f} min")
            else:
                failed += 1
                failed_events.append({
                    'index': index,
                    'error': result['error'],
                    'event_time': event.get('time'),
                    'herd_size': len(event['event_details'].get('Herd', []))
                })
                print(f"❌ Event {index} failed: {result['error'][:100]}")
                
        except Exception as e:
            failed += 1
            failed_events.append({
                'index': index,
                'error': str(e),
                'event_time': event.get('time'),
                'herd_size': len(event['event_details'].get('Herd', []))
            })
            print(f"❌ Event {index} error: {str(e)[:100]}")
    
    # Final report
    elapsed_time = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"📊 UPLOAD COMPLETE!")
    print("=" * 60)
    print(f"✅ Successful: {successful} events")
    print(f"❌ Failed: {failed} events")
    if successful + failed > 0:
        print(f"📈 Success rate: {(successful/(successful+failed)*100):.1f}%")
    print(f"⏱️  Total time: {elapsed_time/60:.1f} minutes")
    print(f"⚡ Upload rate: {successful/(elapsed_time/60):.1f} events/minute")
    print("=" * 60)
    
    # Save failed events for review
    if failed_events:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        failed_file = f"failed_nanw_full_upload_{timestamp}.json"
        with open(failed_file, 'w') as f:
            json.dump(failed_events, f, indent=2, default=str)
        print(f"\n💾 Failed events saved to: {failed_file}")
        
        # Show error summary
        error_counts = {}
        for event in failed_events:
            error_msg = str(event.get('error', 'Unknown'))[:100]
            error_counts[error_msg] = error_counts.get(error_msg, 0) + 1
        
        print(f"\n🔍 ERROR ANALYSIS:")
        for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  • {error}: {count} occurrences")
    else:
        print(f"\n🎉 ALL EVENTS UPLOADED SUCCESSFULLY!")
    
    print("\n✅ Upload process complete. Check the NANW dashboard to verify data.")
    
    return successful, failed

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Upload interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
