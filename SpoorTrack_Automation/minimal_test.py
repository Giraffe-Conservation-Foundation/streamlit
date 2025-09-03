#!/usr/bin/env python3
"""
Minimal test to check what's causing the hang
"""

print("🧪 Starting minimal test...")

try:
    print("1. Testing basic Python...")
    import sys
    print(f"✅ Python version: {sys.version}")
    
    print("2. Testing pandas...")
    import pandas as pd
    print("✅ pandas imported")
    
    print("3. Testing matplotlib...")
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    print("✅ matplotlib imported")
    
    print("4. Testing reportlab...")
    from reportlab.lib.pagesizes import letter
    print("✅ reportlab imported")
    
    print("5. Testing ecoscope...")
    from ecoscope.io.earthranger import EarthRangerIO
    print("✅ ecoscope imported")
    
    print("6. Testing class instantiation...")
    from test_report import SpoorTrackPerformanceReport
    reporter = SpoorTrackPerformanceReport()
    print("✅ SpoorTrackPerformanceReport class created")
    
    print("\n🎉 All tests passed! Ready to run main report.")
    
except Exception as e:
    print(f"❌ Error at step: {e}")
    import traceback
    traceback.print_exc()

print("✅ Test completed successfully!")
