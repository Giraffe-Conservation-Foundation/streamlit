#!/usr/bin/env python3
"""
Test script to verify SpoorTrack performance report fixes
"""

import sys
import os

def test_imports():
    """Test all required imports"""
    print("🧪 Testing imports...")
    
    try:
        import pandas as pd
        print("✅ pandas imported successfully")
    except ImportError as e:
        print(f"❌ pandas failed: {e}")
        return False

    try:
        import matplotlib.pyplot as plt
        print("✅ matplotlib imported successfully")
    except ImportError as e:
        print(f"❌ matplotlib failed: {e}")
        return False

    try:
        import numpy as np
        print("✅ numpy imported successfully")
    except ImportError as e:
        print(f"❌ numpy failed: {e}")
        return False

    try:
        from ecoscope.io.earthranger import EarthRangerIO
        print("✅ ecoscope imported successfully")
    except ImportError as e:
        print(f"❌ ecoscope failed: {e}")
        return False

    try:
        from reportlab.lib.pagesizes import letter
        print("✅ reportlab imported successfully")
    except ImportError as e:
        print(f"❌ reportlab failed: {e}")
        return False

    return True

def test_report_class():
    """Test the SpoorTrackPerformanceReport class instantiation"""
    print("\n🧪 Testing SpoorTrackPerformanceReport class...")
    
    try:
        # Import the fixed report class
        from test_report import SpoorTrackPerformanceReport
        
        # Create an instance
        reporter = SpoorTrackPerformanceReport()
        print("✅ SpoorTrackPerformanceReport class instantiated successfully")
        
        # Test directory creation
        reports_dir = os.path.join(os.path.dirname(__file__), 'reports')
        if os.path.exists(reports_dir):
            print("✅ Reports directory exists")
        else:
            print("📁 Reports directory will be created when needed")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to instantiate SpoorTrackPerformanceReport: {e}")
        return False

def main():
    """Run all tests"""
    print("🦒 SpoorTrack Performance Report - Bug Fix Validation")
    print("=" * 60)
    
    all_tests_passed = True
    
    # Test imports
    if not test_imports():
        all_tests_passed = False
    
    # Test report class
    if not test_report_class():
        all_tests_passed = False
    
    print("\n" + "=" * 60)
    if all_tests_passed:
        print("🎉 All tests passed! The SpoorTrack report should work now.")
        print("\n💡 Next steps:")
        print("   1. Run: python test_report.py")
        print("   2. Enter your EarthRanger credentials")
        print("   3. Wait for the 90-day analysis to complete")
        print("   4. Check the reports/ folder for PDF output")
    else:
        print("❌ Some tests failed. Please check the error messages above.")
        print("\n🔧 Troubleshooting:")
        print("   - Ensure all packages are installed: pip install ecoscope pandas matplotlib reportlab")
        print("   - Check your Python environment is activated")
        print("   - Verify network connectivity for package installation")

if __name__ == "__main__":
    main()
