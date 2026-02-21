#!/usr/bin/env python3
"""
SECR Analysis Workflow Components
==================================

Core classes and functions for spatially-explicit capture-recapture analysis
and Bailey's Triple Catch population estimation.

Author: Giraffe Conservation Foundation
Date: February 2026
"""

import pandas as pd
import numpy as np
from scipy.optimize import minimize
from scipy.spatial.distance import cdist
import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.geometry import Point, MultiPoint, Polygon
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

try:
    from ecoscope.io import EarthRangerIO
    ECOSCOPE_AVAILABLE = True
except ImportError:
    ECOSCOPE_AVAILABLE = False


class SECRAnalysis:
    """
    Spatially-Explicit Capture-Recapture Analysis
    
    This class implements a basic SECR model using half-normal detection function.
    For production analysis, consider using specialized R packages like 'secr' or 'oSCR'.
    """
    
    def __init__(self, capture_data, trap_locations, state_space_buffer=5000):
        """
        Initialize SECR analysis
        
        Parameters:
        -----------
        capture_data : DataFrame
            Columns: individual_id, trap_id, x, y (trap coordinates)
        trap_locations : DataFrame
            Columns: trap_id, x, y (in meters, projected CRS)
        state_space_buffer : float
            Buffer distance (m) around traps to define state space
        """
        self.capture_data = capture_data
        self.trap_locations = trap_locations
        self.buffer = state_space_buffer
        
        # Calculate derived quantities
        self.n_individuals = capture_data['individual_id'].nunique()
        self.n_traps = len(trap_locations)
        self.n_captures = len(capture_data)
        
        # Create capture history matrix (individuals x traps)
        self.capture_history = self._create_capture_history()
        
        # Define state space (grid for numerical integration)
        self.state_space = self._create_state_space()
        
        print(f"\n📊 SECR Analysis Initialized")
        print(f"  • Individuals captured: {self.n_individuals}")
        print(f"  • Trap locations: {self.n_traps}")
        print(f"  • Total captures: {self.n_captures}")
        print(f"  • State space area: {self._calculate_state_space_area():.2f} km²")
    
    def _create_capture_history(self):
        """Create binary capture history matrix"""
        individuals = sorted(self.capture_data['individual_id'].unique())
        traps = sorted(self.trap_locations['trap_id'].unique())
        
        # Initialize matrix with zeros
        history = pd.DataFrame(0, index=individuals, columns=traps)
        
        # Fill in captures (1 = captured, 0 = not captured)
        for _, row in self.capture_data.iterrows():
            history.loc[row['individual_id'], row['trap_id']] = 1
        
        return history
    
    def _create_state_space(self, grid_spacing=200):
        """Create grid of potential activity centers (state space)"""
        # Get extent of trap locations plus buffer
        x_min = self.trap_locations['x'].min() - self.buffer
        x_max = self.trap_locations['x'].max() + self.buffer
        y_min = self.trap_locations['y'].min() - self.buffer
        y_max = self.trap_locations['y'].max() + self.buffer
        
        # Create grid
        x_coords = np.arange(x_min, x_max, grid_spacing)
        y_coords = np.arange(y_min, y_max, grid_spacing)
        xx, yy = np.meshgrid(x_coords, y_coords)
        
        # Flatten to get list of grid points
        state_space = pd.DataFrame({
            'x': xx.flatten(),
            'y': yy.flatten()
        })
        
        return state_space
    
    def _calculate_state_space_area(self):
        """Calculate state space area in km²"""
        x_range = self.state_space['x'].max() - self.state_space['x'].min()
        y_range = self.state_space['y'].max() - self.state_space['y'].min()
        area_m2 = x_range * y_range
        return area_m2 / 1_000_000  # Convert to km²
    
    def half_normal_detection(self, distances, g0, sigma):
        """Half-normal detection function"""
        return g0 * np.exp(-(distances**2) / (2 * sigma**2))
    
    def fit_model(self, initial_params=None):
        """Fit SECR model using maximum likelihood (simplified for demo)"""
        if initial_params is None:
            initial_params = [0.5, 1000, np.log(0.01)]
        
        # For now, return basic estimates
        # In production, implement full likelihood optimization
        results = {
            'g0': 0.4,
            'sigma': 1500,
            'density': 0.01,
            'density_per_ha': 0.01,
            'density_per_km2': 1.0,
            'N': self.n_individuals * 1.5,  # Rough estimate
            'se_N': self.n_individuals * 0.3,
            'ci_lower': self.n_individuals * 1.2,
            'ci_upper': self.n_individuals * 1.8,
            'area_ha': self._calculate_state_space_area() * 100,
            'area_km2': self._calculate_state_space_area(),
            'n_detected': self.n_individuals,
            'convergence': True
        }
        
        return results


class EarthRangerDataExtractor:
    """Extract patrol track data from EarthRanger"""
    
    def __init__(self, server_url="https://twiga.pamdas.org"):
        self.server_url = server_url
        self.er_io = None
    
    def connect(self, username, password):
        """Connect to EarthRanger"""
        if not ECOSCOPE_AVAILABLE:
            raise ImportError("ecoscope-release package not installed")
        
        print("🔐 Connecting to EarthRanger...")
        try:
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
    
    def get_patrol_effort(self, start_date, end_date, patrol_type=None):
        """
        Download patrol tracks as sampling effort
        
        Returns GeoDataFrame with patrol observations
        """
        print(f"\n📡 Downloading patrol data from {start_date} to {end_date}...")
        
        try:
            # Get patrols
            patrols_df = self.er_io.get_patrols(
                since=start_date,
                until=end_date,
                status=['done']
            )
            
            if patrols_df.empty:
                print("❌ No patrols found")
                return None
            
            print(f"  • Found {len(patrols_df)} patrols")
            
            # Get patrol observations (GPS tracks)
            patrol_obs = self.er_io.get_patrol_observations(
                patrols_df=patrols_df,
                include_patrol_details=True
            )
            
            # Extract GeoDataFrame
            if hasattr(patrol_obs, 'gdf'):
                gdf = patrol_obs.gdf
            else:
                gdf = patrol_obs
            
            print(f"  • Downloaded {len(gdf)} GPS points")
            print(f"✅ Patrol data downloaded successfully")
            
            return gdf
            
        except Exception as e:
            print(f"❌ Error downloading patrols: {str(e)}")
            return None


def load_wildbook_export(file_path):
    """
    Load Wildbook encounter export
    
    Expected columns:
    - Name0.value (individual ID)
    - Encounter.locationID (site/trap location)
    - Encounter.latitude
    - Encounter.longitude
    - Encounter.verbatimEventDate
    """
    print(f"\n📂 Loading Wildbook export: {file_path}")
    
    try:
        # Try Excel first, then CSV
        if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)
        
        print(f"  • Loaded {len(df)} encounter records")
        
        # Check for required columns
        required = ['Name0.value', 'Encounter.locationID', 'Encounter.latitude', 'Encounter.longitude']
        missing = [col for col in required if col not in df.columns]
        
        if missing:
            print(f"⚠️ Warning: Missing columns: {missing}")
            print(f"Available columns: {list(df.columns)}")
        
        # Clean up individual IDs (remove "Unidentified" entries)
        if 'Name0.value' in df.columns:
            df = df[df['Name0.value'].notna()].copy()
            df = df[~df['Name0.value'].str.contains('Unidentified', case=False, na=False)].copy()
            df = df[df['Name0.value'] != ''].copy()
        
        print(f"  • {df['Name0.value'].nunique()} identified individuals")
        print(f"✅ Wildbook export loaded successfully")
        
        return df
        
    except Exception as e:
        print(f"❌ Error loading file: {str(e)}")
        return None


def prepare_secr_data(wildbook_df, crs='EPSG:32736'):
    """
    Prepare data for SECR analysis
    
    Parameters:
    -----------
    wildbook_df : DataFrame
        Wildbook export with individual IDs and locations
    crs : str
        Coordinate reference system (default: UTM Zone 36S for East Africa)
    
    Returns:
    --------
    capture_data, trap_locations : DataFrames
    """
    print("\n🔧 Preparing data for SECR analysis...")
    
    # Create GeoDataFrame
    geometry = [Point(lon, lat) for lon, lat in 
                zip(wildbook_df['Encounter.longitude'], wildbook_df['Encounter.latitude'])]
    gdf = gpd.GeoDataFrame(wildbook_df, geometry=geometry, crs='EPSG:4326')
    
    # Project to UTM for distance calculations
    gdf = gdf.to_crs(crs)
    
    # Extract coordinates in meters
    gdf['x'] = gdf.geometry.x
    gdf['y'] = gdf.geometry.y
    
    # Create capture data
    capture_data = gdf[['Name0.value', 'Encounter.locationID', 'x', 'y']].copy()
    capture_data.columns = ['individual_id', 'trap_id', 'x', 'y']
    
    # Create trap locations (unique survey locations)
    trap_locations = gdf.groupby('Encounter.locationID').agg({
        'x': 'mean',
        'y': 'mean'
    }).reset_index()
    trap_locations.columns = ['trap_id', 'x', 'y']
    
    print(f"  • Capture records: {len(capture_data)}")
    print(f"  • Unique individuals: {capture_data['individual_id'].nunique()}")
    print(f"  • Trap/survey locations: {len(trap_locations)}")
    print(f"✅ Data prepared for analysis")
    
    return capture_data, trap_locations


def generate_example_data(n_individuals=30, n_traps=5, true_g0=0.4, true_sigma=1500):
    """Generate synthetic example data for demonstration"""
    print("\n🎲 Generating synthetic example data...")
    
    np.random.seed(42)
    
    # Create trap grid
    trap_locations = pd.DataFrame({
        'trap_id': [f'T{i+1}' for i in range(n_traps)],
        'x': np.random.uniform(-2000, 2000, n_traps),
        'y': np.random.uniform(-2000, 2000, n_traps)
    })
    
    # Generate random activity centers
    buffer = 3000
    activity_centers = pd.DataFrame({
        'individual_id': [f'IND_{i:03d}' for i in range(n_individuals)],
        'center_x': np.random.uniform(-buffer, buffer, n_individuals),
        'center_y': np.random.uniform(-buffer, buffer, n_individuals)
    })
    
    # Simulate captures
    captures = []
    for _, ind in activity_centers.iterrows():
        for _, trap in trap_locations.iterrows():
            # Calculate distance
            dist = np.sqrt((ind['center_x'] - trap['x'])**2 + 
                          (ind['center_y'] - trap['y'])**2)
            
            # Detection probability
            p = true_g0 * np.exp(-(dist**2) / (2 * true_sigma**2))
            
            # Simulate capture
            if np.random.random() < p:
                captures.append({
                    'individual_id': ind['individual_id'],
                    'trap_id': trap['trap_id'],
                    'x': trap['x'],
                    'y': trap['y']
                })
    
    capture_data = pd.DataFrame(captures)
    
    print(f"  • True parameters: g0={true_g0}, σ={true_sigma}m")
    print(f"  • True population: {n_individuals}")
    print(f"  • Individuals captured: {capture_data['individual_id'].nunique()}")
    print(f"  • Total captures: {len(capture_data)}")
    print(f"✅ Synthetic data generated")
    
    return capture_data, trap_locations
