"""
Historical Translocation Data Validator and Uploader
Validates CSV data and uploads to EarthRanger as giraffe_translocation events
"""

import pandas as pd
import requests
from datetime import datetime
import json
import sys
from pathlib import Path
from ecoscope.io.earthranger import EarthRangerIO

# Configuration
SERVER_URL = "https://twiga.pamdas.org"
CSV_FILE = r"G:\My Drive\Data management\streamlit\Historical event push\GCF_translocations_260114.csv"

# Event type mapping
EVENT_TYPE = "giraffe_translocation"
EVENT_CATEGORY = "veterinary"

def validate_csv(csv_path):
    """Validate CSV structure and data"""
    print("="*80)
    print("STEP 1: VALIDATING CSV FILE")
    print("="*80)
    
    try:
        df = pd.read_csv(csv_path)
        print(f"[OK] Successfully loaded CSV: {len(df)} rows")
    except Exception as e:
        print(f"[ERROR] Error loading CSV: {e}")
        return None
    
    # Required columns for translocation events
    required_cols = ['capture_date', 'origin_country', 'destination_country', 'species']
    recommended_cols = [
        'organisation_1', 'origin_site', 'destination_site',
        'origin_longitude', 'origin_latitude',
        'destination_longitude', 'destination_latitude',
        'total_individuals', 'females', 'males',
        'trans_type', 'trans_range', 'notes'
    ]
    
    print("\nColumn Validation:")
    missing_required = [col for col in required_cols if col not in df.columns]
    if missing_required:
        print(f"[ERROR] Missing REQUIRED columns: {missing_required}")
        return None
    else:
        print(f"[OK] All required columns present: {required_cols}")
    
    missing_recommended = [col for col in recommended_cols if col not in df.columns]
    if missing_recommended:
        print(f"[WARN] Missing recommended columns: {missing_recommended}")
    else:
        print(f"[OK] All recommended columns present")
    
    # Data validation
    print("\nData Validation:")
    
    # Check dates (DD-MM-YYYY format expected)
    invalid_dates = df[df['capture_date'].isna() | (df['capture_date'] == '')].shape[0]
    print(f"  - Dates (DD-MM-YYYY): {len(df) - invalid_dates}/{len(df)} valid ({invalid_dates} missing/invalid will be skipped)")
    
    # Check coordinates
    has_coords = df[
        df['origin_latitude'].notna() & 
        df['origin_longitude'].notna() &
        df['destination_latitude'].notna() &
        df['destination_longitude'].notna()
    ].shape[0]
    print(f"  - Complete coordinates: {has_coords}/{len(df)} events")
    
    # Check species
    unique_species = df['species'].dropna().unique()
    print(f"  - Unique species: {list(unique_species)}")
    
    # Check translocation types
    if 'trans_type' in df.columns:
        unique_types = df['trans_type'].dropna().unique()
        print(f"  - Translocation types: {list(unique_types)}")
    
    # Check countries
    if 'origin_country' in df.columns:
        unique_origins = df['origin_country'].dropna().unique()
        print(f"  - Origin countries: {list(unique_origins)}")
    
    if 'destination_country' in df.columns:
        unique_dests = df['destination_country'].dropna().unique()
        print(f"  - Destination countries: {list(unique_dests)}")
    
    print("\n[OK] CSV validation complete!")
    return df

def parse_date(date_str):
    """Parse date string in DD-MM-YYYY format to ISO format with 00:00:00+0000 for missing times"""
    if pd.isna(date_str) or date_str == '':
        return None
    
    try:
        # Handle DD-MM-YYYY format (e.g., "01-01-1971")
        dt = datetime.strptime(str(date_str), '%d-%m-%Y')
        return dt.strftime('%Y-%m-%dT00:00:00+0000')  # Use 00:00:00+0000 for missing times
    except:
        try:
            # Try DD-MM-YY format as fallback (e.g., "01-01-71")
            dt = datetime.strptime(str(date_str), '%d-%m-%y')
            return dt.strftime('%Y-%m-%dT00:00:00+0000')
        except:
            try:
                # Try pandas auto-detection
                dt = pd.to_datetime(date_str)
                return dt.strftime('%Y-%m-%dT00:00:00+0000')
            except:
                print(f"  [WARN] Could not parse date: {date_str}")
                return None

def create_event_payload(row, event_type_value):
    """Create EarthRanger event payload from CSV row"""
    
    # Parse date - use capture_date or release_date
    event_time = parse_date(row.get('capture_date'))
    if not event_time:
        event_time = parse_date(row.get('release_date'))
    if not event_time:
        event_time = datetime.now().strftime('%Y-%m-%dT00:00:00+0000')
    
    # Build event_details
    event_details = {}
    
    # Organizations
    if pd.notna(row.get('organisation_1')):
        event_details['organisation_1'] = str(row['organisation_1'])
    if pd.notna(row.get('organisation_2')):
        event_details['organisation_2'] = str(row['organisation_2'])
    if pd.notna(row.get('organisation_3')):
        event_details['organisation_3'] = str(row['organisation_3'])
    
    # Species - use raw CSV value
    if pd.notna(row.get('species')):
        event_details['species'] = str(row['species'])
    
    # Countries - use raw CSV values
    if pd.notna(row.get('origin_country')):
        event_details['origin_country'] = str(row['origin_country'])
    if pd.notna(row.get('destination_country')):
        event_details['destination_country'] = str(row['destination_country'])
    
    # Location objects with coordinates
    if pd.notna(row.get('origin_latitude')) and pd.notna(row.get('origin_longitude')):
        event_details['origin_location'] = {
            'latitude': float(row['origin_latitude']),
            'longitude': float(row['origin_longitude'])
        }
        if pd.notna(row.get('origin_site')):
            event_details['origin_location']['name'] = str(row['origin_site'])
    elif pd.notna(row.get('origin_site')):
        event_details['origin_location'] = {'name': str(row['origin_site'])}
    
    if pd.notna(row.get('destination_latitude')) and pd.notna(row.get('destination_longitude')):
        event_details['destination_location'] = {
            'latitude': float(row['destination_latitude']),
            'longitude': float(row['destination_longitude'])
        }
        if pd.notna(row.get('destination_site')):
            event_details['destination_location']['name'] = str(row['destination_site'])
    elif pd.notna(row.get('destination_site')):
        event_details['destination_location'] = {'name': str(row['destination_site'])}
    
    # Numbers
    if pd.notna(row.get('total_individuals')):
        event_details['total_individuals'] = int(row['total_individuals'])
    if pd.notna(row.get('females')):
        event_details['females'] = int(row['females'])
    if pd.notna(row.get('males')):
        event_details['males'] = int(row['males'])
    
    # Translocation type and range - use raw CSV values
    if pd.notna(row.get('trans_type')):
        event_details['translocation_type'] = str(row['trans_type'])
    if pd.notna(row.get('trans_range')):
        event_details['range'] = str(row['trans_range'])
    
    # Notes
    if pd.notna(row.get('notes')):
        event_details['notes'] = str(row['notes'])
    if pd.notna(row.get('report/source/url')):
        event_details['source'] = str(row['report/source/url'])
    
    # Dates
    if pd.notna(row.get('capture_date_end')):
        event_details['capture_date_end'] = str(row['capture_date_end'])
    if pd.notna(row.get('release_date')):
        event_details['release_date'] = str(row['release_date'])
    
    # Build main event payload
    payload = {
        'event_type': event_type_value,
        'time': event_time,
        'priority': 200,  # Normal priority
        'state': 'active',
        'event_details': event_details
    }
    
    # Add location if we have destination coordinates
    if pd.notna(row.get('destination_latitude')) and pd.notna(row.get('destination_longitude')):
        payload['location'] = {
            'latitude': float(row['destination_latitude']),
            'longitude': float(row['destination_longitude'])
        }
    
    return payload

def get_event_type_value(er_io):
    """Get the event_type value for giraffe_translocation"""
    print("\n" + "="*80)
    print("STEP 2: FETCHING EVENT TYPE CONFIGURATION")
    print("="*80)
    
    # Use the known event type
    event_type_value = "giraffe_translocation_3"
    print(f"[OK] Using event type: {event_type_value}")
    return event_type_value

def upload_events(df, username, password, dry_run=True, start_from=0, limit=None):
    """Upload events to EarthRanger"""
    
    # Create EarthRangerIO connection first
    try:
        er_io = EarthRangerIO(
            server=SERVER_URL,
            username=username,
            password=password
        )
    except Exception as e:
        print(f"[ERROR] Failed to connect to EarthRanger: {e}")
        return
    
    event_type_value = get_event_type_value(er_io)
    if not event_type_value:
        print("[ERROR] Cannot proceed without event type")
        return
    
    print("\n" + "="*80)
    if dry_run:
        print("STEP 3: DRY RUN - SHOWING WHAT WOULD BE UPLOADED")
    else:
        print("STEP 3: UPLOADING EVENTS TO EARTHRANGER")
        if start_from > 0:
            print(f"[INFO] Starting from row {start_from + 1} (skipping first {start_from} already uploaded)")
    print("="*80)
    
    url = f"{SERVER_URL}/api/v1.0/activity/events"
    
    success_count = 0
    error_count = 0
    errors = []
    
    for idx, row in df.iterrows():
        # Skip already uploaded events
        if idx < start_from:
            continue
        
        # Skip rows with empty capture_date
        if pd.isna(row.get('capture_date')) or row.get('capture_date') == '':
            print(f"[SKIP] Row {idx + 1}: Empty capture_date, skipping")
            continue
        
        # Stop if we've reached the limit
        if limit and idx >= start_from + limit:
            print(f"\n[INFO] Reached limit of {limit} rows, stopping")
            break
        
        try:
            payload = create_event_payload(row, event_type_value)
            
            if dry_run:
                # Just show the first few payloads
                if idx < 3:
                    print(f"\n--- Event {idx + 1}/{len(df)} ---")
                    print(f"Date: {payload['time']}")
                    print(f"Species: {payload['event_details'].get('species', 'N/A')}")
                    print(f"Origin: {payload['event_details'].get('origin_location', {}).get('name', 'N/A')}")
                    print(f"Destination: {payload['event_details'].get('destination_location', {}).get('name', 'N/A')}")
                    print(f"Payload preview: {json.dumps(payload, indent=2)[:500]}...")
                elif idx == 3:
                    print(f"\n... (showing first 3 of {len(df)} events) ...")
                
                success_count += 1
            else:
                # Actually upload using EarthRangerIO's post_event method
                try:
                    result = er_io.post_event(events=[payload])
                    success_count += 1
                    if (idx + 1) % 10 == 0:
                        print(f"[OK] Uploaded {idx + 1}/{len(df)} events")
                except Exception as upload_error:
                    error_count += 1
                    error_msg = f"Row {idx + 1}: {str(upload_error)}"
                    errors.append(error_msg)
                    print(f"[ERROR] {error_msg}")
                    
        except Exception as e:
            error_count += 1
            error_msg = f"Row {idx + 1}: {str(e)}"
            errors.append(error_msg)
            print(f"[ERROR] {error_msg}")
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"[OK] Successfully processed: {success_count}/{len(df)} events")
    if error_count > 0:
        print(f"[ERROR] Errors: {error_count}")
        print("\nError details:")
        for error in errors[:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")
    
    if dry_run:
        print("\n[WARN] This was a DRY RUN - no data was uploaded")
        print("To actually upload, run: python validate_and_upload_historical.py <username> <password> --upload")

def main():
    """Main execution"""
    print("\n" + "="*80)
    print("EARTHRANGER HISTORICAL TRANSLOCATION DATA UPLOADER")
    print("="*80)
    
    # Parse command line arguments
    if len(sys.argv) < 3:
        print("\n[ERROR] Usage: python validate_and_upload_historical.py <username> <password> [--upload] [--start-from N] [--limit N]")
        print("\nWithout --upload flag, runs in DRY RUN mode (validation only)")
        print("Use --start-from N to skip first N rows (useful to resume after interruption)")
        print("Use --limit N to upload only N rows (useful for testing)")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    upload_mode = '--upload' in sys.argv
    
    # Check for --start-from parameter
    start_from = 0
    for i, arg in enumerate(sys.argv):
        if arg == '--start-from' and i + 1 < len(sys.argv):
            try:
                start_from = int(sys.argv[i + 1])
                print(f"[INFO] Will start from row {start_from + 1}")
            except ValueError:
                print(f"[WARN] Invalid --start-from value, using 0")
    
    # Check for --limit parameter
    limit = None
    for i, arg in enumerate(sys.argv):
        if arg == '--limit' and i + 1 < len(sys.argv):
            try:
                limit = int(sys.argv[i + 1])
                print(f"[INFO] Will upload only {limit} rows")
            except ValueError:
                print(f"[WARN] Invalid --limit value, uploading all rows")
    
    # Step 1: Validate CSV
    df = validate_csv(CSV_FILE)
    if df is None:
        print("\n[ERROR] CSV validation failed. Please fix errors and try again.")
        sys.exit(1)
    
    # Step 2 & 3: Upload or dry run
    upload_events(df, username, password, dry_run=not upload_mode, start_from=start_from, limit=limit)
    
    print("\n" + "="*80)
    print("DONE!")
    print("="*80)

if __name__ == "__main__":
    main()
