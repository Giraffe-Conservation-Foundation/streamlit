#!/usr/bin/env python3
"""
Basic SpoorTrack Test - Immediate Output
"""

print("🦒 SpoorTrack Basic Test")
print("=" * 30)

import sys
print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} running")

try:
    import pandas as pd
    print("✅ pandas available")
except ImportError:
    print("❌ pandas not available")

try:
    from ecoscope.io.earthranger import EarthRangerIO
    print("✅ ecoscope available")
    
    # Ask for credentials
    print("\n🔑 Ready to connect to EarthRanger")
    username = input("Enter username: ")
    print(f"Username entered: {username}")
    
    # For now, just show this works
    print("✅ Input working! Ready for full test.")
    
except ImportError as e:
    print(f"❌ ecoscope not available: {e}")

print("\n✅ Basic test completed!")
