#!/usr/bin/env python3
"""
Quick Single Event Test
========================

Simple interactive script to test updating one event.
Perfect for your first test run!

Usage:
    python quick_test.py

Requirements:
    pip install ecoscope-release pandas

Author: Giraffe Conservation Foundation
Date: February 2026
"""

import getpass
import pandas as pd
import requests
from ecoscope.io import EarthRangerIO

def main():
    print("🦒 Quick Event Update Test")
    print("=" * 50)
    print("This tool will update ONE event to test the process.\n")
    
    # Get event ID
    event_id = input("📋 Enter the Event UUID to update: ").strip()
    
    if not event_id:
        print("❌ Event ID is required!")
        return
    
    print(f"\n📝 What do you want to update?")
    print("=" * 50)
    
    # Get update fields
    print("\nEvent Details (enter value or leave blank to skip):")
    detail_status = input("  Status (e.g., 'processed', 'analyzed'): ").strip()
    detail_sample_type = input("  Sample type (e.g., 'blood', 'tissue', 'hair'): ").strip()
    detail_notes = input("  Notes: ").strip()
    
    print("\nEvent Metadata (leave blank to skip):")
    priority_input = input("  Priority (e.g., 200, 300): ").strip()
    state = input("  State (new/active/resolved/false): ").strip()
    title = input("  Title: ").strip()
    
    # Build update data
    update_data = {}
    event_details = {}
    
    if detail_status:
        event_details['status'] = detail_status
    if detail_sample_type:
        event_details['sample_type'] = detail_sample_type
    if detail_notes:
        event_details['notes'] = detail_notes
    
    if event_details:
        update_data['event_details'] = event_details
    
    if priority_input:
        update_data['priority'] = int(priority_input)
    if state:
        update_data['state'] = state
    if title:
        update_data['title'] = title
    
    if not update_data:
        print("\n❌ No updates specified!")
        return
    
    # Show preview
    print("\n" + "=" * 50)
    print("📋 PREVIEW OF UPDATE")
    print("=" * 50)
    print(f"Event ID: {event_id}")
    print(f"Updates: {update_data}")
    
    confirm = input("\n✅ Proceed with update? (yes/no): ").strip().lower()
    
    if confirm not in ['yes', 'y']:
        print("❌ Update cancelled.")
        return
    
    # Get credentials
    print("\n🔐 EarthRanger Credentials")
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")
    
    # Connect and update
    try:
        print("\n🔐 Connecting to EarthRanger...")
        server_url = "https://twiga.pamdas.org"
        er_io = EarthRangerIO(
            server=server_url,
            username=username,
            password=password
        )
        print("✅ Connected!")
        
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
            import requests as req_lib
            session = req_lib.Session()
            # Get token
            auth_url = f"{server_url}/oauth2/token"
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
        
        # If updating event_details, merge with existing to avoid overwriting
        if 'event_details' in update_data:
            print(f"\n🔍 Fetching current event data to merge event_details...")
            try:
                current_events = er_io.get_events(event_ids=[event_id])
                if not current_events.empty:
                    current_event = current_events.iloc[0]
                    existing_details = {}
                    if 'event_details' in current_event and current_event['event_details']:
                        existing_details = current_event['event_details']
                        print(f"Current event_details: {existing_details}")
                    
                    # Merge existing + new
                    merged_details = {**existing_details, **update_data['event_details']}
                    update_data['event_details'] = merged_details
                    print(f"Merged event_details: {merged_details}")
            except Exception as fetch_error:
                print(f"⚠️ Could not fetch current event: {fetch_error}")
                print(f"⚠️ Proceeding anyway (may overwrite other fields)")
        
        print(f"\n📝 Updating event {event_id}...")
        
        # Use the authenticated session for PATCH
        url = f"{server_url}/api/v1.0/activity/events/{event_id}"
        response = session.patch(url, json=update_data)
        
        if response.status_code not in [200, 204]:
            print(f"❌ API returned {response.status_code}: {response.text}")
            return
        
        print("\n" + "=" * 50)
        print("✅ SUCCESS!")
        print("=" * 50)
        print(f"Event {event_id} has been updated.")
        print("\nUpdated fields:")
        for key, value in update_data.items():
            print(f"  - {key}: {value}")
        
        print("\n💡 TIP: Check EarthRanger to verify the changes!")
        
    except Exception as e:
        print(f"\n❌ Update failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
