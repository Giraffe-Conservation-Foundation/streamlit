#!/usr/bin/env python3
"""
Minimal SpoorTrack Performance Report Generator
Quick test without heavy imports
"""

import sys
import os
from datetime import datetime, timedelta
import getpass

# Simple test without heavy dependencies
print("🦒 SpoorTrack Performance Report Generator")
print("=" * 45)
print("Analyzes performance of all deployed SpoorTrack sources")
print("Reports mean battery voltage and observations per day\n")

# Test ecoscope import
try:
    print("Testing ecoscope import...")
    from ecoscope.io.earthranger import EarthRangerIO
    print("✅ Ecoscope available")
    ECOSCOPE_AVAILABLE = True
except ImportError as e:
    print(f"❌ Ecoscope not available: {e}")
    ECOSCOPE_AVAILABLE = False

if not ECOSCOPE_AVAILABLE:
    print("❌ Ecoscope package is required but not available.")
    print("Install with: pip install ecoscope")
    sys.exit(1)

# Get credentials
print("\n🔑 Authentication Setup")
username = input("EarthRanger Username: ")
password = getpass.getpass("EarthRanger Password: ")

print(f"\n🔐 Connecting to EarthRanger...")
print(f"Server: https://twiga.pamdas.org")
print(f"Username: {username}")

try:
    # Initialize EarthRanger connection
    er = EarthRangerIO(
        server="https://twiga.pamdas.org",
        username=username,
        password=password
    )
    
    print("✅ Authentication successful!")
    
    # Test basic connection
    print("\n🔍 Testing connection...")
    sources = er.get_sources(limit=5)
    print(f"✅ Retrieved {len(sources)} test sources")
    
    # Look for SpoorTrack sources
    print("\n🔍 Searching for SpoorTrack sources...")
    all_sources = er.get_sources()
    print(f"📊 Total sources found: {len(all_sources)}")
    
    if 'manufacturer_id' in all_sources.columns:
        spoortrack_sources = all_sources[
            all_sources['manufacturer_id'].str.contains('SPOORTRACK', case=False, na=False)
        ]
        print(f"✅ Found {len(spoortrack_sources)} SpoorTrack sources")
        
        if len(spoortrack_sources) > 0:
            print("\nSpoorTrack Sources:")
            for _, source in spoortrack_sources.head(5).iterrows():
                print(f"  - {source['name']} (ID: {source['id']})")
    else:
        print("❌ No manufacturer_id column found")
    
    print(f"\n✅ Connection test completed successfully!")
    print(f"🎉 Ready to generate full performance report!")

except Exception as e:
    print(f"❌ Connection failed: {str(e)}")
    print("💡 Please check your credentials and network connection")
