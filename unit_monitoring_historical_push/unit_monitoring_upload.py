#!/usr/bin/env python3
"""
Unit Monitoring Historical Event Push Script
===========================================

Purpose: Upload historical unit monitoring events to EarthRanger
Event Type: unit_monitoring / unit_update              # Add user field (using created_by_user field)
        if 'name' in row and not pd.isna(row['name']) and str(row['name']).strip():
            name_value = str(row['name']).strip()
            # Only add if it's not empty
            if name_value:
                event['created_by_user'] = name_value
                print(f"  👤 Setting created_by_user to: {name_value}")reported_by field (matches EarthRanger UI field name)
        if 'name' in row and not pd.isna(row['name']) and str(row['name']).strip():
            name_value = str(row['name']).strip()
            # Only add if it's not empty
            if name_value:
                event['reported_by'] = name_value
                print(f"  👤 Setting reported_by to: {name_value}")
This script handles bulk upload of historical unit monitoring data including:
- Unit deployments and retrievals
- Battery maintenance events  
- Unit status updates
- Location changes and maintenance activities

Event Structure:
- event_category: "unit_monitoring"
- event_type: "unit_update"
- event_details: Contains unit_id, action, country, notes, etc.

Author: Giraffe Conservation Foundation
Date: August 2025
Version: 1.0
"""

import pandas as pd
import requests
import json
import getpass
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path
import logging
import time

class UnitMonitoringUploader:
    """Upload historical unit monitoring events to EarthRanger"""
    
    def __init__(self):
        self.server_url = "https://twiga.pamdas.org"
        self.api_base = f"{self.server_url}/api/v1.0"
        self.token_url = f"{self.server_url}/oauth2/token"
        self.access_token = None
        self.headers = {'Content-Type': 'application/json'}
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging for the upload process"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(f'unit_monitoring_upload_{datetime.now().strftime("%Y%m%d")}.log')
            ]
        )
        self.logger = logging.getLogger(__name__)

    def authenticate(self):
        """Authenticate with EarthRanger using OAuth2"""
        print("🔐 EarthRanger Authentication for Unit Monitoring Upload")
        print("=" * 55)
        print(f"Server: {self.server_url}")
        
        username = input("Username: ").strip()
        password = getpass.getpass("Password: ")
        
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
                self.logger.info("Successfully authenticated with EarthRanger")
                return True
            else:
                print(f"❌ Authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Authentication error: {str(e)}")
            return False

    def validate_csv_data(self, df):
        """Validate CSV data structure and content"""
        print("🔍 Validating CSV data...")
        
        required_columns = ['unit_id', 'action', 'country', 'notes', 'date_time']
        # name is optional but recommended
        optional_columns = ['name', 'subject_id', 'latitude', 'longitude']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"❌ Missing required columns: {missing_columns}")
            return False
        
        # Validate data types and content
        errors = []
        
        for idx, row in df.iterrows():
            row_errors = []
            
            # Validate required fields
            if pd.isna(row['unit_id']) or str(row['unit_id']).strip() == '':
                row_errors.append("Missing unit_id")
            
            if pd.isna(row['action']) or str(row['action']).strip() == '':
                row_errors.append("Missing action")
            
            if pd.isna(row['country']) or str(row['country']).strip() == '':
                row_errors.append("Missing country")
            
            if pd.isna(row['notes']) or str(row['notes']).strip() == '':
                row_errors.append("Missing notes")
            
            # Validate date with explicit format handling
            try:
                pd.to_datetime(row['date_time'], format='%d-%m-%Y %H:%M:%S', dayfirst=True)
            except:
                try:
                    pd.to_datetime(row['date_time'])
                except:
                    row_errors.append("Invalid date_time format")
            
            # Validate coordinates if provided
            if 'latitude' in df.columns and not pd.isna(row['latitude']):
                try:
                    lat = float(row['latitude'])
                    if not (-90 <= lat <= 90):
                        row_errors.append("Invalid latitude range")
                except:
                    row_errors.append("Invalid latitude format")
            
            if 'longitude' in df.columns and not pd.isna(row['longitude']):
                try:
                    lon = float(row['longitude'])
                    if not (-180 <= lon <= 180):
                        row_errors.append("Invalid longitude range")
                except:
                    row_errors.append("Invalid longitude format")
            
            if row_errors:
                errors.append(f"Row {idx + 1}: {', '.join(row_errors)}")
        
        if errors:
            print(f"❌ Found {len(errors)} validation errors:")
            for error in errors[:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more errors")
            return False
        
        print(f"✅ Data validation passed for {len(df)} records")
        return True

    def create_event_payload(self, row):
        """Create event payload for EarthRanger API"""
        # Convert date_time to proper format - ensure YYYY-MM-DD format
        try:
            date_str = str(row['date_time']).strip()
            
            # Handle different date formats
            if date_str.count('-') == 2:
                # Check if it's DD-MM-YYYY or YYYY-MM-DD format
                parts = date_str.split('T')[0].split('-')
                if len(parts[0]) == 2:  # DD-MM-YYYY format
                    dt = pd.to_datetime(row['date_time'], format='%d-%m-%Y %H:%M:%S', dayfirst=True)
                else:  # YYYY-MM-DD format
                    dt = pd.to_datetime(row['date_time'])
            else:
                dt = pd.to_datetime(row['date_time'])
            
            # Format as ISO with Z suffix (no timezone offset)
            event_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        except Exception as e:
            print(f"⚠️ Date parsing error for {row['date_time']}: {e}")
            # Fallback to current time if date parsing fails
            event_time = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Create event payload following the direct_api_upload.py pattern
        event = {
            'event_type': 'unit_update',
            'title': 'Unit Update',
            'time': event_time,
            'state': 'new',
            'priority': 200,
            'is_collection': False,
            'event_details': {
                'unitupdate_unitid': str(row['unit_id']).strip(),
                'unitupdate_action': str(row['action']).strip(),
                'unitupdate_country': str(row['country']).strip(),
                'unitupdate_notes': str(row['notes']).strip()
            }
        }
        
        # Add optional subject ID if available
        if 'subject_id' in row and not pd.isna(row['subject_id']) and str(row['subject_id']).strip():
            event['event_details']['unitupdate_subjectid'] = str(row['subject_id']).strip()
        elif 'subject' in row and not pd.isna(row['subject']) and str(row['subject']).strip():
            event['event_details']['unitupdate_subjectid'] = str(row['subject']).strip()
        
        # Add location if coordinates provided
        if ('latitude' in row and not pd.isna(row['latitude']) and 
            'longitude' in row and not pd.isna(row['longitude'])):
            try:
                lat = float(row['latitude'])
                lon = float(row['longitude'])
                if lat != 0 and lon != 0:  # Avoid 0,0 coordinates
                    event['location'] = {
                        'latitude': lat,
                        'longitude': lon
                    }
                    # Also store in event_details for reliable retrieval
                    event['event_details']['latitude'] = str(lat)
                    event['event_details']['longitude'] = str(lon)
            except (ValueError, TypeError):
                pass  # Skip invalid coordinates
        
        # Add user field (correct EarthRanger API structure)
        if 'name' in row and not pd.isna(row['name']) and str(row['name']).strip():
            name_value = str(row['name']).strip()
            # Only add if it's not empty
            if name_value:
                event['user'] = {
                    'username': name_value
                }
                print(f"  � Setting user.username to: {name_value}")
        
        return event

    def upload_events(self, df):
        """Upload events to EarthRanger"""
        print(f"🚀 Starting upload of {len(df)} unit monitoring events...")
        
        success_count = 0
        failed_events = []
        url = f"{self.api_base}/activity/events/"
        
        for idx, row in df.iterrows():
            try:
                payload = self.create_event_payload(row)
                
                response = requests.post(url, headers=self.headers, data=json.dumps(payload))
                
                if response.status_code in [200, 201]:
                    success_count += 1
                    if success_count % 10 == 0:
                        print(f"  ✅ Uploaded {success_count}/{len(df)} events...")
                else:
                    error_info = {
                        'row_index': idx,
                        'unit_id': row['unit_id'],
                        'action': row['action'],
                        'date_time': str(row['date_time']),
                        'status_code': response.status_code,
                        'error_message': response.text,
                        'payload': payload
                    }
                    failed_events.append(error_info)
                    print(f"  ❌ Failed to upload row {idx + 1}: {response.status_code}")
                
                # Rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                error_info = {
                    'row_index': idx,
                    'unit_id': row.get('unit_id', 'Unknown'),
                    'action': row.get('action', 'Unknown'),
                    'date_time': str(row.get('date_time', 'Unknown')),
                    'status_code': 'Exception',
                    'error_message': str(e),
                    'payload': None
                }
                failed_events.append(error_info)
                print(f"  ❌ Exception uploading row {idx + 1}: {str(e)}")
        
        # Save failed events if any
        if failed_events:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            failed_file = f"failed_unit_monitoring_upload_{timestamp}.json"
            
            with open(failed_file, 'w') as f:
                json.dump(failed_events, f, indent=2, default=str)
            
            print(f"💾 Saved {len(failed_events)} failed events to: {failed_file}")
        
        # Print summary
        print(f"\n📊 Upload Summary:")
        print(f"  ✅ Successful: {success_count}")
        print(f"  ❌ Failed: {len(failed_events)}")
        print(f"  📈 Success Rate: {(success_count/len(df)*100):.1f}%")
        
        return success_count, failed_events

    def generate_csv_template(self):
        """Generate a CSV template for unit monitoring events"""
        template_data = [
            {
                'unit_id': 'TAIL-ST1386',
                'action': 'deployment',
                'country': 'NAM',
                'notes': 'Initial deployment in conservancy',
                'subject_id': 'subject-uuid-123',
                'latitude': -22.5,
                'longitude': 17.1,
                'date_time': '2024-01-15 10:30:00',
                'name': 'johndoe'
            },
            {
                'unit_id': 'TAIL-ST1387',
                'action': 'maintenance',
                'country': 'BWA',
                'notes': 'Battery replacement completed',
                'subject_id': 'subject-uuid-124',
                'latitude': -24.2,
                'longitude': 21.4,
                'date_time': '2024-02-20 14:15:00',
                'name': 'janedoe'
            },
            {
                'unit_id': 'TAIL-ST1388',
                'action': 'battery_change',
                'country': 'ZAF',
                'notes': 'Routine battery maintenance',
                'subject_id': '',
                'latitude': '',
                'longitude': '',
                'date_time': '2024-03-10 09:00:00',
                'name': 'fieldtech'
            }
        ]
        
        df = pd.DataFrame(template_data)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        filename = f"unit_monitoring_template_{timestamp}.csv"
        
        df.to_csv(filename, index=False)
        
        print(f"📝 CSV template created: {filename}")
        print("\nTemplate includes:")
        print("  - unit_id: Tracking unit identifier (required)")
        print("  - action: Type of action (deployment, maintenance, battery_change, retrieval, other)")
        print("  - country: Country code (NAM, BWA, ZAF, etc.) (required)")
        print("  - notes: Description of the event (required)")
        print("  - subject_id: Associated subject UUID (optional)")
        print("  - latitude/longitude: Event location coordinates (optional)")
        print("  - date_time: Event timestamp (YYYY-MM-DD HH:MM:SS format)")
        
        return filename

def main():
    """Main execution function"""
    print("🔧 Unit Monitoring Historical Event Push Tool")
    print("=" * 50)
    print("Upload historical unit monitoring events to EarthRanger")
    print("Event Category: unit_monitoring")
    print("Event Type: unit_update")
    print()
    
    uploader = UnitMonitoringUploader()
    
    # Menu options
    while True:
        print("\nOptions:")
        print("1. Generate CSV template")
        print("2. Upload historical events from CSV")
        print("3. Exit")
        
        choice = input("\nSelect option (1-3): ").strip()
        
        if choice == '1':
            try:
                filename = uploader.generate_csv_template()
                print(f"\n✅ Template created successfully: {filename}")
                print("Fill in your data and use option 2 to upload.")
            except Exception as e:
                print(f"❌ Error creating template: {str(e)}")
        
        elif choice == '2':
            try:
                # Get CSV file
                csv_file = input("Path to CSV file: ").strip().strip('"')
                
                if not os.path.exists(csv_file):
                    print(f"❌ File not found: {csv_file}")
                    continue
                
                # Load and validate data
                print(f"📖 Loading CSV file: {csv_file}")
                df = pd.read_csv(csv_file)
                print(f"📊 Loaded {len(df)} records")
                
                if not uploader.validate_csv_data(df):
                    print("❌ Please fix validation errors and try again")
                    continue
                
                # Authenticate
                if not uploader.authenticate():
                    print("❌ Authentication failed")
                    continue
                
                # Test connection
                print("🔍 Testing API connection...")
                test_url = f"{uploader.api_base}/activity/events"
                test_response = requests.get(test_url, headers=uploader.headers, params={'limit': 1})
                
                if test_response.status_code != 200:
                    print(f"❌ API connection test failed: {test_response.status_code}")
                    continue
                else:
                    print("✅ API connection test successful!")
                
                # Confirm upload
                print(f"\n⚠️ About to upload {len(df)} unit monitoring events")
                confirm = input("Proceed with upload? (y/N): ").strip().lower()
                
                if confirm == 'y':
                    success_count, failed_events = uploader.upload_events(df)
                    
                    if success_count > 0:
                        print(f"\n🎉 Successfully uploaded {success_count} events!")
                    
                    if failed_events:
                        print(f"⚠️ {len(failed_events)} events failed to upload")
                        print("Check the failed events file for details")
                else:
                    print("❌ Upload cancelled")
                    
            except Exception as e:
                print(f"❌ Error during upload: {str(e)}")
        
        elif choice == '3':
            print("👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid option. Please select 1, 2, or 3.")

if __name__ == "__main__":
    main()
