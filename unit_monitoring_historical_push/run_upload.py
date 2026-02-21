#!/usr/bin/env python3
"""
Non-interactive wrapper for unit_monitoring_upload.py
Usage: python run_upload.py <csv_file> <username> <password>
"""

import sys
import os
import pandas as pd
import requests
import json
import getpass
from datetime import datetime
import time
import logging

# Import the uploader class
from unit_monitoring_upload import UnitMonitoringUploader

def main():
    if len(sys.argv) < 4:
        print("Usage: python run_upload.py <csv_file> <username> <password>")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    
    print("🔧 Unit Monitoring Historical Event Push Tool")
    print("=" * 50)
    print(f"CSV File: {csv_file}")
    print(f"Username: {username}")
    print()
    
    if not os.path.exists(csv_file):
        print(f"❌ File not found: {csv_file}")
        sys.exit(1)
    
    # Create uploader instance
    uploader = UnitMonitoringUploader()
    
    # Authenticate directly
    print("🔐 Authenticating with EarthRanger...")
    try:
        token_data = {
            'grant_type': 'password',
            'username': username,
            'password': password,
            'client_id': 'das_web_client'
        }
        
        response = requests.post(uploader.token_url, data=token_data)
        
        if response.status_code == 200:
            token_info = response.json()
            uploader.access_token = token_info['access_token']
            uploader.headers['Authorization'] = f'Bearer {uploader.access_token}'
            print("✅ Authentication successful!")
        else:
            print(f"❌ Authentication failed: {response.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Authentication error: {str(e)}")
        sys.exit(1)
    
    # Load and validate data
    print(f"📖 Loading CSV file: {csv_file}")
    df = pd.read_csv(csv_file)
    print(f"📊 Loaded {len(df)} records")
    
    if not uploader.validate_csv_data(df):
        print("❌ Data validation failed")
        sys.exit(1)
    
    # Test API connection
    print("🔍 Testing API connection...")
    test_url = f"{uploader.api_base}/activity/events"
    test_response = requests.get(test_url, headers=uploader.headers, params={'limit': 1})
    
    if test_response.status_code != 200:
        print(f"❌ API connection test failed: {test_response.status_code}")
        sys.exit(1)
    else:
        print("✅ API connection test successful!")
    
    # Upload events
    print(f"\n⚠️ About to upload {len(df)} unit monitoring events")
    print("Starting upload...")
    
    success_count, failed_events = uploader.upload_events(df)
    
    if success_count > 0:
        print(f"\n🎉 Successfully uploaded {success_count} events!")
    
    if failed_events:
        print(f"⚠️ {len(failed_events)} events failed to upload")
        print("Check the failed events file for details")
    
    sys.exit(0 if len(failed_events) == 0 else 1)

if __name__ == "__main__":
    main()
