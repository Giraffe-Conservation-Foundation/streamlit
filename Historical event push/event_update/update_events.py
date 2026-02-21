#!/usr/bin/env python3
"""
EarthRanger Event Update Script
================================

Update existing events in EarthRanger using ecoscope's authenticated session.
Useful for updating event statuses, event_details fields, locations, priorities, etc.

Usage:
    python update_events.py

Requirements:
    pip install ecoscope-release pandas requests

Author: Giraffe Conservation Foundation
Date: February 2026
"""

import pandas as pd
import sys
import os
from datetime import datetime
import getpass
import requests
import json
from ecoscope.io import EarthRangerIO

class EventUpdater:
    """Update existing EarthRanger events"""
    
    def __init__(self, server_url="https://twiga.pamdas.org"):
        self.server_url = server_url
        self.er_io = None
        self.api_base = f"{server_url}/api/v1.0"
        self.username = None
        self.password = None
    
    def connect(self, username, password):
        """Connect to EarthRanger"""
        try:
            print("🔐 Connecting to EarthRanger...")
            self.username = username
            self.password = password
            # Use ecoscope - it handles authentication internally
            self.er_io = EarthRangerIO(
                server=self.server_url,
                username=username,
                password=password
            )
            print("✅ Connected successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {str(e)}")
            return False
    
    def update_single_event(self, event_id, update_data, merge_event_details=True):
        """Update a single event using direct API"""
        try:
            print(f"\n📝 Updating event {event_id}...")
            
            # If updating event_details, merge with existing data to avoid overwriting
            if merge_event_details and 'event_details' in update_data:
                print(f"  🔍 Fetching current event data to merge event_details...")
                try:
                    # Get current event using ecoscope (this works)
                    current_events = self.er_io.get_events(event_ids=[event_id])
                    if not current_events.empty:
                        current_event = current_events.iloc[0]
                        
                        # Get existing event_details
                        existing_details = {}
                        if 'event_details' in current_event and current_event['event_details']:
                            existing_details = current_event['event_details']
                            print(f"  📋 Current event_details: {existing_details}")
                        
                        # Merge: existing details + new updates
                        merged_details = {**existing_details, **update_data['event_details']}
                        update_data['event_details'] = merged_details
                        print(f"  ✨ Merged event_details: {merged_details}")
                    else:
                        print(f"  ⚠️ Could not fetch current event, updating with provided data only")
                except Exception as fetch_error:
                    print(f"  ⚠️ Could not fetch current event: {fetch_error}")
                    print(f"  ⚠️ Proceeding with update (may overwrite other event_details fields)")
            
            # Use ecoscope's authenticated session for PATCH request
            url = f"{self.api_base}/activity/events/{event_id}"
            print(f"  📤 Sending PATCH request to API...")
            
            # Try to get authenticated session from ecoscope
            session = None
            if hasattr(self.er_io, 'erclient') and hasattr(self.er_io.erclient, 'session'):
                session = self.er_io.erclient.session
            elif hasattr(self.er_io, 'client') and hasattr(self.er_io.client, 'session'):
                session = self.er_io.client.session
            else:
                # Fallback: use requests with manual auth
                import requests as req_lib
                session = req_lib.Session()
                # Try to get token
                auth_url = f"{self.server_url}/oauth2/token"
                auth_response = session.post(auth_url, data={
                    'username': self.username,
                    'password': self.password,
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
                    print(f"  ❌ Authentication failed: {auth_response.status_code}")
                    return {'success': False, 'error': f'Auth failed: {auth_response.status_code}'}
            
            response = session.patch(
                url,
                json=update_data
            )
            
            # Check response
            if response.status_code in [200, 204]:
                # Verify the update by fetching the event again
                print(f"  🔍 Verifying update...")
                try:
                    updated_events = self.er_io.get_events(event_ids=[event_id])
                    if not updated_events.empty:
                        updated_event = updated_events.iloc[0]
                        if 'event_details' in update_data and 'event_details' in updated_event:
                            print(f"  ✓ Current event_details after update: {updated_event['event_details']}")
                except Exception as verify_error:
                    print(f"  ⚠️ Could not verify update: {verify_error}")
                
                print(f"✅ Successfully updated event {event_id}")
                return {'success': True, 'data': response.json() if response.text else {}}
            else:
                error_msg = f"API returned {response.status_code}: {response.text}"
                print(f"❌ Failed to update event {event_id}: {error_msg}")
                return {'success': False, 'error': error_msg}
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Failed to update event {event_id}: {error_msg}")
            return {'success': False, 'error': error_msg}
    
    def update_from_csv(self, csv_file, dry_run=False):
        """Update multiple events from CSV file"""
        try:
            print(f"\n📂 Loading CSV file: {csv_file}")
            df = pd.read_csv(csv_file)
            
            # Validate required column
            if 'event_id' not in df.columns:
                print("❌ CSV must have 'event_id' column!")
                return
            
            total_events = len(df)
            print(f"📊 Found {total_events} event(s) to update")
            
            if dry_run:
                print("\n🔍 DRY RUN MODE - No changes will be made")
                print("\nPreview of updates:")
                print(df.head(10))
                return
            
            # Process each event
            results = []
            successful = 0
            failed = 0
            
            for idx, row in df.iterrows():
                event_id = row['event_id']
                
                # Build update data from CSV columns
                update_data = {}
                
                # Check for direct field updates
                if 'priority' in row and pd.notna(row['priority']):
                    update_data['priority'] = int(row['priority'])
                
                if 'state' in row and pd.notna(row['state']):
                    update_data['state'] = row['state']
                
                if 'title' in row and pd.notna(row['title']):
                    update_data['title'] = row['title']
                
                # Check for location update
                if 'latitude' in row and 'longitude' in row:
                    if pd.notna(row['latitude']) and pd.notna(row['longitude']):
                        update_data['location'] = {
                            'latitude': float(row['latitude']),
                            'longitude': float(row['longitude'])
                        }
                
                # Build event_details from columns starting with 'detail_' or known prefixes
                event_details = {}
                known_detail_prefixes = ['girsam_', 'unit_', 'deployment_', 'sample_']
                
                for col in df.columns:
                    # Handle columns with 'detail_' prefix
                    if col.startswith('detail_') and pd.notna(row[col]):
                        field_name = col.replace('detail_', '')
                        event_details[field_name] = row[col]
                    # Handle known event_details field prefixes directly
                    elif any(col.startswith(prefix) for prefix in known_detail_prefixes) and pd.notna(row[col]):
                        event_details[col] = row[col]
                
                if event_details:
                    update_data['event_details'] = event_details
                
                # Update the event
                result = self.update_single_event(event_id, update_data)
                
                if result['success']:
                    successful += 1
                else:
                    failed += 1
                
                results.append({
                    'event_id': event_id,
                    'success': result['success'],
                    'error': result.get('error', '')
                })
                
                # Progress update
                print(f"Progress: {idx + 1}/{total_events} ({successful} successful, {failed} failed)")
            
            # Summary
            print("\n" + "=" * 50)
            print("📊 UPDATE SUMMARY")
            print("=" * 50)
            print(f"✅ Successful: {successful}")
            print(f"❌ Failed: {failed}")
            print(f"📈 Total: {total_events}")
            
            # Save results
            results_df = pd.DataFrame(results)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_file = f"update_results_{timestamp}.csv"
            results_df.to_csv(results_file, index=False)
            print(f"\n💾 Results saved to: {results_file}")
            
        except Exception as e:
            print(f"❌ Error processing CSV: {str(e)}")
            import traceback
            traceback.print_exc()

def main():
    """Main function"""
    print("🦒 EarthRanger Event Update Tool")
    print("=" * 50)
    
    # Get CSV file
    csv_file = input("📁 Enter path to CSV file with updates: ").strip().strip('"')
    
    if not os.path.exists(csv_file):
        print(f"❌ File not found: {csv_file}")
        return
    
    # Preview mode
    preview = input("\n🔍 Preview only (no changes)? (y/n): ").strip().lower()
    dry_run = preview == 'y'
    
    # Get credentials
    print("\n🔐 EarthRanger Credentials")
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")
    
    # Create updater and connect
    updater = EventUpdater()
    
    if not updater.connect(username, password):
        print("❌ Failed to connect. Exiting...")
        return
    
    # Run updates
    updater.update_from_csv(csv_file, dry_run=dry_run)
    
    print("\n✅ Update process complete!")

if __name__ == "__main__":
    main()
