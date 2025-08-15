#!/usr/bin/env python3
"""
Update Event Coordinates Script
==============================

Updates existing EarthRanger events with correct coordinates from CSV

Usage:
    python update_coordinates.py

Requirements:
    pip install pandas requests

Author: Giraffe Conservation Foundation
Date: August 2025
"""

import pandas as pd
import requests
import json
import getpass
from datetime import datetime

class EarthRangerCoordinateUpdater:
    """Update coordinates for existing EarthRanger events"""
    
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
                print(f"❌ Authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Authentication error: {str(e)}")
            return False
    
    def get_biological_sample_events(self):
        """Get existing biological sample events"""
        try:
            url = f"{self.api_base}/activity/events"
            params = {
                'event_type': 'biological_sample',
                'include_details': 'true',
                'limit': 200
            }
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('results', [])
            else:
                print(f"❌ Failed to get events: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error getting events: {str(e)}")
            return []
    
    def update_event(self, event_id, updated_data):
        """Update an event with new data"""
        try:
            url = f"{self.api_base}/activity/events/{event_id}"
            response = requests.patch(url, headers=self.headers, data=json.dumps(updated_data))
            
            if response.status_code in [200, 204]:
                return {'success': True}
            else:
                return {'success': False, 'error': f"{response.status_code}: {response.text}"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

def main():
    """Main coordinate update function"""
    print("🦒 EarthRanger Coordinate Update Tool")
    print("=" * 50)
    
    # Load CSV with correct coordinates
    csv_file = "comprehensive_biological_sample_250813.csv"
    
    try:
        print(f"📖 Loading CSV file: {csv_file}")
        df_csv = pd.read_csv(csv_file)
        print(f"✅ Loaded {len(df_csv)} rows from CSV")
    except Exception as e:
        print(f"❌ Error loading CSV: {str(e)}")
        return
    
    # Create coordinate lookup by sample ID
    coord_lookup = {}
    for _, row in df_csv.iterrows():
        sample_id = row.get('details_girsam_smpid')
        if pd.notna(sample_id) and pd.notna(row.get('latitude')) and pd.notna(row.get('longitude')):
            coord_lookup[str(sample_id)] = {
                'latitude': float(row['latitude']),
                'longitude': float(row['longitude']),
                'site': row.get('details_girsam_site', 'Unknown')
            }
    
    print(f"📍 Created coordinate lookup for {len(coord_lookup)} samples")
    
    # Get credentials
    username = input("\nEarthRanger Username: ")
    password = getpass.getpass("EarthRanger Password: ")
    
    # Initialize updater
    updater = EarthRangerCoordinateUpdater()
    
    if not updater.authenticate(username, password):
        return
    
    # Get existing events
    print("📥 Fetching existing biological sample events...")
    events = updater.get_biological_sample_events()
    print(f"✅ Found {len(events)} existing events")
    
    # Find events that need coordinate updates
    updates_needed = []
    
    for event in events:
        event_details = event.get('event_details', {})
        sample_id = event_details.get('girsam_smpid')
        
        if sample_id and str(sample_id) in coord_lookup:
            csv_coords = coord_lookup[str(sample_id)]
            current_location = event.get('location')
            
            # Check if coordinates need updating
            needs_update = False
            current_lat = current_location.get('latitude') if current_location else None
            current_lng = current_location.get('longitude') if current_location else None
            
            if (abs(current_lat - csv_coords['latitude']) > 0.0001 or 
                abs(current_lng - csv_coords['longitude']) > 0.0001):
                
                updates_needed.append({
                    'event_id': event['id'],
                    'sample_id': sample_id,
                    'site': csv_coords['site'],
                    'current_coords': (current_lat, current_lng),
                    'correct_coords': (csv_coords['latitude'], csv_coords['longitude'])
                })
                needs_update = True
    
    print(f"\n📊 Found {len(updates_needed)} events that need coordinate updates")
    
    if updates_needed:
        print("\n🔍 Events needing updates:")
        for update in updates_needed[:10]:  # Show first 10
            print(f"  {update['site']} ({update['sample_id']}): "
                  f"{update['current_coords']} → {update['correct_coords']}")
        
        if len(updates_needed) > 10:
            print(f"  ... and {len(updates_needed) - 10} more")
        
        proceed = input(f"\n❓ Proceed with updating {len(updates_needed)} events? (y/N): ").lower().strip()
        if proceed != 'y':
            print("❌ Update cancelled")
            return
        
        # Perform updates
        print(f"\n🚀 Starting coordinate updates...")
        successful = 0
        failed = 0
        
        for update in updates_needed:
            try:
                # Prepare update data
                update_data = {
                    'location': {
                        'latitude': update['correct_coords'][0],
                        'longitude': update['correct_coords'][1]
                    },
                    'event_details': {
                        **event.get('event_details', {}),
                        'latitude': str(update['correct_coords'][0]),
                        'longitude': str(update['correct_coords'][1])
                    }
                }
                
                result = updater.update_event(update['event_id'], update_data)
                
                if result['success']:
                    successful += 1
                    if successful % 10 == 0:
                        print(f"✅ Progress: {successful} successful updates")
                else:
                    failed += 1
                    print(f"❌ Failed to update {update['sample_id']}: {result['error']}")
                    
            except Exception as e:
                failed += 1
                print(f"❌ Error updating {update['sample_id']}: {str(e)}")
        
        # Final report
        print(f"\n📊 UPDATE COMPLETE!")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"📈 Success rate: {(successful/(successful+failed)*100):.1f}%")
    
    else:
        print("✅ All events already have correct coordinates!")

if __name__ == "__main__":
    main()
