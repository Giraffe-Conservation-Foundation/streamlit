#!/usr/bin/env python3
"""
Test script to verify camera trap naming convention
"""

import sys
from pathlib import Path
from datetime import datetime

# Add shared utilities to path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir / "shared"))

from utils import generate_standardized_filename

def test_camera_trap_naming():
    """Test camera trap naming convention"""
    
    # Test data
    original_filename = "IMG_0123.jpg"
    country = "NAMIBIA"
    site = "ETOSHA"
    survey_date = datetime(2025, 8, 5)
    station = "ST01"
    camera = "CAM02"
    
    # Generate camera trap filename
    camera_trap_name = generate_standardized_filename(
        original_filename=original_filename,
        country=country,
        site=site,
        survey_date=survey_date,
        index=1,
        photographer=None,  # Not used for camera traps
        image_metadata=None,
        station=station,
        camera=camera
    )
    
    print("=== Camera Trap Naming Test ===")
    print(f"Original: {original_filename}")
    print(f"Country: {country}")
    print(f"Site: {site}")
    print(f"Station: {station}")
    print(f"Camera: {camera}")
    print(f"Date: {survey_date.strftime('%Y-%m-%d')}")
    print(f"Expected format: COUNTRY_SITE_STATION_CAMERA_YYYYMMDD_ORIGINAL")
    print(f"Generated: {camera_trap_name}")
    print(f"Expected: NAMIBIA_ETOSHA_ST01_CAM02_20250805_IMG_0123.jpg")
    
    # Verify format
    expected = "NAMIBIA_ETOSHA_ST01_CAM02_20250805_IMG_0123.jpg"
    if camera_trap_name == expected:
        print("✅ PASS: Camera trap naming is correct!")
    else:
        print("❌ FAIL: Camera trap naming is incorrect!")
        print(f"   Got: {camera_trap_name}")
        print(f"   Expected: {expected}")

def test_survey_naming():
    """Test survey naming convention for comparison"""
    
    # Test data
    original_filename = "DSC_4567.jpg"
    country = "KENYA"
    site = "SAMBURU"
    survey_date = datetime(2025, 8, 5)
    photographer = "AB"
    
    # Generate survey filename (no station/camera)
    survey_name = generate_standardized_filename(
        original_filename=original_filename,
        country=country,
        site=site,
        survey_date=survey_date,
        index=1,
        photographer=photographer,
        image_metadata=None,
        station=None,  # Not used for surveys
        camera=None    # Not used for surveys
    )
    
    print("\n=== Survey Naming Test ===")
    print(f"Original: {original_filename}")
    print(f"Country: {country}")
    print(f"Site: {site}")
    print(f"Photographer: {photographer}")
    print(f"Date: {survey_date.strftime('%Y-%m-%d')}")
    print(f"Expected format: COUNTRY_SITE_YYYYMMDD_INITIALS_ORIGINAL")
    print(f"Generated: {survey_name}")
    print(f"Expected: KENYA_SAMBURU_20250805_AB_DSC_4567.jpg")
    
    # Verify format
    expected = "KENYA_SAMBURU_20250805_AB_DSC_4567.jpg"
    if survey_name == expected:
        print("✅ PASS: Survey naming is correct!")
    else:
        print("❌ FAIL: Survey naming is incorrect!")
        print(f"   Got: {survey_name}")
        print(f"   Expected: {expected}")

if __name__ == "__main__":
    test_camera_trap_naming()
    test_survey_naming()
    print("\n=== Test Summary ===")
    print("Camera trap format: COUNTRY_SITE_STATION_CAMERA_YYYYMMDD_ORIGINAL")
    print("Survey format: COUNTRY_SITE_YYYYMMDD_INITIALS_ORIGINAL")
    print("Both formats preserve original filename and use date from EXIF or survey date")
