#!/usr/bin/env python3
"""
Retry Failed EarthRanger Uploads
===============================

Retries the failed events from a previous upload attempt.

Usage:
    python retry_failed_uploads.py failed_direct_upload_20250818_151518.json

Author: Giraffe Conservation Foundation
Date: August 2025
"""

import json
import sys
import time
import requests
from datetime import datetime
import getpass

class RetryUploader:
    """Retry failed uploads with better error handling"""
    
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
    
    def upload_event(self, event_data, retry_count=3, delay=2):
        """Upload single event with retry logic"""
        for attempt in range(retry_count):
            try:
                response = requests.post(
                    f"{self.api_base}/activity/events/",
                    headers=self.headers,
                    json=event_data,
                    timeout=30
                )
                
                if response.status_code == 201:
                    return {'success': True, 'data': response.json()}
                elif response.status_code in [502, 504]:
                    # Gateway errors - retry after delay
                    if attempt < retry_count - 1:
                        print(f"⏳ Gateway error, retrying in {delay} seconds...")
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff
                        continue
                    else:
                        return {'success': False, 'error': f"{response.status_code}: Gateway timeout after {retry_count} attempts"}
                else:
                    return {'success': False, 'error': f"{response.status_code}: {response.text}"}
                    
            except requests.exceptions.Timeout:
                if attempt < retry_count - 1:
                    print(f"⏳ Request timeout, retrying in {delay} seconds...")
                    time.sleep(delay)
                    delay *= 2
                    continue
                else:
                    return {'success': False, 'error': f"Timeout after {retry_count} attempts"}
            except Exception as e:
                return {'success': False, 'error': str(e)}
        
        return {'success': False, 'error': 'Max retries exceeded'}

def main():
    """Main retry function"""
    print("🔄 EarthRanger Failed Upload Retry Tool")
    print("=" * 50)
    
    # Get failed events file
    if len(sys.argv) > 1:
        failed_file = sys.argv[1]
    else:
        failed_file = input("📁 Enter path to failed events JSON file: ").strip().strip('"')
    
    # Load failed events
    try:
        print(f"📖 Loading failed events: {failed_file}")
        with open(failed_file, 'r') as f:
            failed_events = json.load(f)
        print(f"✅ Loaded {len(failed_events)} failed events")
    except Exception as e:
        print(f"❌ Error loading file: {str(e)}")
        return
    
    # Get credentials
    username = input("EarthRanger Username: ")
    password = getpass.getpass("EarthRanger Password: ")
    
    # Initialize uploader
    uploader = RetryUploader()
    
    if not uploader.authenticate(username, password):
        print("❌ Authentication failed. Exiting.")
        return
    
    # Retry uploads
    print(f"🚀 Starting retry of {len(failed_events)} events...")
    successful = 0
    still_failed = []
    
    for i, failed_event in enumerate(failed_events, 1):
        event_data = failed_event['event']
        row_num = failed_event['row']
        
        print(f"📤 Retrying {i}/{len(failed_events)} (Row {row_num})...")
        
        result = uploader.upload_event(event_data)
        
        if result['success']:
            successful += 1
            print(f"✅ Row {row_num} succeeded on retry!")
        else:
            still_failed.append(failed_event)
            print(f"❌ Row {row_num} still failed: {result['error']}")
        
        # Brief pause between requests
        time.sleep(0.5)
    
    # Final report
    print(f"\n📊 RETRY COMPLETE!")
    print(f"✅ Successful retries: {successful}")
    print(f"❌ Still failed: {len(still_failed)}")
    print(f"📈 Retry success rate: {(successful/len(failed_events)*100):.1f}%")
    
    # Save still-failed events
    if still_failed:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        still_failed_file = f"still_failed_{timestamp}.json"
        with open(still_failed_file, 'w') as f:
            json.dump(still_failed, f, indent=2, default=str)
        print(f"💾 Still-failed events saved to: {still_failed_file}")

if __name__ == "__main__":
    main()
