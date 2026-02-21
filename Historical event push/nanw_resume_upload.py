#!/usr/bin/env python3
"""
NANW Resume Upload - Continue from Event 520
============================================

Resumes upload from event 521 onwards to avoid duplicates.

Usage:
    python nanw_resume_upload.py

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

class NANWResumeUploader:
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
        local_time = pd.to_datetime(datetime_str)
        utc_time = local_time - timedelta(hours=2)
        return utc_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception as e:
        print(f"⚠️ Error converting time: {e}")
        return datetime_str

def parse_csv_to_events(df):
    """Parse CSV into NANW monitoring events with nested Herd structure"""
    events = []
    
    print("\n🕐 Converting timestamps from GMT+2 to UTC...")
    df['time_utc'] = df['time'].apply(convert_gmt2_to_utc)
    
    print(f"\n🔄 Grouping {len(df)} individuals into herd events...")
    grouped = df.groupby(['time_utc', 'location.latitude', 'location.longitude'])
    print(f"   Found {len(grouped)} unique herd events")
    
    for (evt_time, lat, lon), group in grouped:
        event = {
            'event_type': 'giraffe_nw_monitoring0',
            'event_category': 'monitoring_nanw',
            'title': 'NANW Giraffe Monitoring',
            'time': evt_time,
            'state': 'new',
            'priority': 200,
            'is_collection': False,
            'event_details': {
                'Herd': []
            }
        }
        
        if pd.notna(lat) and pd.notna(lon) and float(lat) != 0 and float(lon) != 0:
            event['location'] = {
                'latitude': float(lat),
                'longitude': float(lon)
            }
        
        first_row = group.iloc[0]
        
        if pd.notna(first_row.get('event_details.herd_size')):
            event['event_details']['herd_size'] = int(first_row['event_details.herd_size'])
        if pd.notna(first_row.get('event_details.herd_notes')):
            event['event_details']['herd_notes'] = str(first_row['event_details.herd_notes'])
        if pd.notna(first_row.get('event_details.river_system')):
            event['event_details']['river_system'] = str(first_row['event_details.river_system'])
        if pd.notna(first_row.get('event_details.image_prefix')):
            event['event_details']['image_prefix'] = str(first_row['event_details.image_prefix'])
        
        for _, row in group.iterrows():
            individual = {}
            
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
            
            if individual:
                event['event_details']['Herd'].append(individual)
        
        events.append(event)
    
    return events

def main():
    """Main upload function"""
    SKIP_EVENTS = 520  # Already uploaded events
    
    print("🦒 NANW RESUME UPLOAD - Continue from Event 521")
    print("=" * 60)
    print(f"⏭️  Skipping first {SKIP_EVENTS} events (already uploaded)")
    print("=" * 60)
    
    csv_file = "G:\\My Drive\\Data management\\streamlit\\Historical event push\\nanw_events_historical_push_260107.csv"
    
    if not os.path.exists(csv_file):
        print(f"❌ File not found: {csv_file}")
        return
    
    try:
        print(f"\n📖 Loading CSV file...")
        df = pd.read_csv(csv_file)
        print(f"✅ Loaded {len(df)} total rows")
    except Exception as e:
        print(f"❌ Error loading CSV: {str(e)}")
        return
    
    print("\n" + "=" * 60)
    try:
        all_events = parse_csv_to_events(df)
        print(f"\n✅ Parsed {len(all_events)} total herd events")
        
        # Skip already uploaded events
        events_to_upload = all_events[SKIP_EVENTS:]
        print(f"⏭️  Skipping {SKIP_EVENTS} already uploaded events")
        print(f"📤 Remaining events to upload: {len(events_to_upload)}")
        
    except Exception as e:
        print(f"❌ Error parsing data: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    username = input("\n👤 EarthRanger Username: ")
    password = getpass.getpass("🔑 EarthRanger Password: ")
    
    uploader = NANWResumeUploader()
    
    if not uploader.authenticate(username, password):
        return
    
    if not uploader.test_connection():
        print("❌ API connection test failed")
        return
    
    print("✅ API connection test successful!")
    
    print("\n" + "=" * 60)
    print(f"⚠️  READY TO UPLOAD REMAINING {len(events_to_upload)} EVENTS")
    print(f"   (Events {SKIP_EVENTS + 1} to {len(all_events)})")
    print("=" * 60)
    proceed = input(f"\n❓ Proceed with upload? Type 'YES' to continue: ").strip()
    if proceed != 'YES':
        print("❌ Upload cancelled")
        return
    
    print(f"\n🚀 Starting upload from event {SKIP_EVENTS + 1}...")
    print("=" * 60)
    
    successful = 0
    failed = 0
    failed_events = []
    start_time = time.time()
    
    for idx, event in enumerate(events_to_upload, 1):
        actual_event_num = SKIP_EVENTS + idx
        
        try:
            result = uploader.upload_event(event)
            
            if result['success']:
                successful += 1
                
                if successful % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = successful / elapsed
                    remaining_events = len(events_to_upload) - successful
                    remaining_time = remaining_events / rate if rate > 0 else 0
                    total_complete = SKIP_EVENTS + successful
                    print(f"✅ {total_complete}/{len(all_events)} total ({total_complete/len(all_events)*100:.1f}%) - ETA: {remaining_time/60:.1f} min")
            else:
                failed += 1
                failed_events.append({
                    'event_number': actual_event_num,
                    'error': result['error'],
                    'event_time': event.get('time')
                })
                print(f"❌ Event {actual_event_num} failed: {result['error'][:100]}")
                
        except Exception as e:
            failed += 1
            failed_events.append({
                'event_number': actual_event_num,
                'error': str(e),
                'event_time': event.get('time')
            })
            print(f"❌ Event {actual_event_num} error: {str(e)[:100]}")
    
    elapsed_time = time.time() - start_time
    total_successful = SKIP_EVENTS + successful
    
    print("\n" + "=" * 60)
    print(f"📊 UPLOAD COMPLETE!")
    print("=" * 60)
    print(f"✅ Previously uploaded: {SKIP_EVENTS} events")
    print(f"✅ Just uploaded: {successful} events")
    print(f"✅ Total successful: {total_successful} events")
    print(f"❌ Failed this session: {failed} events")
    if successful + failed > 0:
        print(f"📈 Session success rate: {(successful/(successful+failed)*100):.1f}%")
    print(f"⏱️  Session time: {elapsed_time/60:.1f} minutes")
    print(f"⚡ Upload rate: {successful/(elapsed_time/60):.1f} events/minute")
    print("=" * 60)
    
    if failed_events:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        failed_file = f"failed_nanw_resume_{timestamp}.json"
        with open(failed_file, 'w') as f:
            json.dump(failed_events, f, indent=2, default=str)
        print(f"\n💾 Failed events saved to: {failed_file}")
    else:
        print(f"\n🎉 ALL REMAINING EVENTS UPLOADED SUCCESSFULLY!")
    
    print("\n✅ Upload complete. Check the NANW dashboard to verify data.")
    
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
