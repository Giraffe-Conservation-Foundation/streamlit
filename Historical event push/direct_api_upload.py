#!/usr/bin/env python3
"""
Direct EarthRanger API Upload Script
===================================

Bypasses ecoscope and calls EarthRanger API directly for better control.

Usage:
    python direct_api_upload.py

Requirements:
    pip install pandas requests

Author: Giraffe Conservation Foundation
Date: August 2025
"""

import pandas as pd
import requests
import json
import sys
import os
from datetime import datetime
import getpass

class DirectEarthRangerUploader:
    """Direct API uploader for EarthRanger"""
    
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
            
            # Get OAuth token
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

def main():
    """Main upload function"""
    print("🦒 Direct EarthRanger API Upload Tool")
    print("=" * 50)
    
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
    
    # Get credentials
    username = input("\nEarthRanger Username: ")
    password = getpass.getpass("EarthRanger Password: ")
    
    # Initialize uploader
    uploader = DirectEarthRangerUploader()
    
    if not uploader.authenticate(username, password):
        return
    
    if not uploader.test_connection():
        print("❌ API connection test failed")
        return
    
    print("✅ API connection test successful!")
    
    # Confirm upload
    proceed = input(f"\n❓ Proceed with uploading {len(df)} events? (y/N): ").lower().strip()
    if proceed != 'y':
        print("❌ Upload cancelled")
        return
    
    # Upload events
    print(f"\n🚀 Starting upload of {len(df)} events...")
    
    successful = 0
    failed = 0
    failed_events = []
    
    for index, row in df.iterrows():
        try:
            # Create event structure
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
                # Also store coordinates in event_details for reliable retrieval
                event['event_details']['latitude'] = str(float(row['latitude']))
                event['event_details']['longitude'] = str(float(row['longitude']))
            
            # Add details
            for col in df.columns:
                if col.startswith('details_') and pd.notna(row[col]):
                    key = col.replace('details_', '')
                    event['event_details'][key] = str(row[col])
            
            # Upload event
            result = uploader.upload_event(event)
            
            if result['success']:
                successful += 1
                if successful % 10 == 0:
                    print(f"✅ Progress: {successful} successful uploads")
            else:
                failed += 1
                failed_events.append({
                    'row': index,
                    'error': result['error'],
                    'event': event
                })
                print(f"❌ Row {index} failed: {result['error']}")
                
        except Exception as e:
            failed += 1
            print(f"❌ Row {index} error: {str(e)}")
    
    # Final report
    print(f"\n📊 UPLOAD COMPLETE!")
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success rate: {(successful/(successful+failed)*100):.1f}%")
    
    # Save failed events for review
    if failed_events:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        failed_file = f"failed_direct_upload_{timestamp}.json"
        with open(failed_file, 'w') as f:
            json.dump(failed_events, f, indent=2, default=str)
        print(f"💾 Failed events saved to: {failed_file}")
        
        # Show common error patterns
        error_counts = {}
        for event in failed_events:
            error_msg = str(event.get('error', 'Unknown'))[:100]  # Truncate long errors
            error_counts[error_msg] = error_counts.get(error_msg, 0) + 1
        
        print(f"\n🔍 ERROR ANALYSIS:")
        for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {error}: {count} occurrences")
    
    return successful, failed, failed_events

if __name__ == "__main__":
    main()
