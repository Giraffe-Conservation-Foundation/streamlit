#!/usr/bin/env python3
"""
Bailey's Triple Catch Analysis - Residents Only
================================================

Population estimation using Bailey's Triple Catch method with residents/transients classification.
Based on the R script: residents_only_analysis_parameterized.R

Author: Giraffe Conservation Foundation
Date: February 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os

try:
    from pywildbook import WildbookClient
    from pywildbook.queries import filter_by_location, filter_by_date_range, combine_queries
    PYWILDBOOK_AVAILABLE = True
except ImportError as e:
    PYWILDBOOK_AVAILABLE = False
    print(f"⚠️ pywildbook not available: {e}")


class BaileyAnalysis:
    """
    Bailey's Triple Catch population estimation
    
    Implements the residents-only approach:
    1. Classify individuals as residents (2+ captures) or transients (1 capture)
    2. Apply Bailey/Chapman estimator to residents only
    3. Add transients to get total population estimate
    """
    
    def __init__(self, capture_data, occasion_col='occasion'):
        """
        Initialize Bailey's analysis
        
        Parameters:
        -----------
        capture_data : DataFrame
            Columns: individual_id, date, location, occasion (optional)
        occasion_col : str
            Column name to use as occasion identifier (default: 'occasion')
            If 'occasion' column exists, uses that. Otherwise falls back to 'date'
        """
        self.capture_data = capture_data.copy()
        
        # Determine which column to use for occasions
        if occasion_col in self.capture_data.columns:
            self.occasion_col = occasion_col
            self.unique_occasions = sorted(self.capture_data[occasion_col].unique())
            print(f"\n📊 Bailey's Triple Catch Analysis Initialized")
            print(f"  • Using '{occasion_col}' as occasion identifier")
            print(f"  • Total encounters: {len(self.capture_data)}")
            print(f"  • Unique individuals: {self.capture_data['individual_id'].nunique()}")
            print(f"  • Survey occasions: {len(self.unique_occasions)}")
            if len(self.unique_occasions) >= 3:
                print(f"    - Occasion 1: {self.unique_occasions[0]}")
                print(f"    - Occasion 2: {self.unique_occasions[1]}")
                print(f"    - Occasion 3: {self.unique_occasions[2]}")
        else:
            # Fall back to date-based occasions
            self.occasion_col = 'date'
            if 'date' in self.capture_data.columns:
                self.capture_data['date'] = pd.to_datetime(self.capture_data['date'])
            self.unique_occasions = sorted(self.capture_data['date'].unique())
            print(f"\n📊 Bailey's Triple Catch Analysis Initialized")
            print(f"  • Using 'date' as occasion identifier (no 'occasion' column found)")
            print(f"  • Total encounters: {len(self.capture_data)}")
            print(f"  • Unique individuals: {self.capture_data['individual_id'].nunique()}")
            print(f"  • Survey dates: {len(self.unique_occasions)}")
            if len(self.unique_occasions) >= 3:
                print(f"    - Day 1: {self.unique_occasions[0]}")
                print(f"    - Day 2: {self.unique_occasions[1]}")
                print(f"    - Day 3: {self.unique_occasions[2]}")
    
    def classify_residents_transients(self, min_captures=2):
        """
        Classify individuals as residents or transients
        
        Parameters:
        -----------
        min_captures : int
            Minimum number of captures to be classified as resident (default: 2)
        
        Returns:
        --------
        residents, transients : DataFrames
        """
        # Count captures per individual
        capture_counts = self.capture_data.groupby('individual_id').size().reset_index(name='total_captures')
        
        # Classify
        residents = capture_counts[capture_counts['total_captures'] >= min_captures].copy()
        transients = capture_counts[capture_counts['total_captures'] < min_captures].copy()
        
        print(f"\n📋 Classification Results (min_captures={min_captures})")
        print(f"=" * 60)
        
        # Capture frequency distribution
        print(f"\nCapture frequency distribution:")
        max_captures = capture_counts['total_captures'].max()
        for i in range(1, int(max_captures) + 1):
            n = sum(capture_counts['total_captures'] == i)
            pct = round(100 * n / len(capture_counts), 1)
            print(f"  {i} capture(s): {n} individuals ({pct}%)")
        
        print(f"\nClassification:")
        print(f"  • Residents (≥{min_captures} captures): {len(residents)} individuals")
        print(f"  • Transients (<{min_captures} captures): {len(transients)} individuals")
        
        return residents, transients
    
    def bailey_triple_catch(self, residents_only=True):
        """
        Apply Bailey's Triple Catch (Chapman estimator) method
        
        Parameters:
        -----------
        residents_only : bool
            If True, only use residents for estimation (recommended)
        
        Returns:
        --------
        results : dict
            Population estimate and statistics
        """
        if len(self.unique_occasions) < 3:
            raise ValueError(f"Need at least 3 survey occasions, got {len(self.unique_occasions)}")
        
        # Classify residents and transients
        residents, transients = self.classify_residents_transients()
        
        # Filter to residents if requested
        if residents_only:
            resident_ids = residents['individual_id'].tolist()
            analysis_data = self.capture_data[self.capture_data['individual_id'].isin(resident_ids)].copy()
            print(f"\n🔍 Using residents only for Bailey's estimate")
        else:
            analysis_data = self.capture_data.copy()
            print(f"\n🔍 Using all individuals for Bailey's estimate")
        
        # Get individuals captured on each of first 3 occasions
        occ1 = self.unique_occasions[0]
        occ2 = self.unique_occasions[1]
        occ3 = self.unique_occasions[2]
        
        occ1_ids = set(analysis_data[analysis_data[self.occasion_col] == occ1]['individual_id'].unique())
        occ2_ids = set(analysis_data[analysis_data[self.occasion_col] == occ2]['individual_id'].unique())
        occ3_ids = set(analysis_data[analysis_data[self.occasion_col] == occ3]['individual_id'].unique())
        
        # Sample statistics
        n1 = len(occ1_ids)
        n2 = len(occ2_ids)
        n3 = len(occ3_ids)
        m12 = len(occ1_ids & occ2_ids)  # Seen on both occasion 1 and 2
        m13 = len(occ1_ids & occ3_ids)  # Seen on both occasion 1 and 3
        m23 = len(occ2_ids & occ3_ids)  # Seen on both occasion 2 and 3
        m123 = len(occ1_ids & occ2_ids & occ3_ids)  # Seen on all 3 occasions
        
        print(f"\n📊 Sample Statistics")
        print(f"=" * 60)
        print(f"  Occasion 1 ({occ1}): {n1} individuals")
        print(f"  Occasion 2 ({occ2}): {n2} individuals")
        print(f"  Occasion 3 ({occ3}): {n3} individuals")
        print(f"  Recaptures 1&2: {m12}")
        print(f"  Recaptures 1&3: {m13}")
        print(f"  Recaptures 2&3: {m23}")
        print(f"  All 3 occasions: {m123}")
        
        # Check if we can calculate estimate
        if m23 == 0:
            print(f"\n⚠️ No recaptures between occasions 2 and 3")
            print(f"Cannot calculate population estimate")
            return None
        
        # Chapman's estimator (modified Petersen for closed population)
        M = n1 + n2 - m12  # Number marked by end of occasion 2
        n = n3             # Sample size on occasion 3
        m = m23            # Recaptures on occasion 3 (from occasions 1 or 2)
        
        # Chapman's estimator
        N_chapman = ((M + 1) * (n + 1)) / (m + 1) - 1
        
        # Standard error (Seber 1982)
        se_chapman = np.sqrt(((M + 1) * (n + 1) * (M - m) * (n - m)) / 
                            ((m + 1)**2 * (m + 2)))
        
        # 95% confidence interval (normal approximation)
        ci_lower = N_chapman - 1.96 * se_chapman
        ci_upper = N_chapman + 1.96 * se_chapman
        
        print(f"\n🔬 Chapman's Estimator (Residents Only)")
        print(f"=" * 60)
        print(f"  M (marked by occasion 2): {M}")
        print(f"  n (sample occasion 3): {n}")
        print(f"  m (recaptures occasion 3): {m}")
        print(f"  N̂ = {N_chapman:.1f}")
        print(f"  SE = {se_chapman:.1f}")
        print(f"  95% CI: ({ci_lower:.1f}, {ci_upper:.1f})")
        
        # Add transients for total estimate
        N_total = N_chapman + len(transients)
        
        print(f"\n🦒 Total Population Estimate")
        print(f"=" * 60)
        print(f"  Resident estimate: {N_chapman:.1f}")
        print(f"  Transient count: {len(transients)}")
        print(f"  Total estimate: {N_total:.1f}")
        
        # Compile results
        results = {
            'method': 'Bailey Triple Catch - Residents Only',
            'approach': 'residents_only' if residents_only else 'all_individuals',
            'occasion_type': self.occasion_col,
            'total_individuals': self.capture_data['individual_id'].nunique(),
            'residents': len(residents),
            'transients': len(transients),
            'sample_statistics': {
                'n1': n1,
                'n2': n2,
                'n3': n3,
                'm12': m12,
                'm13': m13,
                'm23': m23,
                'm123': m123,
                'M': M
            },
            'resident_estimate': {
                'N': round(N_chapman, 1),
                'SE': round(se_chapman, 1),
                'CI_lower': round(ci_lower, 1),
                'CI_upper': round(ci_upper, 1),
                'CV': round(100 * se_chapman / N_chapman, 1)
            },
            'total_estimate': {
                'N': round(N_total, 1),
                'note': 'Residents + all transients'
            },
            'occasions': {
                'occasion1': str(occ1),
                'occasion2': str(occ2),
                'occasion3': str(occ3)
            }
        }
        
        return results


class GiraffeSpotterClient:
    """
    Connect to GiraffeSpotter (Wildbook) using pywildbook library
    """
    
    def __init__(self, base_url='https://giraffespotter.org'):
        """
        Initialize GiraffeSpotter client
        
        Parameters:
        -----------
        base_url : str
            Base URL for GiraffeSpotter instance (default: giraffespotter.org without www)
        """
        try:
            self.client = WildbookClient(base_url=base_url)
            self.authenticated = False
        except Exception as e:
            print(f"❌ Failed to initialize WildbookClient: {str(e)}")
            self.client = None
            self.authenticated = False
    
    def login(self, username, password):
        """
        Login to GiraffeSpotter
        
        Parameters:
        -----------
        username : str
            GiraffeSpotter username
        password : str
            GiraffeSpotter password
        
        Returns:
        --------
        success : bool
        """
        print(f"\n🔐 Connecting to GiraffeSpotter...")
        
        if self.client is None:
            print("❌ Client not initialized")
            return False
        
        try:
            # Call login method with credentials
            result = self.client.login(username=username, password=password)
            
            # Check if authentication was successful
            if self.client.is_authenticated:
                self.authenticated = True
                print("✅ Successfully authenticated with GiraffeSpotter")
                return True
            else:
                print("❌ Authentication failed: Invalid credentials")
                return False
                
        except Exception as e:
            print(f"❌ Authentication failed: {str(e)}")
            self.authenticated = False
            return False
    
    def download_encounters(self, location=None, start_date=None, end_date=None, size=1000, hydrate=True):
        """
        Download encounter data from GiraffeSpotter
        
        Parameters:
        -----------
        location : str, optional
            Location ID to filter
        start_date : str, optional
            Start date (YYYY-MM-DD)
        end_date : str, optional
            End date (YYYY-MM-DD)
        size : int
            Maximum number of results to fetch
        hydrate : bool
            If True, fetch full encounter records to include coordinates
        
        Returns:
        --------
        encounters : list of dicts
        """
        if not self.authenticated or self.client is None:
            print("❌ Not authenticated. Please login first.")
            return None
        
        print(f"\n📡 Downloading encounter data from GiraffeSpotter...")
        
        # Build query with filters
        filters = []
        
        if location:
            filters.append(filter_by_location(location_id=location))
        
        if start_date or end_date:
            filters.append(filter_by_date_range(start_date=start_date, end_date=end_date))
        
        # Combine filters if we have any
        if filters:
            if len(filters) == 1:
                query = filters[0]
            else:
                query = combine_queries(*filters, operator='must')
        else:
            query = None
        
        def extract_encounter_id(enc):
            for key in ('encounterId', 'encounter_id', 'encounterID', 'id', '_id'):
                value = enc.get(key)
                if value:
                    return value
            return None

        try:
            # Search encounters with pagination
            all_encounters = []
            offset = 0
            batch_size = min(100, size)
            
            while len(all_encounters) < size:
                result = self.client.search_encounters(query, from_=offset, size=batch_size)
                hits = result.get('hits', [])
                
                if not hits:
                    break

                for hit in hits:
                    if len(all_encounters) >= size:
                        break

                    if hydrate:
                        enc_id = extract_encounter_id(hit)
                        if enc_id:
                            try:
                                full_encounter = self.client.get_encounter(enc_id)
                                if isinstance(full_encounter, dict):
                                    all_encounters.append(full_encounter)
                                    continue
                            except Exception:
                                pass
                    all_encounters.append(hit)

                print(f"  Retrieved {len(all_encounters)} encounters...")
                
                if len(all_encounters) >= result.get('total', 0):
                    break
                
                offset += batch_size
            
            print(f"✅ Downloaded {len(all_encounters)} encounter records")
            return all_encounters
                
        except Exception as e:
            print(f"❌ Download error: {str(e)}")
            return None


def prepare_bailey_data(wildbook_encounters, include_unidentified=True):
    """
    Prepare GiraffeSpotter encounter data for Bailey's analysis
    
    Parameters:
    -----------
    wildbook_encounters : list of dicts
        Encounter data from pywildbook
    include_unidentified : bool, default=True
        If True, assign unique IDs to unidentified encounters (e.g., UNIDENT_001)
        If False, skip unidentified encounters entirely
    
    Returns:
    --------
    bailey_data : DataFrame
        Formatted for Bailey analysis with columns: individual_id, date, location
    """
    print(f"\n🔧 Preparing data for Bailey's analysis...")
    
    if not wildbook_encounters:
        print("⚠️ No encounter data provided")
        return None
    
    def extract_coords(enc):
        """Extract latitude/longitude from various possible fields."""
        candidate_pairs = [
            ('decimalLatitude', 'decimalLongitude'),
            ('latitude', 'longitude'),
            ('lat', 'lon'),
            ('lat', 'lng'),
            ('gpsLatitude', 'gpsLongitude'),
            ('gps_latitude', 'gps_longitude'),
            ('verbatimLatitude', 'verbatimLongitude'),
            ('verbatim_latitude', 'verbatim_longitude')
        ]

        for lat_key, lon_key in candidate_pairs:
            lat_val = enc.get(lat_key)
            lon_val = enc.get(lon_key)
            if lat_val not in (None, '') and lon_val not in (None, ''):
                return lat_val, lon_val

        # Check common nested objects
        nested_keys = [
            'locationGeoPoint', 'location', 'encounterLocation', 'geoPoint', 'locationPoint',
            'point', 'coordinates', 'gpsLocation'
        ]
        for key in nested_keys:
            obj = enc.get(key)
            if isinstance(obj, dict):
                # GeoJSON style: {"type": "Point", "coordinates": [lon, lat]}
                if 'coordinates' in obj and isinstance(obj['coordinates'], (list, tuple)):
                    coords = obj['coordinates']
                    if len(coords) >= 2:
                        return coords[1], coords[0]
                # GiraffeSpotter style: {"lon": 37.27917, "lat": -2.46456}
                if 'lon' in obj and 'lat' in obj:
                    lat_val = obj.get('lat')
                    lon_val = obj.get('lon')
                    if lat_val not in (None, '') and lon_val not in (None, ''):
                        return lat_val, lon_val
                for lat_key, lon_key in candidate_pairs:
                    lat_val = obj.get(lat_key)
                    lon_val = obj.get(lon_key)
                    if lat_val not in (None, '') and lon_val not in (None, ''):
                        return lat_val, lon_val
            elif isinstance(obj, (list, tuple)) and len(obj) >= 2:
                # Assume [lon, lat]
                return obj[1], obj[0]

        return None, None

    # Extract relevant fields from pywildbook format
    records = []
    unidentified_counter = 1
    
    for enc in wildbook_encounters:
        # pywildbook returns nested dict structure
        individual_id = enc.get('individualId') or enc.get('individual_id')
        date = enc.get('verbatimEventDate') or enc.get('date') or enc.get('eventDate')
        location = enc.get('locationId') or enc.get('location_id') or enc.get('locationID')

        # GPS coordinates (try multiple possible keys)
        lat, lon = extract_coords(enc)
        
        # Skip if missing critical data (date is required)
        if not date:
            continue
        
        # Handle unidentified encounters
        is_unidentified = (
            not individual_id or 
            individual_id == '' or 
            (isinstance(individual_id, str) and 'unidentified' in individual_id.lower())
        )
        
        if is_unidentified:
            if not include_unidentified:
                continue  # Skip this encounter
            else:
                # Assign unique ID (each unidentified = unique individual)
                individual_id = f"UNIDENT_{unidentified_counter:03d}"
                unidentified_counter += 1
        
        records.append({
            'individual_id': str(individual_id),
            'date': date,
            'location': location or 'Unknown',
            'latitude': lat,
            'longitude': lon
        })
    
    if not records:
        print("⚠️ No valid encounters found after filtering")
        return None
    
    # Create DataFrame
    bailey_data = pd.DataFrame(records)
    
    # Parse dates
    bailey_data['date'] = pd.to_datetime(bailey_data['date'], errors='coerce')
    bailey_data = bailey_data[bailey_data['date'].notna()].copy()
    
    print(f"  • Encounters: {len(bailey_data)}")
    print(f"  • Unique individuals: {bailey_data['individual_id'].nunique()}")
    print(f"  • Survey dates: {bailey_data['date'].nunique()}")
    print(f"  • Locations: {bailey_data['location'].nunique()}")
    missing_coords = bailey_data['latitude'].isna().sum() + bailey_data['longitude'].isna().sum()
    if missing_coords:
        print(f"  • Missing coords (lat/lon): {missing_coords}")
    print(f"✅ Data prepared")
    
    return bailey_data
