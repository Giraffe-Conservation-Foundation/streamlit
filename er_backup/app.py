# -*- coding: utf-8 -*-
"""
ER Backup Tool - High Performance Incremental Version
Designed for large date ranges with month-by-month processing and resume capabilities.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import json
import os
import zipfile
import io
from pathlib import Path
import warnings
import pickle
warnings.filterwarnings("ignore")

# Ecoscope imports for EarthRanger integration
try:
    from ecoscope.io.earthranger import EarthRangerIO
    ECOSCOPE_AVAILABLE = True
except ImportError:
    ECOSCOPE_AVAILABLE = False
    st.warning("Ecoscope package not available. Please install ecoscope to use this backup tool.")

def init_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'username' not in st.session_state:
        st.session_state.username = ""
    if 'password' not in st.session_state:
        st.session_state.password = ""
    if 'server_url' not in st.session_state:
        st.session_state.server_url = "https://twiga.pamdas.org"
    if 'backup_progress' not in st.session_state:
        st.session_state.backup_progress = {}
    if 'current_backup_id' not in st.session_state:
        st.session_state.current_backup_id = None
    # Initialize backup data storage variables
    if 'backup_data' not in st.session_state:
        st.session_state.backup_data = None
    if 'backup_metadata' not in st.session_state:
        st.session_state.backup_metadata = None

def er_login(username, password):
    """Simple login function"""
    try:
        er = EarthRangerIO(
            server=st.session_state.server_url,
            username=username,
            password=password
        )
        # Try a simple call to check credentials
        er.get_subjects(limit=1)
        return True
    except Exception:
        return False

def authenticate_earthranger():
    """Handle EarthRanger authentication using ecoscope"""
    if not ECOSCOPE_AVAILABLE:
        st.error("❌ Ecoscope package is required but not available. Please install ecoscope.")
        return
        
    st.title("🔐 Login to ER Backup Tool - High Performance")
    st.info("**Server:** https://twiga.pamdas.org")
    
    st.subheader("👤 Username/Password Authentication")
    username = st.text_input("EarthRanger Username")
    password = st.text_input("EarthRanger Password", type="password")
    
    if st.button("Login"):
        if er_login(username, password):
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.password = password
            st.success("✅ Login successful!")
            st.rerun()
        else:
            st.error("❌ Invalid credentials. Please try again.")
    
    st.stop()

def generate_month_ranges(start_date, end_date):
    """Generate list of month ranges for incremental processing"""
    months = []
    current = start_date.replace(day=1)  # Start from first day of month
    
    while current <= end_date:
        # Calculate end of current month
        if current.month == 12:
            next_month = current.replace(year=current.year + 1, month=1)
        else:
            next_month = current.replace(month=current.month + 1)
        
        month_end = min(next_month - timedelta(days=1), end_date)
        
        months.append({
            'start': current,
            'end': month_end,
            'label': current.strftime('%Y-%m')
        })
        
        current = next_month
    
    return months

def save_backup_progress(backup_id, progress_data):
    """Save backup progress to disk"""
    progress_dir = Path("backup_progress")
    progress_dir.mkdir(exist_ok=True)
    
    progress_file = progress_dir / f"{backup_id}.json"
    with open(progress_file, 'w') as f:
        json.dump(progress_data, f, default=str)

def load_backup_progress(backup_id):
    """Load backup progress from disk"""
    progress_file = Path("backup_progress") / f"{backup_id}.json"
    if progress_file.exists():
        with open(progress_file, 'r') as f:
            return json.load(f)
    return None

def get_sources_and_deployments(username, password, server_url):
    """Get sources and deployments data using direct API calls (R-style)"""
    try:
        import requests
        
        # Get authentication token
        if 'er_io' not in st.session_state:
            from ecoscope.io.earthranger import EarthRangerIO
            st.session_state.er_io = EarthRangerIO(
                server=server_url,
                username=username,
                password=password
            )
        
        # Get authentication token safely
        auth_token = None
        
        # Get token from ecoscope-based authentication
        if hasattr(st.session_state.er_io, 'auth') and hasattr(st.session_state.er_io.auth, 'token'):
            auth_token = f"Bearer {st.session_state.er_io.auth.token}"
        elif hasattr(st.session_state.er_io, '_token'):
            auth_token = f"Bearer {st.session_state.er_io._token}"
        elif hasattr(st.session_state.er_io, 'session') and hasattr(st.session_state.er_io.session, 'headers'):
            # Extract from session headers
            auth_header = st.session_state.er_io.session.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                auth_token = auth_header
        
        if not auth_token:
            # Fallback: try to authenticate directly with requests
            st.write("🔐 Getting fresh authentication token...")
            auth_url = f"{server_url}/oauth2/token/"
            auth_data = {
                'username': username,
                'password': password,
                'grant_type': 'password',
                'client_id': 'das_web_client'
            }
            auth_response = requests.post(auth_url, data=auth_data)
            if auth_response.status_code == 200:
                token_data = auth_response.json()
                auth_token = f"Bearer {token_data['access_token']}"
            else:
                raise Exception(f"Authentication failed: {auth_response.status_code}")
        
        headers = {
            'Authorization': auth_token,
            'Content-Type': 'application/json'
        }
        
        # Get sources (like your R src query)
        st.write("📡 Getting sources data...")
        sources_url = f"{server_url}/api/v1.0/sources/?page=1&page_size=4000"
        response = requests.get(sources_url, headers=headers)
        
        if response.status_code == 200:
            sources_data = response.json()
            if 'results' in sources_data:
                sources_df = pd.DataFrame(sources_data['results'])
                # Process sources like your R code
                if not sources_df.empty:
                    sources_df = sources_df.rename(columns={
                        'id': 'sourceID',
                        'manufacturer_id': 'tagID',
                        'collar_key': 'ceresID',
                        'collar_manufacturer': 'tagManufac',
                        'collar_model': 'tagModel',
                        'created_at': 'sourceCreated'
                    })
                    sources_df['sourceCreated'] = pd.to_datetime(sources_df['sourceCreated'], errors='coerce')
                    st.success(f"✅ Got {len(sources_df):,} sources")
                else:
                    sources_df = pd.DataFrame()
            else:
                sources_df = pd.DataFrame()
        else:
            st.error(f"Failed to get sources: {response.status_code}")
            sources_df = pd.DataFrame()
        
        # Get deployments/subjectsources (like your R dep query)
        st.write("🔗 Getting deployments data...")
        deployments_url = f"{server_url}/api/v1.0/subjectsources/?page=1&page_size=4000"
        response = requests.get(deployments_url, headers=headers)
        
        if response.status_code == 200:
            deployments_data = response.json()
            
            # Check for different response structures
            raw_results = None
            if 'results' in deployments_data:
                raw_results = deployments_data['results']
            elif 'data' in deployments_data:
                # Check if data contains nested results (this is the correct structure!)
                if isinstance(deployments_data['data'], dict) and 'results' in deployments_data['data']:
                    raw_results = deployments_data['data']['results']
                elif isinstance(deployments_data['data'], list):
                    raw_results = deployments_data['data']
            
            if raw_results is not None:
                deployments_df = pd.DataFrame(raw_results)
                
                # Process deployments like your R code
                if not deployments_df.empty:
                    try:
                        deployments_df = deployments_df.rename(columns={
                            'id': 'deployID',
                            'source': 'sourceID',
                            'subject': 'subjectID'
                        })
                        
                        # Handle assigned_range like your R code
                        if 'assigned_range' in deployments_df.columns:
                            range_data = []
                            for idx, row in deployments_df.iterrows():
                                assigned_range = row.get('assigned_range', {})
                                if isinstance(assigned_range, dict):
                                    start = assigned_range.get('lower')
                                    end = assigned_range.get('upper')
                                else:
                                    start = end = None
                                range_data.append({
                                    'deployStart': pd.to_datetime(start, errors='coerce') if start else None,
                                    'deployEnd': pd.to_datetime(end, errors='coerce') if end else None
                                })
                            
                            range_df = pd.DataFrame(range_data)
                            deployments_df = pd.concat([deployments_df.reset_index(drop=True), range_df], axis=1)
                        
                        # Calculate deployment days like your R code
                        if 'deployStart' in deployments_df.columns and 'deployEnd' in deployments_df.columns:
                            deployments_df['deployDays'] = (deployments_df['deployEnd'] - deployments_df['deployStart']).dt.days
                        
                        # Handle additional comments (notes) - Enhanced for R-style processing
                        if 'additional' in deployments_df.columns:
                            notes_data = []
                            for idx, row in deployments_df.iterrows():
                                additional = row.get('additional', {})
                                if isinstance(additional, dict):
                                    notes = additional.get('comments', '')
                                    # Extract additional deployment fields
                                    collar_status = additional.get('collar_status', '')
                                    deployment_status = additional.get('deployment_status', '')
                                    deployment_type = additional.get('deployment_type', '')
                                    end_reason = additional.get('end_reason', '')
                                    mortality = additional.get('mortality', '')
                                    mortality_date = additional.get('mortality_date', '')
                                else:
                                    notes = collar_status = deployment_status = deployment_type = end_reason = mortality = mortality_date = ''
                                
                                notes_data.append({
                                    'notes': notes,
                                    'collarStatus': collar_status,
                                    'deploymentStatus': deployment_status,
                                    'deploymentType': deployment_type,
                                    'endReason': end_reason,
                                    'mortality': mortality,
                                    'mortalityDate': pd.to_datetime(mortality_date, errors='coerce') if mortality_date else None
                                })
                            
                            notes_df = pd.DataFrame(notes_data)
                            deployments_df = pd.concat([deployments_df.reset_index(drop=True), notes_df], axis=1)
                        
                        # Add more deployment metadata (like R dep processing)
                        if 'created_at' in deployments_df.columns:
                            deployments_df['deployCreated'] = pd.to_datetime(deployments_df['created_at'], errors='coerce')
                        
                        if 'updated_at' in deployments_df.columns:
                            deployments_df['deployUpdated'] = pd.to_datetime(deployments_df['updated_at'], errors='coerce')
                        
                        # Calculate deployment period status
                        current_date = pd.Timestamp.now(tz='UTC')  # Make timezone-aware
                        
                        # Ensure deployment dates are timezone-aware for comparison
                        if 'deployStart' in deployments_df.columns and 'deployEnd' in deployments_df.columns:
                            try:
                                # Convert to UTC for consistent comparison
                                deployments_df['deployStart'] = pd.to_datetime(deployments_df['deployStart'], errors='coerce', utc=True)
                                deployments_df['deployEnd'] = pd.to_datetime(deployments_df['deployEnd'], errors='coerce', utc=True)
                                
                                deployments_df['deploymentActive'] = (
                                    (deployments_df['deployStart'] <= current_date) & 
                                    ((deployments_df['deployEnd'] >= current_date) | deployments_df['deployEnd'].isna())
                                )
                            except Exception as e:
                                st.warning(f"⚠️ Could not calculate deployment active status: {str(e)}")
                                deployments_df['deploymentActive'] = False
                        
                        # Remove duplicates like your R code
                        deployments_df = deployments_df.drop_duplicates(subset=['sourceID'], keep='first')
                        st.success(f"✅ Got {len(deployments_df):,} deployments with enhanced metadata")
                        
                    except Exception as e:
                        st.error(f"❌ Error processing deployment data: {str(e)}")
                        deployments_df = pd.DataFrame()
                else:
                    st.warning("⚠️ Deployment DataFrame is empty after processing")
                    deployments_df = pd.DataFrame()
            else:
                st.warning(f"⚠️ Could not find deployment data in response. Available keys: {list(deployments_data.keys()) if isinstance(deployments_data, dict) else 'Response not a dict'}")
                deployments_df = pd.DataFrame()
        else:
            st.error(f"❌ Failed to get deployments: {response.status_code}")
            try:
                error_text = response.text[:500]  # First 500 chars of error
                st.error(f"Error details: {error_text}")
            except:
                st.error("Could not get error details")
            deployments_df = pd.DataFrame()
        
        # Try alternative deployment endpoints if no data was found
        if deployments_df.empty:
            st.write("🔄 Trying alternative deployment endpoints...")
            
            alternative_urls = [
                f"{server_url}/api/v1.0/subjectsources/",  # Without pagination
                f"{server_url}/api/v1.0/subject_sources/",  # Alternative naming
                f"{server_url}/api/v1.0/sources/subjectsources/",  # Nested endpoint
            ]
            
            for alt_url in alternative_urls:
                st.write(f"📡 Trying: {alt_url}")
                try:
                    alt_response = requests.get(alt_url, headers=headers)
                    if alt_response.status_code == 200:
                        alt_data = alt_response.json()
                        st.write(f"📊 Alternative endpoint response keys: {list(alt_data.keys()) if isinstance(alt_data, dict) else 'Not a dict'}")
                        
                        # Check different possible data structures
                        data_key = None
                        if 'results' in alt_data and alt_data['results']:
                            data_key = 'results'
                        elif 'data' in alt_data and alt_data['data']:
                            # Check if 'data' contains nested results
                            if isinstance(alt_data['data'], dict) and 'results' in alt_data['data']:
                                deployments_df = pd.DataFrame(alt_data['data']['results'])
                                st.success(f"✅ Found deployment data at {alt_url} (nested data.results)")
                                break
                            elif isinstance(alt_data['data'], list) and alt_data['data']:
                                deployments_df = pd.DataFrame(alt_data['data'])
                                st.success(f"✅ Found deployment data at {alt_url} (data list)")
                                break
                            else:
                                data_key = 'data'
                        elif isinstance(alt_data, list) and alt_data:
                            deployments_df = pd.DataFrame(alt_data)
                            st.success(f"✅ Found deployment data at {alt_url} (direct list)")
                            break
                        
                        if data_key and alt_data[data_key]:
                            deployments_df = pd.DataFrame(alt_data[data_key])
                            st.success(f"✅ Found deployment data at {alt_url} (key: {data_key})")
                            break
                    else:
                        st.write(f"❌ {alt_url} returned {alt_response.status_code}")
                except Exception as e:
                    st.write(f"❌ Error with {alt_url}: {str(e)}")
            
            if not deployments_df.empty:
                st.write(f"📊 Alternative endpoint found {len(deployments_df):,} deployment records")
                st.write(f"📊 Deployment DataFrame columns: {list(deployments_df.columns)}")
                
                # Process the alternatively-sourced deployment data
                if 'id' in deployments_df.columns:
                    deployments_df = deployments_df.rename(columns={
                        'id': 'deployID',
                        'source': 'sourceID',
                        'subject': 'subjectID'
                    })
                    
                    # Add the same processing as the main deployment logic
                    # Handle assigned_range like your R code
                    if 'assigned_range' in deployments_df.columns:
                        range_data = []
                        for idx, row in deployments_df.iterrows():
                            assigned_range = row.get('assigned_range', {})
                            if isinstance(assigned_range, dict):
                                start = assigned_range.get('lower')
                                end = assigned_range.get('upper')
                            else:
                                start = end = None
                            range_data.append({
                                'deployStart': pd.to_datetime(start, errors='coerce') if start else None,
                                'deployEnd': pd.to_datetime(end, errors='coerce') if end else None
                            })
                        
                        range_df = pd.DataFrame(range_data)
                        deployments_df = pd.concat([deployments_df.reset_index(drop=True), range_df], axis=1)
                    
                    # Calculate deployment days
                    if 'deployStart' in deployments_df.columns and 'deployEnd' in deployments_df.columns:
                        deployments_df['deployDays'] = (deployments_df['deployEnd'] - deployments_df['deployStart']).dt.days
                    
                    st.info("✅ Processed alternative deployment data with full metadata")
        
        # Final fallback: try using ecoscope directly
        if deployments_df.empty:
            st.write("🔄 Final fallback: Using ecoscope to get deployment data...")
            try:
                if 'er_io' in st.session_state:
                    ecoscope_deployments = st.session_state.er_io.get_subjectsources()
                    if not ecoscope_deployments.empty:
                        deployments_df = ecoscope_deployments.copy()
                        st.success(f"✅ Got {len(deployments_df):,} deployments via ecoscope")
                    else:
                        st.warning("⚠️ Ecoscope also returned no deployment data")
                else:
                    st.warning("⚠️ No ecoscope connection available for fallback")
            except Exception as e:
                st.error(f"❌ Ecoscope fallback failed: {str(e)}")
        
        # Get subject groups (like your R grp query)
        st.write("🏷️ Getting subject groups data...")
        groups_url = f"{server_url}/api/v1.0/subjectgroups/?include_hidden=TRUE&include_inactive=TRUE&flat=flat"
        response = requests.get(groups_url, headers=headers)
        
        if response.status_code == 200:
            groups_data = response.json()
            if 'data' in groups_data:
                groups_df = pd.DataFrame(groups_data['data'])
                # Process groups like your R code
                if not groups_df.empty:
                    # Unnest subjects (like R unnest)
                    group_records = []
                    for idx, row in groups_df.iterrows():
                        group_id = row.get('id')
                        group_name = row.get('name', '')
                        subjects = row.get('subjects', [])
                        
                        # Handle empty subjects
                        if not subjects:
                            subjects = [{}]  # Keep empty to maintain group record
                        
                        for subject in subjects:
                            record = {
                                'groupID': group_id,
                                'groupName': group_name,
                                'subjectID': subject.get('id'),
                                'subjName': subject.get('name'),
                                'subjectType': subject.get('subject_subtype'),
                                'subjectSpecies': subject.get('common_name'),
                                'subjectSex': subject.get('sex')
                            }
                            group_records.append(record)
                    
                    if group_records:
                        groups_processed_df = pd.DataFrame(group_records)
                        
                        # Parse group names like R separate() function
                        name_parts = groups_processed_df['groupName'].str.split('_', expand=True, n=2)
                        if name_parts.shape[1] >= 3:
                            groups_processed_df['obsCountry'] = name_parts[0]
                            groups_processed_df['obsRegion'] = name_parts[1] 
                            groups_processed_df['obsSpecies'] = name_parts[2]
                        elif name_parts.shape[1] >= 2:
                            groups_processed_df['obsCountry'] = name_parts[0]
                            groups_processed_df['obsRegion'] = name_parts[1]
                            groups_processed_df['obsSpecies'] = None
                        elif name_parts.shape[1] >= 1:
                            groups_processed_df['obsCountry'] = name_parts[0]
                            groups_processed_df['obsRegion'] = None
                            groups_processed_df['obsSpecies'] = None
                        else:
                            groups_processed_df['obsCountry'] = None
                            groups_processed_df['obsRegion'] = None
                            groups_processed_df['obsSpecies'] = None
                        
                        # Filter out unwanted groups like your R code
                        exclude_countries = ['AF', 'TwigaTracker', 'WildScapeVet', 'Donor', 'Movebank', 'White']
                        exclude_group_id = 'bbe1967b-6a46-4a58-aca1-5e3f791933dd'
                        
                        groups_processed_df = groups_processed_df[
                            (~groups_processed_df['obsCountry'].isin(exclude_countries)) &
                            (groups_processed_df['groupID'] != exclude_group_id)
                        ]
                        
                        st.success(f"✅ Got {len(groups_processed_df):,} group-subject relationships")
                        groups_df = groups_processed_df
                    else:
                        groups_df = pd.DataFrame()
                else:
                    groups_df = pd.DataFrame()
            else:
                groups_df = pd.DataFrame()
        else:
            st.error(f"Failed to get groups: {response.status_code}")
            groups_df = pd.DataFrame()
        
        return sources_df, deployments_df, groups_df
        
    except Exception as e:
        st.error(f"Error getting sources/deployments/groups: {str(e)}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def process_deployment_notes(df):
    """Process deployment notes to extract tag placement info (like your R code)"""
    try:
        # Check for both 'notes' and 'depNotes' columns
        notes_column = None
        if 'depNotes' in df.columns:
            notes_column = 'depNotes'
        elif 'notes' in df.columns:
            notes_column = 'notes'
        else:
            return df
        
        st.write("🏷️ Processing deployment notes for tag placement details...")
        
        # Split notes by pipe character like your R separate() function
        note_columns = ['note1', 'note2', 'note3', 'note4', 'note5', 'note6']
        notes_split = df[notes_column].str.split('|', expand=True, n=5)
        notes_split.columns = note_columns[:notes_split.shape[1]]
        
        # Fill missing columns
        for col in note_columns:
            if col not in notes_split.columns:
                notes_split[col] = ''
        
        df = pd.concat([df.reset_index(drop=True), notes_split], axis=1)
        
        # Parse key-value pairs from the pipe-separated notes
        def parse_note_field(row, field_name):
            """Extract value for a specific field from the notes"""
            if notes_column in row:
                note_text = str(row[notes_column])
                # Split by | and look for field_name;
                parts = note_text.split('|')
                for part in parts:
                    part = part.strip()
                    if part.lower().startswith(field_name.lower() + ';'):
                        # Extract value after the semicolon
                        value = part.split(';', 1)[1].strip() if ';' in part else ''
                        return value
            return None
        
        # Extract Tag information
        def extract_tag_place(row):
            tag_value = parse_note_field(row, 'Tag')
            if tag_value:
                tag_value_lower = tag_value.lower()
                # Look for placement keywords
                placement_conditions = ['ear', 'ossicone', 'tail', 'neck', 'ankle', 'head', 'collar']
                for placement in placement_conditions:
                    if placement in tag_value_lower:
                        return placement
            return None
        
        df['tagPlace'] = df.apply(extract_tag_place, axis=1)
        
        # Extract AltName
        df['altName'] = df.apply(lambda row: parse_note_field(row, 'AltName'), axis=1)
        
        # Extract Age and convert to subAge categories
        def extract_age(row):
            age_value = parse_note_field(row, 'Age')
            if age_value:
                age_lower = age_value.lower()
                if 'subadult' in age_lower:
                    return 'subadult'
                elif any(word in age_lower for word in ['adult', 'year']):
                    return 'adult'
            return 'adult'  # default
        
        df['subAge'] = df.apply(extract_age, axis=1)
        
        # Extract ear placement details from Tag and Comments fields
        def extract_ear_inside_outside(row):
            # Check Tag field first
            tag_value = parse_note_field(row, 'Tag')
            if tag_value and ('inside' in tag_value.lower() or 'outside' in tag_value.lower()):
                if 'inside' in tag_value.lower():
                    return 'inside'
                elif 'outside' in tag_value.lower():
                    return 'outside'
            
            # Check Comments field
            comments_value = parse_note_field(row, 'Comments')
            if comments_value:
                comments_lower = comments_value.lower()
                if 'inside' in comments_lower:
                    return 'inside'
                elif 'outside' in comments_lower:
                    return 'outside'
            return None
        
        def extract_ear_left_right(row):
            # Check Tag field first
            tag_value = parse_note_field(row, 'Tag')
            if tag_value and ('left' in tag_value.lower() or 'right' in tag_value.lower()):
                if 'right' in tag_value.lower():
                    return 'right'
                elif 'left' in tag_value.lower():
                    return 'left'
            
            # Check Comments field for "right [code], left [code]" pattern
            comments_value = parse_note_field(row, 'Comments')
            if comments_value:
                comments_lower = comments_value.lower()
                # Look for patterns like "right 0120D3AE, left 0120BAE4"
                if 'right' in comments_lower and 'left' in comments_lower:
                    return 'both'
                elif 'right' in comments_lower:
                    return 'right'
                elif 'left' in comments_lower:
                    return 'left'
            return None
        
        df['tagPlaceEar1'] = df.apply(extract_ear_inside_outside, axis=1)
        df['tagPlaceEar2'] = df.apply(extract_ear_left_right, axis=1)
        
        # Extract deployment end cause from Unit field
        def extract_end_cause(row):
            unit_value = parse_note_field(row, 'Unit')
            if unit_value:
                return unit_value.strip()  # Return the full Unit value
            return 'unknown'
        
        df['depEndCause'] = df.apply(extract_end_cause, axis=1)
        
        # Extract Comments field as separate column
        df['depComments'] = df.apply(lambda row: parse_note_field(row, 'Comments'), axis=1)
        
        # Extract additional species information
        def extract_species_additional(row):
            for col in note_columns:
                note_text = str(row.get(col, ''))
                if 'Species;' in note_text:
                    return note_text
            return None
        
        df['species_additional'] = df.apply(extract_species_additional, axis=1)
        
        # Clean up note columns
        df = df.drop(columns=note_columns, errors='ignore')
        
        st.success("✅ Processed deployment notes for tag placement details")
        return df
        
    except Exception as e:
        st.warning(f"⚠️ Error processing deployment notes: {str(e)}")
        return df

def create_master_file(obs_df, sources_df, deployments_df, subjects_df, groups_df, filter_giraffes_only=True):
    """Create master file with all joins like your R code lines 1-140"""
    try:
        st.write("🔗 Creating master file with all data joins...")
        
        # Start with observations (like your R data1/data0)
        master_df = obs_df.copy()
        
        # Join with sources (like your R left_join(src1))
        if not sources_df.empty and 'source_id' in master_df.columns:
            master_df = master_df.merge(sources_df, left_on='source_id', right_on='sourceID', how='left')
            st.info("✅ Joined sources data")
        
        # Join with deployments (like your R left_join(dep1))
        if not deployments_df.empty and 'source_id' in master_df.columns:
            # Ensure we have the key columns for joining
            if 'sourceID' in deployments_df.columns:
                master_df = master_df.merge(deployments_df, left_on='source_id', right_on='sourceID', how='left', suffixes=('', '_dep'))
                
                # Check how many records got deployment data
                deployment_data_filled = master_df['deployID'].notna().sum() if 'deployID' in master_df.columns else 0
                st.info(f"✅ Joined deployments data: {deployment_data_filled:,} records have deployment info")
            else:
                st.warning("⚠️ No 'sourceID' column found in deployments data for joining")
        else:
            if deployments_df.empty:
                st.warning("⚠️ No deployment data available")
            elif 'source_id' not in master_df.columns:
                st.warning("⚠️ No 'source_id' column in observations for deployment join")
        
        # Join with subjects (like your R left_join(sub1))
        if not subjects_df.empty and 'subject_id' in master_df.columns:
            # Prepare subjects data
            subjects_clean = subjects_df.rename(columns={
                'id': 'subjectID',
                'name': 'subjectName',
                'subject_subtype': 'subjectType',
                'common_name': 'subjectSpecies',
                'sex': 'subjectSex',
                'is_active': 'subjectActive',
                'last_position_date': 'subjectLastDate',
                'region': 'obsLandscape'
            })
            
            master_df = master_df.merge(subjects_clean, left_on='subject_id', right_on='subjectID', how='left', suffixes=('', '_sub'))
            st.info("✅ Joined subjects data")
        
        # Join with groups (like your R left_join(grp1))
        if not groups_df.empty and 'subject_id' in master_df.columns:
            # Group data includes: groupID, groupName, subjectID, obsCountry, obsRegion, obsSpecies
            master_df = master_df.merge(groups_df, left_on='subject_id', right_on='subjectID', how='left', suffixes=('', '_grp'))
            st.info("✅ Joined groups data")
        
        # Filter records within deployment period (like your R filter)
        if 'recorded_at' in master_df.columns and 'deployStart' in master_df.columns and 'deployEnd' in master_df.columns:
            master_df['recorded_at'] = pd.to_datetime(master_df['recorded_at'], errors='coerce')
            initial_count = len(master_df)
            
            # Filter within deployment range
            mask = (
                (master_df['recorded_at'] >= master_df['deployStart']) & 
                (master_df['recorded_at'] <= master_df['deployEnd'])
            ) | (
                master_df['deployStart'].isna() | master_df['deployEnd'].isna()
            )
            
            master_df = master_df[mask]
            filtered_count = len(master_df)
            st.info(f"🔍 Filtered to deployment periods: {initial_count:,} → {filtered_count:,} records")
        
        # Remove duplicates (like your R distinct)
        if all(col in master_df.columns for col in ['source_id', 'recorded_at', 'longitude', 'latitude']):
            initial_count = len(master_df)
            master_df = master_df.drop_duplicates(subset=['source_id', 'recorded_at', 'longitude', 'latitude'], keep='first')
            final_count = len(master_df)
            st.info(f"🧹 Removed duplicates: {initial_count:,} → {final_count:,} records")
        
        # Process deployment notes for tag placement
        master_df = process_deployment_notes(master_df)
        
        # Clean up and standardize column names (like your R data3 section)
        master_df = standardize_master_columns(master_df, filter_giraffes_only)
        
        st.success(f"✅ Master file created with {len(master_df):,} records")
        return master_df
        
    except Exception as e:
        st.error(f"Error creating master file: {str(e)}")
        return obs_df

def standardize_master_columns(df, filter_giraffes_only=True):
    """Standardize column names and clean data like your R data3 section"""
    try:
        st.write("🔧 Standardizing column names and cleaning data...")
        
        # 0. Check for and handle duplicate columns first
        duplicate_cols = df.columns[df.columns.duplicated()].tolist()
        if duplicate_cols:
            st.warning(f"⚠️ Found duplicate columns: {duplicate_cols}")
            # Remove duplicate columns by keeping only the first occurrence
            df = df.loc[:, ~df.columns.duplicated()]
            st.info(f"✅ Removed duplicate columns, now have {len(df.columns)} unique columns")
        
        # 1. Remove specific unwanted columns
        columns_to_remove = [
            'created_at', 'exclusion_flags', 'accuracy', 'locationAccuracy',
            'activity1', 'activity2', 'activity3', 'activity4', 'charge_status',
            'orientation', 'activity', 'activity_label', 'location_accuracy',
            'location_accuracy_label', 'GPS activity count', 'heading',
            'gps_hdop', 'event_id', 'sourceCreated', 'subjectLastDate',
            'location', 'device_status_properties',
            'additional', 'content_type', 'created_at_sub', 'device_status_properties_sub',
            'hex', 'image_url', 'last_position', 'last_position_status', 'source_id',
            'subjectActive', 'subjectName', 'subjectType', 'tracks_available', 'user', 'updated_at',
            # New columns to remove as requested
            'additional_sub', 'sourceID', 'subjectID_sub'
        ]
        
        for col in columns_to_remove:
            if col in df.columns:
                df = df.drop(columns=[col])
                
        # 2. Handle assigned_range expansion - only if we don't have deployment dates already
        if 'assigned_range' in df.columns:
            # Check if we already have deployment dates from actual deployment data
            has_deploy_dates = 'deployStart' in df.columns and 'deployEnd' in df.columns
            
            if has_deploy_dates:
                pass  # Skip assigned_range expansion
            else:
                # Expand assigned_range only if we don't have deployment dates
                range_data = []
                for idx, row in df.iterrows():
                    assigned_range = row.get('assigned_range', {})
                    if isinstance(assigned_range, dict):
                        start = assigned_range.get('lower')
                        end = assigned_range.get('upper')
                    else:
                        start = end = None
                    range_data.append({
                        'deployStart': pd.to_datetime(start, errors='coerce') if start else None,
                        'deployEnd': pd.to_datetime(end, errors='coerce') if end else None
                    })
                
                range_df = pd.DataFrame(range_data)
                df = pd.concat([df.reset_index(drop=True), range_df], axis=1)
            
            # Always remove the original assigned_range column
            df = df.drop(columns=['assigned_range'], errors='ignore')
        
        # 3. Skip further processing until after column renaming
        
        # 4. Skip giraffe filtering for now - will do it after column renaming
        
        # Note: Ranger filtering is now handled in the giraffe filtering section
        
        # Consolidate battery voltage columns (like your R coalesce)
        battery_voltage_cols = ['battery_volts', 'batt', 'voltage', 'tag_voltage']
        battery_percentage_cols = ['battery_percentage', 'battery_percent', 'bat_soc']
        
        # Get available battery voltage columns
        available_voltage_cols = [col for col in battery_voltage_cols if col in df.columns]
        if available_voltage_cols:
            # Create consolidated battery voltage column using the first available column
            df['srcBatt_v'] = df[available_voltage_cols[0]]
            # Remove original battery voltage columns except the first one we used
            for col in available_voltage_cols:
                if col in df.columns:
                    df = df.drop(columns=[col])
        
        # Get available battery percentage columns  
        available_percentage_cols = [col for col in battery_percentage_cols if col in df.columns]
        if available_percentage_cols:
            # Create consolidated battery percentage column using the first available column
            df['srcBatt_p'] = df[available_percentage_cols[0]]
            # Remove original battery percentage columns
            for col in available_percentage_cols:
                if col in df.columns:
                    df = df.drop(columns=[col])
        
        # Rename columns to match your R naming convention
        column_mapping = {
            'id': 'obsID',
            'recorded_at': 'obsDatetime',
            'country': 'obsCountry',
            'source': 'srcID',
            'deployment_id': 'movebank_depID',
            'tag_local_identifier': 'tagID',
            'tag_id': 'movebank_tagID',
            'latitude': 'obsLat',
            'longitude': 'obsLon',
            'url': 'obsUrl',  # renamed from url
            'subject_id': 'subID',
            'subject_name': 'subName',
            'subject_type': 'subType',
            'subjectType': 'subGenus',
            'species': 'subSpecies',
            'subject_sex': 'subSex',
            'subject_active': 'subActive',
            'case_temperature_c': 'srcTemp_case_c',
            'device_temperature_c': 'srcTemp_unit_c',
            'temperature': 'srcTemp',
            'tagPlace': 'srcPlace',  # renamed from tagPlace
            'tagPlaceEar1': 'srcPlaceEar1',  # renamed 
            'tagPlaceEar2': 'srcPlaceEar2',  # renamed
            'altName': 'subName2',  # renamed from altName
            # Deployment-specific columns (matching R conventions) - removing unneeded ones
            'deployID': 'depID',
            'deployStart': 'depStart',
            'deployEnd': 'depEnd',
            'deploymentActive': 'depActive',
            'deployCreated': 'depCreated',
            'deployUpdated': 'depUpdated'
            # Removed: depDays, depNotes, depCollarStatus, depStatus, depType, depMortality, depMortalityDate
        }
        
        # Apply column renaming
        for old_name, new_name in column_mapping.items():
            if old_name in df.columns:
                df = df.rename(columns={old_name: new_name})
        
        # Remove duplicate/unneeded columns
        duplicate_cols_to_remove = [
            'obsSpecies', 'subject_type_sub', 'subjectSpecies', 'subjectID_grp', 
            'subjName', 'subjectType_grp', 'subjectSpecies_grp', 'subjectSex_grp', 
            'subjectID', 'subjectSex', 'depDays', 'depNotes', 'depCollarStatus', 
            'depStatus', 'depType', 'depMortality', 'depMortalityDate'
        ]
        
        existing_duplicates = [col for col in duplicate_cols_to_remove if col in df.columns]
        if existing_duplicates:
            df = df.drop(columns=existing_duplicates)
        
        # Fix deployment end reason - use depEndCause over depEndReason if available
        if 'depEndCause' in df.columns and 'depEndReason' in df.columns:
            # Use depEndCause values where available, otherwise use depEndReason
            df['depEndReason'] = df['depEndCause'].fillna(df['depEndReason'])
            df = df.drop(columns=['depEndCause'])
        elif 'depEndCause' in df.columns:
            # Rename depEndCause to depEndReason
            df = df.rename(columns={'depEndCause': 'depEndReason'})
        
        # Fix obsCountry column AFTER all other processing - extract from groupName
        if 'groupName' in df.columns:
            # Always recreate obsCountry from groupName to ensure it's correct (e.g., NAM_Mudumu_giraffe → NAM)
            df['obsCountry'] = df['groupName'].str.split('_').str[0]
        
        # Ensure proper data types
        datetime_cols = ['obsDatetime', 'depStart', 'depEnd', 'depCreated', 'depUpdated']
        for col in datetime_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Convert obsDatetime to UTC and rename for clarity
        if 'obsDatetime' in df.columns:
            # Convert to UTC if not already
            if df['obsDatetime'].dt.tz is None:
                # If no timezone info, assume UTC
                df['obsDatetime'] = df['obsDatetime'].dt.tz_localize('UTC')
            else:
                # Convert to UTC if timezone-aware
                df['obsDatetime'] = df['obsDatetime'].dt.tz_convert('UTC')
            
            # Rename to indicate UTC timezone
            df = df.rename(columns={'obsDatetime': 'obsDatetime_UTC'})
        
        # Filter to giraffes only (if requested) - after column renaming
        if filter_giraffes_only:
            # Try multiple columns that might contain the animal type
            filtered = False
            
            # First try subType column
            if 'subType' in df.columns and not df['subType'].isna().all():
                initial_count = len(df)
                
                # Filter out rangers first
                df = df[~df['subType'].isin(['ranger', 'er_mobile'])]
                
                # Then filter for giraffes
                giraffe_mask = (
                    (df['subType'].str.lower().str.contains('giraffe', na=False)) |
                    (df['subType'] == 'giraffe') |
                    (df['subType'].str.lower() == 'giraffe')
                )
                df = df[giraffe_mask]
                filtered_count = len(df)
                st.info(f"🦒 Filtered by subType: {initial_count:,} → {filtered_count:,} records")
                filtered = True
                
            # If subType didn't work, try subSpecies
            elif 'subSpecies' in df.columns and not df['subSpecies'].isna().all():
                initial_count = len(df)
                
                # All subspecies with these patterns are giraffes
                giraffe_subspecies_patterns = ['Southern_', 'Northern_', 'Masai_', 'Rothschild', 'Reticulated', 'Angolan', 'Kordofan', 'Nubian', 'SouthAfrican']
                giraffe_mask = df['subSpecies'].str.contains('|'.join(giraffe_subspecies_patterns), na=False, case=False)
                
                # Also filter out rangers
                ranger_mask = ~df['subSpecies'].str.contains('ranger|er_mobile', na=False, case=False)
                df = df[giraffe_mask & ranger_mask]
                
                filtered_count = len(df)
                st.info(f"🦒 Filtered by subSpecies: {initial_count:,} → {filtered_count:,} records")
                filtered = True
                
            if not filtered:
                st.warning("⚠️ No suitable column found for giraffe filtering. Keeping all records.")
        else:
            st.info("🐾 Keeping all animal types (giraffe filtering disabled)")
        
        # 5. Order columns in specific custom order
        
        # Check for any remaining duplicate columns before ordering
        if df.columns.duplicated().any():
            st.warning("⚠️ Found duplicate columns after processing, removing them...")
            df = df.loc[:, ~df.columns.duplicated()]
        
        current_columns = list(df.columns)
        
        # Define the specific column order you want
        desired_order = [
            'obsID', 'obsDatetime_UTC', 'obsLat', 'obsLon', 'obsRegion', 'obsSpecies', 
            'groupID', 'groupName', 'obsCountry', 
            'srcID', 'srcPlace', 'srcPlaceEar1', 'srcPlaceEar2', 'srcTemp_unit_c', 'srcBatt_v', 'srcBatt_p',
            'subID', 'subName', 'subName2', 'subType', 'subSpecies', 'subSex', 'subActive', 'subAge',
            'depID', 'depStart', 'depEnd', 'depCreated', 'depUpdated', 'depActive', 'depEndReason',
            'speed', 'srcTemp_case_c', 'srcTemp', 'movebank_depID', 'tagID', 'movebank_tagID', 
            'location_dep', 'obsLandscape', 'obsUrl', 'depComments', 'species_additional'
        ]
        
        # Get columns that exist in the dataframe from the desired order
        existing_ordered_cols = [col for col in desired_order if col in current_columns]
        
        # Get any remaining columns not in the desired order
        remaining_cols = [col for col in current_columns if col not in desired_order]
        
        # Final column order: desired order first, then any remaining columns
        final_order = existing_ordered_cols + remaining_cols
        
        # Reorder DataFrame
        df = df[final_order]
        
        st.success("✅ Standardized column names and cleaned data")
        return df
        
    except Exception as e:
        st.warning(f"⚠️ Error standardizing columns: {str(e)}")
        return df

def get_all_subjects(username, password, server_url):
    """Get all subjects data using direct API calls"""
    try:
        import requests
        
        # Get authentication token
        if 'er_io' not in st.session_state:
            from ecoscope.io.earthranger import EarthRangerIO
            st.session_state.er_io = EarthRangerIO(
                server=server_url,
                username=username,
                password=password
            )
        
        # Get authentication token safely
        auth_token = None
        
        # Get token from ecoscope-based authentication
        if hasattr(st.session_state.er_io, 'auth') and hasattr(st.session_state.er_io.auth, 'token'):
            auth_token = f"Bearer {st.session_state.er_io.auth.token}"
        elif hasattr(st.session_state.er_io, '_token'):
            auth_token = f"Bearer {st.session_state.er_io._token}"
        elif hasattr(st.session_state.er_io, 'session') and hasattr(st.session_state.er_io.session, 'headers'):
            # Extract from session headers
            auth_header = st.session_state.er_io.session.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                auth_token = auth_header
        
        if not auth_token:
            # Fallback: try to authenticate directly with requests
            st.write("🔐 Getting fresh authentication token...")
            auth_url = f"{server_url}/oauth2/token/"
            auth_data = {
                'username': username,
                'password': password,
                'grant_type': 'password',
                'client_id': 'das_web_client'
            }
            auth_response = requests.post(auth_url, data=auth_data)
            if auth_response.status_code == 200:
                token_data = auth_response.json()
                auth_token = f"Bearer {token_data['access_token']}"
            else:
                raise Exception(f"Authentication failed: {auth_response.status_code}")
        
        headers = {
            'Authorization': auth_token,
            'Content-Type': 'application/json'
        }
        
        # Get subjects
        st.write("👥 Getting subjects data...")
        subjects_url = f"{server_url}/api/v1.0/subjects/?page=1&page_size=4000&include_inactive=true"
        response = requests.get(subjects_url, headers=headers)
        
        if response.status_code == 200:
            subjects_data = response.json()
            if 'results' in subjects_data:
                subjects_df = pd.DataFrame(subjects_data['results'])
                if not subjects_df.empty:
                    st.success(f"✅ Got {len(subjects_df):,} subjects")
                    return subjects_df
                else:
                    return pd.DataFrame()
            else:
                return pd.DataFrame()
        else:
            st.error(f"Failed to get subjects: {response.status_code}")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Error getting subjects: {str(e)}")
        return pd.DataFrame()

def get_subject_groups(username, password, server_url):
    """Get subject groups data by processing subjects"""
    try:
        # Use cached subjects data or get fresh
        if 'subjects_df' in st.session_state:
            subjects_df = st.session_state.subjects_df
        else:
            subjects_df = get_all_subjects(username, password, server_url)
        
        if subjects_df.empty:
            return pd.DataFrame()
        
        st.write("🏷️ Processing subject groups...")
        
        # Process groups data like your R code
        groups_data = []
        for _, subject in subjects_df.iterrows():
            subject_id = subject.get('id')
            
            if 'groups' in subject and subject['groups']:
                groups = subject['groups'] if isinstance(subject['groups'], list) else [subject['groups']]
                for group in groups:
                    if isinstance(group, dict):
                        group_name = group.get('name', '')
                        country, region, species = None, None, None
                        if '_' in group_name:
                            parts = group_name.split('_', 2)
                            country = parts[0] if len(parts) > 0 else None
                            region = parts[1] if len(parts) > 1 else None
                            species = parts[2] if len(parts) > 2 else None
                        
                        groups_data.append({
                            'subject_id': subject_id,
                            'group_id': group.get('id'),
                            'group_name': group_name,
                            'country': country,
                            'region': region,
                            'species': species
                        })
        
        if groups_data:
            groups_df = pd.DataFrame(groups_data)
            # Filter out unwanted groups (like your R code)
            exclude_countries = ['AF', 'TwigaTracker', 'WildScapeVet', 'Donor', 'Movebank', 'White']
            groups_df = groups_df[
                ~groups_df['country'].isin(exclude_countries)
            ]
            st.success(f"✅ Processed {len(groups_df):,} group relationships")
            return groups_df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Error getting subject groups: {str(e)}")
        return pd.DataFrame()

def backup_all_observations_r_style(username, password, server_url, start_date, end_date, include_subject_details=True, filter_giraffes_only=True):
    """Backup all observations using direct API calls (R-style approach) - MUCH FASTER"""
    try:
        import requests
        from urllib.parse import quote
        
        # Format dates for API
        start_str = start_date.strftime('%Y-%m-%dT00:00:00+0000')
        end_str = end_date.strftime('%Y-%m-%dT23:59:59+0000')
        
        st.write(f"🚀 **Ultra-Fast R-Style Download**: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Get cached data or initialize ecoscope connection for other data
        if 'er_io' not in st.session_state:
            from ecoscope.io.earthranger import EarthRangerIO
            st.session_state.er_io = EarthRangerIO(
                server=server_url,
                username=username,
                password=password
            )
        
        er_io = st.session_state.er_io
        
        # Get subjects and groups data (cached)
        if include_subject_details and 'subjects_df' not in st.session_state:
            st.write("📥 Loading subject details (one-time fetch)...")
            st.session_state.subjects_df = er_io.get_subjects(include_inactive=True)
            
            # Process groups data like your R code
            if not st.session_state.subjects_df.empty:
                groups_data = []
                for _, subject in st.session_state.subjects_df.iterrows():
                    subject_id = subject.get('id')
                    
                    if 'groups' in subject and subject['groups']:
                        groups = subject['groups'] if isinstance(subject['groups'], list) else [subject['groups']]
                        for group in groups:
                            if isinstance(group, dict):
                                group_name = group.get('name', '')
                                country, region, species = None, None, None
                                if '_' in group_name:
                                    parts = group_name.split('_', 2)
                                    country = parts[0] if len(parts) > 0 else None
                                    region = parts[1] if len(parts) > 1 else None
                                    species = parts[2] if len(parts) > 2 else None
                                
                                groups_data.append({
                                    'subject_id': subject_id,
                                    'group_id': group.get('id'),
                                    'group_name': group_name,
                                    'country': country,
                                    'region': region,
                                    'species': species
                                })
                
                if groups_data:
                    st.session_state.groups_df = pd.DataFrame(groups_data)
                    # Filter out unwanted groups (like your R code)
                    exclude_countries = ['AF', 'TwigaTracker', 'WildScapeVet', 'Donor', 'Movebank', 'White']
                    st.session_state.groups_df = st.session_state.groups_df[
                        ~st.session_state.groups_df['country'].isin(exclude_countries)
                    ]
                else:
                    st.session_state.groups_df = pd.DataFrame()
        
        # Use direct API calls exactly like your R code - MAXIMUM SPEED!
        st.write(f"🚀 Starting ultra-fast direct API download (R-style with cursor pagination)...")
        
        try:
            # Get authentication token from ecoscope session
            # EarthRangerIO stores the token in the auth property
            if hasattr(er_io, 'auth') and hasattr(er_io.auth, 'token'):
                auth_token = f"Bearer {er_io.auth.token}"
            elif hasattr(er_io, '_token'):
                auth_token = f"Bearer {er_io._token}"
            elif hasattr(er_io, 'session') and hasattr(er_io.session, 'headers'):
                # Extract from session headers
                auth_header = er_io.session.headers.get('Authorization', '')
                if auth_header.startswith('Bearer '):
                    auth_token = auth_header
                else:
                    raise Exception("Could not find authentication token in EarthRangerIO session")
            else:
                # Fallback: try to authenticate directly with requests
                st.write("🔐 Getting fresh authentication token...")
                auth_url = f"{server_url}/oauth2/token/"
                auth_data = {
                    'username': username,
                    'password': password,
                    'grant_type': 'password',
                    'client_id': 'das_web_client'
                }
                auth_response = requests.post(auth_url, data=auth_data)
                if auth_response.status_code == 200:
                    token_data = auth_response.json()
                    auth_token = f"Bearer {token_data['access_token']}"
                else:
                    raise Exception(f"Authentication failed: {auth_response.status_code}")
            
            # URL encode the dates
            since_encoded = quote(start_str, safe='')
            until_encoded = quote(end_str, safe='')
            
            # Initial API call with cursor pagination (exactly like your R code)
            base_url = f"{server_url}/api/v1.0/observations/"
            url = f"{base_url}?page_size=4000&use_cursor=true&since={since_encoded}&until={until_encoded}"
            
            headers = {
                'Authorization': auth_token,
                'Content-Type': 'application/json'
            }
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            all_data = []
            page_count = 0
            start_time = datetime.now()
            
            # Pagination loop exactly like your R code
            while url:
                response = requests.get(url, headers=headers)
                if response.status_code != 200:
                    st.error(f"API request failed with status {response.status_code}: {response.text}")
                    break
                
                data = response.json()
                
                if 'data' in data and 'results' in data['data']:
                    results = data['data']['results']
                    if results:
                        all_data.extend(results)
                        page_count += 1
                        
                        # Update progress
                        elapsed = datetime.now() - start_time
                        status_text.text(f"📄 Page {page_count} | Records: {len(all_data):,} | Time: {elapsed.total_seconds():.1f}s")
                        
                        # Estimate progress (rough)
                        if page_count <= 10:
                            progress_bar.progress(min(page_count / 10, 0.9))
                    
                    # Get next URL for pagination (like your R while loop)
                    url = data['data'].get('next')
                else:
                    break
            
            progress_bar.progress(1.0)
            
            if not all_data:
                st.info("ℹ️ No observations found for the selected date range")
                return pd.DataFrame(), 0
            
            st.success(f"🚀 Downloaded {len(all_data):,} observations in {page_count} pages using R-style direct API!")
            
            # Convert to DataFrame (like your R bind_rows)
            df = pd.DataFrame(all_data)
            
            # Handle device status properties exactly like your R code
            if 'device_status_properties' in df.columns:
                st.write("🔧 Processing device status properties (R-style)...")
                
                device_props = []
                for idx, row in df.iterrows():
                    props = row.get('device_status_properties', [])
                    prop_dict = {}
                    if isinstance(props, list):
                        for prop in props:
                            if isinstance(prop, dict):
                                label = prop.get('label', 'unknown')
                                value = prop.get('value', None)
                                units = prop.get('units', '')
                                
                                # Handle battery voltage labeling exactly like R code
                                if units == 'v':
                                    label = 'battery_volts'
                                elif label == 'battery' and units:
                                    label = units
                                
                                prop_dict[label] = value
                    device_props.append(prop_dict)
                
                # Convert to DataFrame and merge (like R pivot_wider)
                if device_props:
                    device_df = pd.DataFrame(device_props)
                    df = pd.concat([df.reset_index(drop=True), device_df], axis=1)
            
            # Handle location data (like your R unnest)
            if 'location' in df.columns:
                st.write("📍 Processing location data (R-style unnest)...")
                
                location_data = []
                for idx, row in df.iterrows():
                    location = row.get('location', {})
                    if isinstance(location, dict):
                        lat = location.get('latitude', None)
                        lon = location.get('longitude', None)
                    else:
                        lat = lon = None
                    location_data.append({'latitude': lat, 'longitude': lon})
                
                location_df = pd.DataFrame(location_data)
                df = pd.concat([df.reset_index(drop=True), location_df], axis=1)
            
            # Handle subject identification
            if 'source' in df.columns:
                st.write("🔗 Processing source/subject relationships...")
                
                # Debug: Check what the source field actually looks like
                sample_sources = df['source'].head(3).tolist()
                st.write(f"📊 Debug: Sample source field values:")
                for i, src in enumerate(sample_sources):
                    st.write(f"  Row {i}: {type(src)} = {src}")
                
                source_data = []
                for idx, row in df.iterrows():
                    source = row.get('source', {})
                    
                    # Handle different possible formats
                    if isinstance(source, dict):
                        subject_id = source.get('subject')
                        source_id = source.get('id')
                    elif isinstance(source, str):
                        # If source is just a string ID, use it as source_id and try to get subject from subjectsources
                        source_id = source
                        subject_id = None  # Will need to get from subjectsources later
                    else:
                        subject_id = source_id = None
                        
                    source_data.append({'subject_id': subject_id, 'source_id': source_id})
                
                source_df = pd.DataFrame(source_data)
                df = pd.concat([df.reset_index(drop=True), source_df], axis=1)
                
                # Check extracted IDs
                valid_subject_ids = source_df['subject_id'].notna().sum()
                valid_source_ids = source_df['source_id'].notna().sum()
                
                # If we have source IDs but no subject IDs, try to get subjects from subjectsources
                if valid_source_ids > 0 and valid_subject_ids == 0:
                    st.write("🔍 Attempting to get subject IDs from subjectsources...")
                    
                    # Get subjectsources data to map source_id to subject_id
                    if 'subjectsources_df' not in st.session_state:
                        if 'er_io' not in st.session_state:
                            from ecoscope.io.earthranger import EarthRangerIO
                            st.session_state.er_io = EarthRangerIO(
                                server=server_url,
                                username=username,
                                password=password
                            )
                        st.session_state.subjectsources_df = st.session_state.er_io.get_subjectsources()
                    
                    subjectsources = st.session_state.subjectsources_df
                    if not subjectsources.empty:
                        # Create mapping from source_id to subject_id
                        source_to_subject = dict(zip(subjectsources['source'], subjectsources['subject']))
                        
                        # Update subject_id based on source_id
                        df['subject_id'] = df['source_id'].map(source_to_subject).fillna(df['subject_id'])
                        
                        updated_subject_ids = df['subject_id'].notna().sum()
                    else:
                        st.warning("⚠️ No subjectsources data available")
            
            # Join with subject details (like your R left_join)
            if include_subject_details and 'subjects_df' in st.session_state and 'subject_id' in df.columns:
                st.write("👥 Joining subject details (R-style left_join)...")
                
                subject_cols = ['id', 'name', 'subject_subtype', 'common_name', 'sex', 'is_active']
                available_subject_cols = [col for col in subject_cols if col in st.session_state.subjects_df.columns]
                
                if available_subject_cols:
                    # Check subject IDs before join
                    obs_subject_ids = set(df['subject_id'].dropna().unique())
                    subj_ids = set(st.session_state.subjects_df['id'].unique())
                    matching_ids = obs_subject_ids.intersection(subj_ids)
                    
                    subjects_renamed = st.session_state.subjects_df[available_subject_cols].rename(columns={
                        'id': 'subject_id',
                        'name': 'subject_name',
                        'subject_subtype': 'subject_type',
                        'common_name': 'species',
                        'sex': 'subject_sex',
                        'is_active': 'subject_active'
                    })
                    
                    # Perform the join
                    before_join = len(df)
                    df = df.merge(subjects_renamed, on='subject_id', how='left')
                    after_join = len(df)
                    
                    # Check if subject data was actually joined
                    subject_data_filled = df['subject_name'].notna().sum()
                    st.info(f"✅ Joined subject details: {before_join} → {after_join} records, {subject_data_filled:,} with subject data")
                else:
                    st.warning(f"⚠️ No valid subject columns found. Available: {list(st.session_state.subjects_df.columns)}")
                
                # Join with groups data
                if 'groups_df' in st.session_state and not st.session_state.groups_df.empty:
                    df = df.merge(st.session_state.groups_df, on='subject_id', how='left')
                    st.info("✅ Joined group details")
            else:
                if not include_subject_details:
                    st.info("ℹ️ Subject details not requested")
                elif 'subjects_df' not in st.session_state:
                    st.warning("⚠️ No subjects data in cache")
                elif 'subject_id' not in df.columns:
                    st.warning("⚠️ No subject_id column in observations")
                    st.info(f"Available columns: {list(df.columns)}")
            
            # Ensure proper datetime columns
            datetime_cols = ['recorded_at', 'created_at', 'time']
            for col in datetime_cols:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
            
            # Sort by recorded_at
            if 'recorded_at' in df.columns:
                df = df.sort_values('recorded_at')
            
            total_time = datetime.now() - start_time
            st.success(f"✅ **R-Style Ultra-Fast Download Complete!**")
            st.success(f"📊 {len(df):,} observations processed in {total_time.total_seconds():.1f} seconds")
            
            # Create master file with comprehensive joins (like your R ER_dataPull.R lines 1-140)
            st.write("🔗 Creating comprehensive master file with all data joins...")
            
            # Get additional data for master file creation
            sources_df, deployments_df, groups_df = get_sources_and_deployments(username, password, server_url)
            
            # Use cached subjects data (groups are now fetched above)
            subjects_df = st.session_state.get('subjects_df', pd.DataFrame())
            
            # Create master file with all joins
            master_df = create_master_file(df, sources_df, deployments_df, subjects_df, groups_df, filter_giraffes_only)
            
            # Return only the master file, not the raw observations
            return master_df, len(df)
            
        except Exception as e:
            st.error(f"Error in R-style download: {str(e)}")
            return pd.DataFrame(), 0
            
    except Exception as e:
        st.error(f"Error in ultra-fast backup: {str(e)}")
        return pd.DataFrame(), 0

def backup_month_subjectsource_observations(username, password, server_url, start_date, end_date, month_label, include_subject_details=True):
    """Backup subjectsource observations for a single month using direct API calls"""
    try:
        import requests
        from urllib.parse import quote
        
        # Format dates for API
        start_str = start_date.strftime('%Y-%m-%dT00:00:00+0000')
        end_str = end_date.strftime('%Y-%m-%dT23:59:59+0000')
        
        st.write(f"📅 Processing {month_label}: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Get cached data or initialize ecoscope connection for other data
        if 'er_io' not in st.session_state:
            from ecoscope.io.earthranger import EarthRangerIO
            st.session_state.er_io = EarthRangerIO(
                server=server_url,
                username=username,
                password=password
            )
        
        er_io = st.session_state.er_io
        
        # Get subjectsources (cached at session level) 
        if 'subjectsources_df' not in st.session_state:
            st.write("🔍 Getting subjectsources (one-time fetch)...")
            st.session_state.subjectsources_df = er_io.get_subjectsources()
        
        subjectsources_df = st.session_state.subjectsources_df
        
        if subjectsources_df.empty:
            return pd.DataFrame(), 0
        
        # Get subjects data (cached at session level)
        if include_subject_details and 'subjects_df' not in st.session_state:
            st.write("📥 Loading subject details (one-time fetch)...")
            st.session_state.subjects_df = er_io.get_subjects(include_inactive=True)
            
            # Process groups data
            if not st.session_state.subjects_df.empty:
                groups_data = []
                for _, subject in st.session_state.subjects_df.iterrows():
                    subject_id = subject.get('id')
                    
                    if 'groups' in subject and subject['groups']:
                        groups = subject['groups'] if isinstance(subject['groups'], list) else [subject['groups']]
                        for group in groups:
                            if isinstance(group, dict):
                                group_name = group.get('name', '')
                                country, region, species = None, None, None
                                if '_' in group_name:
                                    parts = group_name.split('_', 2)
                                    country = parts[0] if len(parts) > 0 else None
                                    region = parts[1] if len(parts) > 1 else None
                                    species = parts[2] if len(parts) > 2 else None
                                
                                groups_data.append({
                                    'subject_id': subject_id,
                                    'group_id': group.get('id'),
                                    'group_name': group_name,
                                    'country': country,
                                    'region': region,
                                    'species': species
                                })
                
                if groups_data:
                    st.session_state.groups_df = pd.DataFrame(groups_data)
                    # Filter out unwanted groups
                    exclude_countries = ['AF', 'TwigaTracker', 'WildScapeVet', 'Donor', 'Movebank', 'White']
                    st.session_state.groups_df = st.session_state.groups_df[
                        ~st.session_state.groups_df['country'].isin(exclude_countries)
                    ]
                else:
                    st.session_state.groups_df = pd.DataFrame()
        
        # Use direct API calls like your R code - MUCH FASTER!
        st.write(f"📥 Getting all observations for {month_label} (direct API - high speed)...")
        
        try:
            # Get authentication token from ecoscope session
            auth_token = f"Bearer {er_io.token}"
            
            # URL encode the dates
            since_encoded = quote(start_str, safe='')
            until_encoded = quote(end_str, safe='')
            
            # Initial API call with cursor pagination (like your R code)
            base_url = f"{server_url}/api/v1.0/observations/"
            url = f"{base_url}?page_size=4000&use_cursor=true&since={since_encoded}&until={until_encoded}"
            
            headers = {
                'Authorization': auth_token,
                'Content-Type': 'application/json'
            }
            
            st.write(f"🚀 Starting direct API download for {month_label}...")
            
            all_data = []
            page_count = 0
            
            while url:
                response = requests.get(url, headers=headers)
                if response.status_code != 200:
                    st.error(f"API request failed with status {response.status_code}: {response.text}")
                    break
                
                data = response.json()
                
                if 'data' in data and 'results' in data['data']:
                    results = data['data']['results']
                    if results:
                        all_data.extend(results)
                        page_count += 1
                        st.write(f"📄 Downloaded page {page_count}, total records so far: {len(all_data):,}")
                    
                    # Get next URL for pagination
                    url = data['data'].get('next')
                else:
                    break
            
            if not all_data:
                st.info(f"ℹ️ No observations found for {month_label}")
                return pd.DataFrame(), 0
            
            # Convert to DataFrame
            df = pd.DataFrame(all_data)
            
            # Handle location data (similar to your R code's unnest)
            if 'location' in df.columns:
                # Extract coordinates from location
                location_data = []
                for idx, row in df.iterrows():
                    location = row.get('location', {})
                    if isinstance(location, dict):
                        lat = location.get('latitude', None)
                        lon = location.get('longitude', None)
                    else:
                        lat = lon = None
                    location_data.append({'latitude': lat, 'longitude': lon})
                
                location_df = pd.DataFrame(location_data)
                df = pd.concat([df.reset_index(drop=True), location_df], axis=1)
            
            # Handle device status properties (like your R code)
            if 'device_status_properties' in df.columns:
                # Flatten device status properties
                device_props = []
                for idx, row in df.iterrows():
                    props = row.get('device_status_properties', [])
                    prop_dict = {}
                    if isinstance(props, list):
                        for prop in props:
                            if isinstance(prop, dict):
                                label = prop.get('label', 'unknown')
                                value = prop.get('value', None)
                                units = prop.get('units', '')
                                # Handle battery voltage labeling like R code
                                if units == 'v':
                                    label = 'battery_volts'
                                elif label == 'battery' and units:
                                    label = units
                                prop_dict[label] = value
                    device_props.append(prop_dict)
                
                # Convert to DataFrame and merge
                if device_props:
                    device_df = pd.DataFrame(device_props)
                    df = pd.concat([df.reset_index(drop=True), device_df], axis=1)
            
            st.success(f"📥 Downloaded {len(df):,} observations for {month_label} using direct API")
            
        except Exception as e:
            st.error(f"Error downloading observations for {month_label}: {str(e)}")
            return pd.DataFrame(), 0
        
        # Handle subject identification (from the API response structure)
        if 'source' in df.columns:
            # Extract subject information from source data
            source_data = []
            for idx, row in df.iterrows():
                source = row.get('source', {})
                if isinstance(source, dict):
                    subject_id = source.get('subject')
                    source_id = source.get('id')
                else:
                    subject_id = source_id = None
                source_data.append({'subject_id': subject_id, 'source_id': source_id})
            
            source_df = pd.DataFrame(source_data)
            df = pd.concat([df.reset_index(drop=True), source_df], axis=1)
        
        # Ensure proper datetime columns
        datetime_cols = ['recorded_at', 'created_at', 'time']
        for col in datetime_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Debug: Check data structure
        st.write(f"📊 Observations columns: {list(df.columns)}")
        st.write(f"📊 Total observations: {len(df)}")
        
        # Join with subject details if requested and available
        if include_subject_details and 'subjects_df' in st.session_state and not st.session_state.subjects_df.empty:
            if 'subject_id' in df.columns:
                # Join with subjects data
                subject_cols = ['id', 'name', 'subject_subtype', 'common_name', 'sex', 'is_active']
                available_subject_cols = [col for col in subject_cols if col in st.session_state.subjects_df.columns]
                
                if available_subject_cols:
                    subjects_renamed = st.session_state.subjects_df[available_subject_cols].rename(columns={
                        'id': 'subject_id',
                        'name': 'subject_name',
                        'subject_subtype': 'subject_type',
                        'common_name': 'species',
                        'sex': 'subject_sex',
                        'is_active': 'subject_active'
                    })
                    
                    # Perform the merge
                    try:
                        df = df.merge(subjects_renamed, on='subject_id', how='left')
                        st.info(f"✅ Joined subject details for {month_label}")
                    except Exception as e:
                        st.warning(f"⚠️ Error joining subjects for {month_label}: {str(e)}")
                
                # Join with groups data
                if 'groups_df' in st.session_state and not st.session_state.groups_df.empty:
                    try:
                        df = df.merge(st.session_state.groups_df, on='subject_id', how='left')
                        st.info(f"✅ Joined group details for {month_label}")
                    except Exception as e:
                        st.warning(f"⚠️ Error joining groups for {month_label}: {str(e)}")
            else:
                st.warning(f"⚠️ No 'subject_id' column found in {month_label} data. Available columns: {list(df.columns)}")
        
        # Sort by recorded_at for better organization
        if 'recorded_at' in df.columns:
            df = df.sort_values('recorded_at')
        
        record_count = len(df)
        st.success(f"✅ {month_label}: {record_count:,} observations processed with direct API")
        
        return df, record_count
        
    except Exception as e:
        st.error(f"Error backing up {month_label}: {str(e)}")
        return pd.DataFrame(), 0

def backup_month_events(username, password, server_url, start_date, end_date, month_label):
    """Backup events for a single month"""
    try:
        er_io = EarthRangerIO(
            server=server_url,
            username=username,
            password=password
        )
        
        # Get events using ecoscope
        events_df = er_io.get_events(
            since=start_date.strftime('%Y-%m-%dT00:00:00Z'),
            until=end_date.strftime('%Y-%m-%dT23:59:59Z'),
            include_details=True,
            include_notes=True
        )
        
        if events_df.empty:
            return pd.DataFrame(), 0
        
        # Convert to regular DataFrame
        df = pd.DataFrame(events_df.drop(columns='geometry', errors='ignore'))
        
        record_count = len(df)
        st.success(f"✅ {month_label}: {record_count:,} events")
        
        return df, record_count
        
    except Exception as e:
        st.error(f"Error backing up events for {month_label}: {str(e)}")
        return pd.DataFrame(), 0

def create_incremental_backup_zip(backup_data_by_month, backup_id):
    """Create a ZIP file with monthly backup data"""
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add metadata
        metadata = {
            'backup_id': backup_id,
            'created_at': datetime.now().isoformat(),
            'total_months': len(backup_data_by_month),
            'months': list(backup_data_by_month.keys())
        }
        zip_file.writestr('backup_metadata.json', json.dumps(metadata, indent=2))
        
        # Add monthly data files
        for month_label, month_data in backup_data_by_month.items():
            for data_type, df in month_data.items():
                if not df.empty:
                    csv_buffer = io.StringIO()
                    df.to_csv(csv_buffer, index=False)
                    csv_content = csv_buffer.getvalue()
                    
                    filename = f"{month_label}/{backup_id}_{data_type}_{month_label}.csv"
                    zip_file.writestr(filename, csv_content)
    
    zip_buffer.seek(0)
    return zip_buffer

def main():
    """Main high-performance backup tool interface"""
    init_session_state()
    
    # Header with logo
    current_dir = Path(__file__).parent.parent
    logo_path = current_dir / "shared" / "logo.png"
    
    if logo_path.exists():
        try:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image(str(logo_path), width=300)
                st.markdown('<div style="text-align: center;"><h1>💾 ER Backup Tool</h1></div>', unsafe_allow_html=True)
                st.markdown('<div style="text-align: center;"><h3>🚀 High Performance Incremental Backup</h3></div>', unsafe_allow_html=True)
        except Exception:
            st.title("💾 ER Backup Tool - High Performance")
    else:
        st.title("💾 ER Backup Tool - High Performance")
    
    # Authentication check
    if not st.session_state.authenticated:
        authenticate_earthranger()
        return
    
    # Show authentication status
    st.sidebar.markdown("### 🔐 Authentication ✅")
    st.sidebar.write("**Method:** Username/Password")
    st.sidebar.write(f"**User:** {st.session_state.username}")
    
    if st.sidebar.button("🔓 Logout"):
        for key in ['authenticated', 'username', 'password', 'subjectsources_df', 'subjects_df', 'groups_df']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # Main interface
  
    # Backup configuration
    st.subheader("🛠️ Backup Configuration")
    
    # Set defaults - deployment info and subject info always included
    backup_subjectsource_obs_enabled = True  # Always include deployment information
    join_subject_details = True  # Always include subject information
    
    col1, col2 = st.columns(2)
    
    with col1:
        backup_events_enabled = st.checkbox("📝 Include Events", value=True,
                                           help="Field observations and incidents")
    
    with col2:
        filter_giraffes_only = st.checkbox("🦒 Filter to Giraffe Subtype Only", value=True,
                                          help="Only include data for animals with subType = 'giraffe'")
    
    # Speed optimization - ultrafast mode is now default and only option
    use_bulk_mode = True  # Always use ultrafast mode
    
    # Date range selection (part of backup configuration)
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=date(2024, 1, 1),
            min_value=date(2016, 1, 1),
            help="Start date for backup"
        )
    
    with col2:
        end_date = st.date_input(
            "End Date",
            value=date.today(),
            help="End date for backup"
        )
    
    if start_date > end_date:
        st.error("❌ Start date cannot be after end date")
        return
    
    # Show backup scope
    month_ranges = generate_month_ranges(start_date, end_date)
    total_months = len(month_ranges)
    
    st.info(f"""
    **Backup Scope:**
    - 📅 **Date Range**: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}
    - 📊 **Total Months**: {total_months}
    - ⏱️ **Estimated Time**: {total_months * 1:.0f}-{total_months * 3:.0f} minutes
    """)
    

    # Backup execution
    st.subheader("🚀 Execute Backup")
    
    # Since ultrafast mode is now default, skip the mode selection info
    
    if st.button("🔄 Start backup", type="primary"):
        if not backup_subjectsource_obs_enabled and not backup_events_enabled:
            st.error("❌ Please select at least one backup option")
            return
        
        # Generate backup ID
        backup_id = f"GCF_ER_Backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        st.session_state.current_backup_id = backup_id
        
        backup_data = {}
        total_records = 0
        start_time = datetime.now()
        
        try:
            if use_bulk_mode:
                # R-STYLE ULTRA-FAST MODE - Download all data at once
                st.markdown("### 🚀 Ultra-Fast R-Style Download")
                
                if backup_subjectsource_obs_enabled:
                    master_df, obs_count = backup_all_observations_r_style(
                        username=st.session_state.username,
                        password=st.session_state.password,
                        server_url=st.session_state.server_url,
                        start_date=start_date,
                        end_date=end_date,
                        include_subject_details=join_subject_details,
                        filter_giraffes_only=filter_giraffes_only
                    )
                    
                    if not master_df.empty:
                        backup_data['master_file'] = master_df
                        total_records += obs_count
                        
                        st.success(f"✅ Master file created with {len(master_df):,} comprehensive records")
                        
                        # Show what's in the master file
                        with st.expander("📊 Master File Details"):
                            st.write("**Master file includes:**")
                            st.write("- 🗂️ Raw observations data")
                            st.write("- 🏷️ Source/tag information (ID, manufacturer, model)")
                            st.write("- 📅 Deployment details (start/end dates, duration)")
                            st.write("- 🐘 Subject details (name, species, sex)")
                            st.write("- 🏞️ Group/landscape information (country, region, species)")
                            st.write("- 📍 Tag placement details (extracted from notes)")
                            st.write("- 🔋 Device status and battery information")
                            st.write("- 🧹 Filtered to deployment periods only")
                            st.write("- 📏 Standardized column names matching R output")
                            
                            cols = master_df.columns.tolist()
                            st.write(f"**Total columns:** {len(cols)}")
                            st.write(f"**Key columns:** {', '.join(cols[:10])}{'...' if len(cols) > 10 else ''}")
                            
                            # Show group information if available
                            if 'obsCountry' in master_df.columns:
                                try:
                                    # Handle potential multi-dimensional data
                                    country_series = master_df['obsCountry'].dropna()
                                    if len(country_series) > 0:
                                        countries = country_series.value_counts().head(5)
                                        st.write(f"**Top countries:** {dict(countries)}")
                                except Exception as e:
                                    st.write(f"**Countries:** Available but complex structure")
                            
                            if 'obsRegion' in master_df.columns:
                                try:
                                    region_series = master_df['obsRegion'].dropna()
                                    if len(region_series) > 0:
                                        regions = region_series.value_counts().head(5)
                                        st.write(f"**Top regions:** {dict(regions)}")
                                except Exception as e:
                                    st.write(f"**Regions:** Available but complex structure")
                            
                            if 'deployDays' in master_df.columns:
                                try:
                                    deploy_days = pd.to_numeric(master_df['deployDays'], errors='coerce')
                                    avg_deploy_days = deploy_days.mean()
                                    if not pd.isna(avg_deploy_days):
                                        st.write(f"**Average deployment days:** {avg_deploy_days:.1f}")
                                except Exception as e:
                                    st.write(f"**Deployment days:** Available but needs processing")
                
                if backup_events_enabled:
                    # Use ecoscope for events (usually smaller dataset)
                    if 'er_io' not in st.session_state:
                        from ecoscope.io.earthranger import EarthRangerIO
                        st.session_state.er_io = EarthRangerIO(
                            server=st.session_state.server_url,
                            username=st.session_state.username,
                            password=st.session_state.password
                        )
                    
                    st.write("📝 Getting events...")
                    events_df = st.session_state.er_io.get_events(
                        since=start_date.strftime('%Y-%m-%dT00:00:00Z'),
                        until=end_date.strftime('%Y-%m-%dT23:59:59Z'),
                        include_details=True,
                        include_notes=True
                    )
                    
                    if not events_df.empty:
                        events_clean = pd.DataFrame(events_df.drop(columns='geometry', errors='ignore'))
                        backup_data['events'] = events_clean
                        total_records += len(events_clean)
                        st.success(f"✅ Downloaded {len(events_clean):,} events")
                
            else:
                # MONTH-BY-MONTH MODE (original approach)
                st.markdown("### 📅 Month-by-Month Processing")
                
                # Initialize progress tracking
                month_ranges = generate_month_ranges(start_date, end_date)
                total_months = len(month_ranges)
                
                progress_data = {
                    'backup_id': backup_id,
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'total_months': total_months,
                    'completed_months': [],
                    'failed_months': [],
                    'backup_options': {
                        'subjectsource_obs': backup_subjectsource_obs_enabled,
                        'events': backup_events_enabled,
                        'join_details': join_subject_details
                    }
                }
                
                backup_data_by_month = {}
                
                # Progress tracking
                overall_progress = st.progress(0)
                status_text = st.empty()
                
                # Metrics display
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    completed_metric = st.metric("Completed Months", 0)
                with col2:
                    total_records_metric = st.metric("Total Records", 0)
                with col3:
                    current_month_metric = st.metric("Current Month", "Starting...")
                with col4:
                    eta_metric = st.metric("ETA", "Calculating...")
                
                for i, month_range in enumerate(month_ranges):
                    month_label = month_range['label']
                    month_start = month_range['start']
                    month_end = month_range['end']
                    
                    # Update current month display
                    current_month_metric.metric("Current Month", month_label)
                    status_text.text(f"📅 Processing {month_label} ({i+1}/{total_months})")
                    
                    month_data = {}
                    month_records = 0
                    
                    # Backup subjectsource observations for this month
                    if backup_subjectsource_obs_enabled:
                        obs_df, obs_count = backup_month_subjectsource_observations(
                            st.session_state.username,
                            st.session_state.password,
                            st.session_state.server_url,
                            month_start,
                            month_end,
                            month_label,
                            include_subject_details=join_subject_details
                        )
                        
                        if not obs_df.empty:
                            month_data['subjectsource_obs'] = obs_df
                            month_records += obs_count
                    
                    # Backup events for this month
                    if backup_events_enabled:
                        events_df, events_count = backup_month_events(
                            st.session_state.username,
                            st.session_state.password,
                            st.session_state.server_url,
                            month_start,
                            month_end,
                            month_label
                        )
                        
                        if not events_df.empty:
                            month_data['events'] = events_df
                            month_records += events_count
                    
                    # Store month data
                    if month_data:
                        backup_data_by_month[month_label] = month_data
                        progress_data['completed_months'].append(month_label)
                    else:
                        progress_data['failed_months'].append(month_label)
                    
                    total_records += month_records
                    
                    # Update progress
                    progress = (i + 1) / total_months
                    overall_progress.progress(progress)
                    
                    # Update metrics
                    completed_metric.metric("Completed Months", f"{i+1}/{total_months}")
                    total_records_metric.metric("Total Records", f"{total_records:,}")
                    
                    # Calculate ETA
                    elapsed = datetime.now() - start_time
                    if i > 0:
                        avg_time_per_month = elapsed.total_seconds() / (i + 1)
                        remaining_months = total_months - (i + 1)
                        eta_seconds = remaining_months * avg_time_per_month
                        eta_minutes = eta_seconds / 60
                        eta_metric.metric("ETA", f"{eta_minutes:.1f} min")
                    
                    # Save progress
                    save_backup_progress(backup_id, progress_data)
                    
                    # Small delay to prevent overwhelming the API
                    if i < total_months - 1:
                        import time
                        time.sleep(1)
                
                status_text.text("✅ Backup completed!")
                
                # Consolidate month data for download
                backup_data = backup_data_by_month
            
            # Store backup data in session state to persist across downloads (for both modes)
            if backup_data:
                # Convert any non-serializable objects before storing
                serializable_backup_data = {}
                for key, value in backup_data.items():
                    if hasattr(value, 'to_dict'):
                        # Convert DataFrame to dict for better serialization
                        serializable_backup_data[key] = value.copy()
                    else:
                        serializable_backup_data[key] = value
                
                st.session_state.backup_data = serializable_backup_data
                st.session_state.backup_metadata = {
                    'backup_id': backup_id,
                    'total_records': total_records,
                    'use_bulk_mode': use_bulk_mode,
                    'start_time': start_time,
                    'end_time': datetime.now()
                }
                
                # Also save to a temporary file as backup
                temp_backup_file = f"temp_backup_{backup_id}.pkl"
                try:
                    with open(temp_backup_file, 'wb') as f:
                        pickle.dump({
                            'backup_data': serializable_backup_data,
                            'backup_metadata': st.session_state.backup_metadata
                        }, f)
                    st.session_state.temp_backup_file = temp_backup_file
                except Exception as e:
                    st.warning(f"Could not save temporary backup file: {e}")
                
                st.success("✅ Backup completed successfully!")
                st.balloons()
            else:
                st.warning("⚠️ No data was backed up.")
                
        except Exception as e:
            st.error(f"❌ Backup failed: {str(e)}")
            st.exception(e)
    
    # Download section - moved outside backup execution to persist across streamlit reruns
    # Check both session state and temporary backup file
    backup_data_available = False
    backup_data = None
    metadata = None
    
    if 'backup_data' in st.session_state and st.session_state.backup_data:
        backup_data_available = True
        backup_data = st.session_state.backup_data
        metadata = st.session_state.backup_metadata
    elif 'temp_backup_file' in st.session_state and os.path.exists(st.session_state.temp_backup_file):
        # Fall back to temporary file if session state is lost
        try:
            with open(st.session_state.temp_backup_file, 'rb') as f:
                temp_data = pickle.load(f)
                backup_data = temp_data['backup_data']
                metadata = temp_data['backup_metadata']
                backup_data_available = True
                # Restore to session state
                st.session_state.backup_data = backup_data
                st.session_state.backup_metadata = metadata
        except Exception as e:
            st.error(f"Could not restore backup data: {e}")
    
    if backup_data_available:
        st.subheader("📦 Download Backup Files")
        
        backup_id = metadata['backup_id']
        total_records = metadata['total_records']
        use_bulk_mode = metadata['use_bulk_mode']
        elapsed_time = metadata['end_time'] - metadata['start_time']
        
        # Show summary
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Records", f"{total_records:,}")
        
        with col2:
            if use_bulk_mode:
                st.metric("Mode", "Ultra-Fast R-Style")
            else:
                st.metric("Months Processed", f"{len(backup_data) if isinstance(backup_data, dict) else 1}")
        
        with col3:
            st.metric("Total Time", f"{elapsed_time.total_seconds()/60:.1f} min")
        
        # Create download buttons
        if use_bulk_mode:
            # Single master file download for ultra-fast mode
            if 'master_file' in backup_data and not backup_data['master_file'].empty:
                st.markdown("### 🎯 Master File Download")
                st.info("📊 Comprehensive file with all data joined and processed (like your R workflow)")
                
                master_csv = backup_data['master_file'].to_csv(index=False)
                st.download_button(
                    label="🎯 Download Master Comprehensive File",
                    data=master_csv,
                    file_name=f"{backup_id}_MASTER_COMPREHENSIVE.csv",
                    mime="text/csv",
                    help="Single comprehensive file with all data joined (like your R ER_dataPull.R output)",
                    key="download_master"
                )
            else:
                st.warning("⚠️ No master file was created.")
            
            # Add events download if available
            if 'events' in backup_data and not backup_data['events'].empty:
                st.markdown("### 📝 Events File Download")
                events_csv = backup_data['events'].to_csv(index=False)
                st.download_button(
                    label="📝 Download Events File",
                    data=events_csv,
                    file_name=f"{backup_id}_EVENTS.csv",
                    mime="text/csv",
                    help="Events and reports data",
                    key="download_events"
                )
        else:
            # Month-by-month mode - create individual files for each month
            st.markdown("### 📅 Monthly Files Download")
            for month_label, month_data in backup_data.items():
                st.markdown(f"**{month_label}:**")
                for data_type, df in month_data.items():
                    if not df.empty:
                        csv_data = df.to_csv(index=False)
                        st.download_button(
                            label=f"📥 Download {data_type.title()} - {month_label}",
                            data=csv_data,
                            file_name=f"{backup_id}_{data_type}_{month_label}.csv",
                            mime="text/csv",
                            key=f"{month_label}_{data_type}"
                        )
        
        # Clear backup data button
        if st.button("🗑️ Clear Backup Data", help="Remove downloaded backup from memory"):
            if 'backup_data' in st.session_state:
                del st.session_state.backup_data
            if 'backup_metadata' in st.session_state:
                del st.session_state.backup_metadata
            # Clean up temporary file
            if 'temp_backup_file' in st.session_state:
                try:
                    if os.path.exists(st.session_state.temp_backup_file):
                        os.remove(st.session_state.temp_backup_file)
                except Exception as e:
                    st.warning(f"Could not remove temporary file: {e}")
                del st.session_state.temp_backup_file
            st.success("✅ Backup data cleared from memory")
            st.rerun()

if __name__ == "__main__":
    main()
