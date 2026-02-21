#!/usr/bin/env python3
"""
Mortality Event Historical Upload Script
========================================

Upload historical mortality events to EarthRanger for the Mortality Dashboard.
This script uploads events with event_type='mortality' to be displayed in the mortality dashboard.

Usage:
    python mortality_upload.py

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

class MortalityEventUploader:
    """Direct API uploader for EarthRanger mortality events"""
    
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

def validate_mortality_cause(cause):
    """Validate mortality cause format"""
    valid_causes = [
        'natural_predation', 'natural_disease', 'natural_starvation', 
        'natural_old_age', 'natural_drought', 'natural_unknown',
        'unnatural_vehicle_collision', 'unnatural_poaching', 'unnatural_immobilisation',
        'unnatural_wire_snare', 'unnatural_human_conflict', 'unnatural_unknown',
        'Unknown'
    ]
    
    if not cause or cause == 'Unknown':
        return True
    
    if cause in valid_causes:
        return True
    
    # Check if it follows the pattern (natural|unnatural)_*
    if cause.startswith('natural_') or cause.startswith('unnatural_'):
        return True
    
    return False

def main():
    """Main upload function"""
    print("☠️  Mortality Event Historical Upload Tool")
    print("=" * 60)
    print("This tool uploads historical mortality events to EarthRanger")
    print("=" * 60)
    
    # Get CSV file
    csv_file = input("\n📁 Enter path to CSV file (or press Enter for template): ").strip().strip('"')
    
    if not csv_file:
        csv_file = "mortality_events_template.csv"
    
    if not os.path.exists(csv_file):
        print(f"❌ File not found: {csv_file}")
        print("\n💡 TIP: Use 'mortality_events_template.csv' as a starting point")
        return
    
    # Load CSV with encoding handling
    try:
        print(f"📖 Loading CSV file: {csv_file}")
        # Try different encodings
        try:
            df = pd.read_csv(csv_file, encoding='utf-8')
        except UnicodeDecodeError:
            print("⚠️  UTF-8 encoding failed, trying latin-1...")
            try:
                df = pd.read_csv(csv_file, encoding='latin-1')
            except:
                print("⚠️  Latin-1 encoding failed, trying cp1252...")
                df = pd.read_csv(csv_file, encoding='cp1252')
        print(f"✅ Loaded {len(df)} rows")
    except Exception as e:
        print(f"❌ Error loading CSV: {str(e)}")
        return
    
    # Validate required columns
    required_cols = ['event_datetime']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"❌ Missing required columns: {missing_cols}")
        return
    
    # Show preview
    print("\n📋 DATA PREVIEW:")
    print("-" * 60)
    preview_cols = ['event_datetime', 'details_giraffe_mortality_cause', 'details_gir_species', 'details_country']
    available_cols = [col for col in preview_cols if col in df.columns]
    if available_cols:
        print(df[available_cols].head(3))
    else:
        print(df.head(3))
    print("-" * 60)
    
    # Validate mortality causes
    print("\n🔍 Validating mortality causes...")
    if 'details_giraffe_mortality_cause' in df.columns:
        invalid_causes = []
        for idx, row in df.iterrows():
            cause = row.get('details_giraffe_mortality_cause')
            if pd.notna(cause) and not validate_mortality_cause(str(cause)):
                invalid_causes.append((idx, cause))
        
        if invalid_causes:
            print(f"⚠️  Warning: {len(invalid_causes)} rows have non-standard mortality causes:")
            for idx, cause in invalid_causes[:5]:  # Show first 5
                print(f"   Row {idx}: {cause}")
            if len(invalid_causes) > 5:
                print(f"   ... and {len(invalid_causes) - 5} more")
            
            proceed = input("\n❓ Continue anyway? (y/N): ").lower().strip()
            if proceed != 'y':
                print("❌ Upload cancelled. Please review your mortality_cause values.")
                print("\n💡 Valid formats:")
                print("   - natural_predation, natural_disease, natural_old_age, etc.")
                print("   - unnatural_vehicle_collision, unnatural_poaching, unnatural_immobilisation, etc.")
                return
    
    # Get credentials
    print("\n🔐 EarthRanger Authentication")
    username = input("Username: ")
    password = getpass.getpass("Password: ")
    
    # Initialize uploader
    uploader = MortalityEventUploader()
    
    if not uploader.authenticate(username, password):
        return
    
    if not uploader.test_connection():
        print("❌ API connection test failed")
        return
    
    print("✅ API connection test successful!")
    
    # Confirm upload
    print("\n" + "=" * 60)
    print(f"📊 Ready to upload {len(df)} mortality events")
    print("   Event Type: 'mortality'")
    print("   Event Category: 'veterinary'")
    print("=" * 60)
    proceed = input(f"\n❓ Proceed with upload? (y/N): ").lower().strip()
    if proceed != 'y':
        print("❌ Upload cancelled")
        return
    
    # Upload events
    print(f"\n🚀 Starting upload of {len(df)} events...")
    print("-" * 60)
    
    successful = 0
    failed = 0
    failed_events = []
    
    for index, row in df.iterrows():
        try:
            # Parse datetime
            event_time = str(row.get('event_datetime', '2024-01-01T12:00:00Z'))
            
            # Fix malformed seconds (e.g., 12:50:150Z -> 12:50:15.0Z)
            import re
            match = re.search(r'(\d{2}:\d{2}):(\d{2,3})(Z|[\+\-]\d{2}:\d{2})', event_time)
            if match:
                time_prefix = match.group(1)  # HH:MM
                seconds_str = match.group(2)  # Seconds (possibly malformed)
                timezone = match.group(3)     # Z or offset
                
                # If seconds has 3 digits (e.g., "150"), treat last digit as fractional
                if len(seconds_str) == 3:
                    secs = seconds_str[:2]  # "15"
                    frac = seconds_str[2]   # "0"
                    fixed_seconds = f"{secs}.{frac}"
                else:
                    fixed_seconds = seconds_str
                
                # Reconstruct the time portion
                event_time = event_time[:match.start()] + f"{time_prefix}:{fixed_seconds}{timezone}"
            
            # Ensure Z timezone if not present
            if not event_time.endswith('Z') and '+' not in event_time and '-' not in event_time[-6:]:
                event_time = event_time + 'Z'
            
            # Create event structure
            event = {
                'event_type': 'giraffe_mortality',
                'event_category': 'veterinary',
                'title': 'Mortality Event',
                'time': event_time,
                'state': 'new',
                'priority': 300,  # High priority for mortality events
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
            
            # Add details from columns starting with 'details_'
            for col in df.columns:
                if col.startswith('details_') and pd.notna(row[col]):
                    key = col.replace('details_', '')
                    # Map mortality_cause to giraffe_mortality_cause
                    if key == 'mortality_cause':
                        key = 'giraffe_mortality_cause'
                    event['event_details'][key] = str(row[col])
            
            # Add giraffe_id if present
            if 'giraffe_id' in df.columns and pd.notna(row['giraffe_id']):
                event['event_details']['giraffe_id'] = str(row['giraffe_id'])
            
            # Ensure critical fields are present
            if 'giraffe_mortality_cause' not in event['event_details']:
                event['event_details']['giraffe_mortality_cause'] = 'Unknown'
            
            # Upload event
            result = uploader.upload_event(event)
            
            if result['success']:
                successful += 1
                if successful % 10 == 0:
                    print(f"✅ Progress: {successful}/{len(df)} uploaded")
            else:
                failed += 1
                failed_events.append({
                    'row': index + 1,
                    'serial_number': row.get('serial_number', index + 1),
                    'error': result['error'],
                    'event': event
                })
                print(f"❌ Row {index + 1} failed: {result['error']}")
                
        except Exception as e:
            failed += 1
            failed_events.append({
                'row': index + 1,
                'serial_number': row.get('serial_number', index + 1),
                'error': str(e),
                'event': None
            })
            print(f"❌ Row {index + 1} error: {str(e)}")
    
    # Final report
    print("\n" + "=" * 60)
    print("📊 UPLOAD COMPLETE!")
    print("=" * 60)
    print(f"✅ Successful:    {successful}")
    print(f"❌ Failed:        {failed}")
    print(f"📈 Success rate:  {(successful/(successful+failed)*100):.1f}%")
    print("=" * 60)
    
    # Save failed events for review
    if failed_events:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        failed_file = f"failed_mortality_upload_{timestamp}.json"
        
        with open(failed_file, 'w') as f:
            json.dump(failed_events, f, indent=2)
        
        print(f"\n⚠️  Failed events saved to: {failed_file}")
        print("   Review this file to retry failed uploads")
    
    print(f"\n✅ Upload process complete!")
    print(f"   You can now view these events in the Mortality Dashboard")
    print(f"   at https://twiga.pamdas.org")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Upload cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {str(e)}")
        sys.exit(1)
