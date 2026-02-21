#!/usr/bin/env python3
"""
NANW Giraffe Monitoring Event Upload Script
============================================

Uploads historical NANW monitoring events to EarthRanger.
Event Category: monitoring_nanw
Event Type: giraffe_nw_monitoring0

This script handles the nested Herd structure required by the NANW dashboard.

Usage:
    python nanw_monitoring_upload.py

Requirements:
    pip install pandas requests

Author: Giraffe Conservation Foundation
Date: January 2026
"""

import pandas as pd
import requests
import json
import sys
import os
from datetime import datetime
import getpass

class NANWMonitoringUploader:
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

def parse_csv_to_events(df):
    """
    Parse CSV into NANW monitoring events with nested Herd structure.
    
    Expected CSV format:
    - One row per individual giraffe
    - Rows with same event_datetime/lat/lon are grouped into one herd event
    - Each row becomes one entry in the Herd array
    """
    events = []
    
    # Group by event_datetime, latitude, longitude (one event per herd sighting)
    grouped = df.groupby(['event_datetime', 'latitude', 'longitude'])
    
    for (evt_time, lat, lon), group in grouped:
        # Create herd-level event
        event = {
            'event_type': 'giraffe_nw_monitoring0',
            'event_category': 'monitoring_nanw',
            'title': 'NANW Giraffe Monitoring',
            'time': str(evt_time),
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
        
        # Extract herd-level details from first row (should be same for all)
        first_row = group.iloc[0]
        
        # Add herd-level details
        herd_details = {
            'image_prefix': first_row.get('details_image_prefix', ''),
            'herd_dire': first_row.get('details_herd_dire', ''),
            'herd_dist': first_row.get('details_herd_dist', ''),
            'herd_size': first_row.get('details_herd_size', len(group)),
            'herd_notes': first_row.get('details_herd_notes', ''),
            'river_system': first_row.get('details_river_system', '')
        }
        
        # Add non-empty herd details to event_details
        for key, value in herd_details.items():
            if pd.notna(value) and value != '':
                # Keep herd_size as integer, others as strings
                if key == 'herd_size':
                    event['event_details'][key] = int(value)
                else:
                    event['event_details'][key] = str(value)
        
        # Process each individual giraffe in the herd
        for _, row in group.iterrows():
            individual = {}
            
            # Map individual giraffe fields
            giraffe_fields = {
                'giraffe_id': 'giraffe_id',
                'giraffe_age': 'giraffe_age',
                'giraffe_sex': 'giraffe_sex',
                'giraffe_gsd': 'giraffe_gsd',
                'giraffe_dire': 'giraffe_dire',
                'giraffe_dist': 'giraffe_dist',
                'giraffe_snar': 'giraffe_snar',
                'giraffe_notes': 'giraffe_notes',
                'giraffe_right': 'giraffe_right',
                'giraffe_left': 'giraffe_left',
                'giraffe_gsd_loc': 'giraffe_gsd_loc',
                'giraffe_gsd_sev': 'giraffe_gsd_sev'
            }
            
            for csv_field, event_field in giraffe_fields.items():
                value = row.get(csv_field, '')
                if pd.notna(value) and value != '':
                    individual[event_field] = str(value)
            
            # Add individual to Herd array
            if individual:  # Only add if there's data
                event['event_details']['Herd'].append(individual)
        
        events.append(event)
    
    return events

def main():
    """Main upload function"""
    print("🦒 NANW Giraffe Monitoring Event Upload Tool")
    print("=" * 60)
    print("Event Category: monitoring_nanw")
    print("Event Type: giraffe_nw_monitoring0")
    print("=" * 60)
    
    # Get CSV file
    csv_file = input("\n📁 Enter path to CSV file: ").strip().strip('"')
    
    if not os.path.exists(csv_file):
        print(f"❌ File not found: {csv_file}")
        return
    
    # Load CSV
    try:
        print(f"📖 Loading CSV file: {csv_file}")
        df = pd.read_csv(csv_file)
        print(f"✅ Loaded {len(df)} rows")
        print(f"\n📋 Columns found: {', '.join(df.columns)}")
    except Exception as e:
        print(f"❌ Error loading CSV: {str(e)}")
        return
    
    # Validate required columns
    required_cols = ['event_datetime', 'latitude', 'longitude']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"❌ Missing required columns: {', '.join(missing_cols)}")
        return
    
    # Show preview
    print("\n📋 DATA PREVIEW:")
    print(df.head(3))
    
    # Parse into events
    print("\n🔄 Parsing CSV into NANW monitoring events...")
    try:
        events = parse_csv_to_events(df)
        print(f"✅ Parsed {len(events)} herd events from {len(df)} individual records")
        
        # Show sample event structure
        if events:
            print(f"\n📦 Sample event structure:")
            sample = events[0].copy()
            # Truncate Herd array for display
            if 'Herd' in sample.get('event_details', {}):
                herd_count = len(sample['event_details']['Herd'])
                sample['event_details']['Herd'] = f"[{herd_count} individuals]"
            print(json.dumps(sample, indent=2, default=str))
    except Exception as e:
        print(f"❌ Error parsing CSV: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    # Get credentials
    username = input("\n👤 EarthRanger Username: ")
    password = getpass.getpass("🔑 EarthRanger Password: ")
    
    # Initialize uploader
    uploader = NANWMonitoringUploader()
    
    if not uploader.authenticate(username, password):
        return
    
    if not uploader.test_connection():
        print("❌ API connection test failed")
        return
    
    print("✅ API connection test successful!")
    
    # Confirm upload
    proceed = input(f"\n❓ Proceed with uploading {len(events)} herd events? (y/N): ").lower().strip()
    if proceed != 'y':
        print("❌ Upload cancelled")
        return
    
    # Upload events
    print(f"\n🚀 Starting upload of {len(events)} herd events...")
    print("=" * 60)
    
    successful = 0
    failed = 0
    failed_events = []
    
    for index, event in enumerate(events, 1):
        try:
            result = uploader.upload_event(event)
            
            if result['success']:
                successful += 1
                herd_size = len(event['event_details'].get('Herd', []))
                print(f"✅ {index}/{len(events)}: Uploaded herd event ({herd_size} individuals)")
            else:
                failed += 1
                failed_events.append({
                    'index': index,
                    'error': result['error'],
                    'event': event
                })
                print(f"❌ {index}/{len(events)}: Failed - {result['error']}")
                
        except Exception as e:
            failed += 1
            failed_events.append({
                'index': index,
                'error': str(e),
                'event': event
            })
            print(f"❌ {index}/{len(events)}: Error - {str(e)}")
    
    # Final report
    print("\n" + "=" * 60)
    print(f"📊 UPLOAD COMPLETE!")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    if successful + failed > 0:
        print(f"📈 Success rate: {(successful/(successful+failed)*100):.1f}%")
    print("=" * 60)
    
    # Save failed events for review
    if failed_events:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        failed_file = f"failed_nanw_upload_{timestamp}.json"
        with open(failed_file, 'w') as f:
            json.dump(failed_events, f, indent=2, default=str)
        print(f"\n💾 Failed events saved to: {failed_file}")
        
        # Show error summary
        error_counts = {}
        for event in failed_events:
            error_msg = str(event.get('error', 'Unknown'))[:100]
            error_counts[error_msg] = error_counts.get(error_msg, 0) + 1
        
        print(f"\n🔍 ERROR ANALYSIS:")
        for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {error}: {count} occurrences")
    
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
