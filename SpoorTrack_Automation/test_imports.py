#!/usr/bin/env python3
"""
Test imports to debug the hanging issue
"""

print("Testing imports...")

try:
    print("1. Testing pandas...")
    import pandas as pd
    print("✅ pandas imported successfully")
except Exception as e:
    print(f"❌ pandas failed: {e}")

try:
    print("2. Testing matplotlib...")
    import matplotlib.pyplot as plt
    print("✅ matplotlib imported successfully")
except Exception as e:
    print(f"❌ matplotlib failed: {e}")

try:
    print("3. Testing numpy...")
    import numpy as np
    print("✅ numpy imported successfully")
except Exception as e:
    print(f"❌ numpy failed: {e}")

try:
    print("4. Testing ecoscope...")
    from ecoscope.io.earthranger import EarthRangerIO
    print("✅ ecoscope imported successfully")
except Exception as e:
    print(f"❌ ecoscope failed: {e}")

try:
    print("5. Testing reportlab...")
    from reportlab.lib.pagesizes import letter
    print("✅ reportlab imported successfully")
except Exception as e:
    print(f"❌ reportlab failed: {e}")

print("Import test completed!")
