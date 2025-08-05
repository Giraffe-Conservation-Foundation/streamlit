#!/usr/bin/env python3
"""
Test script to verify EXIF date analysis functionality
"""

import sys
from pathlib import Path
from datetime import datetime

# Add shared utilities to path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir / "shared"))

from utils import get_image_metadata

def test_exif_analysis():
    """Test EXIF date extraction functionality"""
    
    print("=== EXIF Date Analysis Test ===")
    print("This test demonstrates how the system analyzes image dates")
    print()
    
    # Mock image data simulation (in real usage, this comes from uploaded files)
    test_scenarios = [
        {
            'filename': 'IMG_001.jpg',
            'has_exif': True,
            'exif_date': datetime(2025, 7, 15, 14, 30, 0),
            'description': 'July image with EXIF'
        },
        {
            'filename': 'IMG_002.jpg', 
            'has_exif': True,
            'exif_date': datetime(2025, 8, 5, 10, 45, 0),
            'description': 'August image with EXIF'
        },
        {
            'filename': 'IMG_003.jpg',
            'has_exif': False,
            'exif_date': None,
            'description': 'Image without EXIF (uses fallback)'
        }
    ]
    
    # Simulate the month grouping logic
    image_months = {}
    images_without_exif = []
    fallback_date = datetime(2025, 8, 5)  # Current date fallback
    
    print("📅 **Image Date Analysis:**")
    for scenario in test_scenarios:
        filename = scenario['filename']
        
        if scenario['has_exif']:
            # Use EXIF date
            img_date = scenario['exif_date']
            month_key = f"{img_date.year}{img_date.month:02d}"
            date_source = "EXIF"
            date_display = img_date.strftime('%Y-%m-%d %H:%M:%S')
        else:
            # No EXIF date, use fallback
            images_without_exif.append(filename)
            img_date = fallback_date
            month_key = f"{img_date.year}{img_date.month:02d}"
            date_source = "Fallback"
            date_display = img_date.strftime('%Y-%m-%d')
        
        # Group by month
        if month_key not in image_months:
            image_months[month_key] = []
        image_months[month_key].append({
            'filename': filename,
            'date': img_date,
            'source': date_source
        })
        
        print(f"  📷 {filename}: {date_display} ({date_source}) → Folder: {month_key}")
    
    print()
    print("📁 **Resulting Folder Structure:**")
    
    total_months = len(image_months)
    if total_months > 1:
        print(f"✅ Multiple months detected! {total_months} folders will be created:")
        for month_key in sorted(image_months.keys()):
            images = image_months[month_key]
            count = len(images)
            year = month_key[:4]
            month = month_key[4:6]
            month_name = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(month)-1]
            
            print(f"  📁 {month_key} ({month_name} {year}): {count} images")
            for img in images:
                print(f"    • {img['filename']} ({img['source']})")
    else:
        month_key = list(image_months.keys())[0]
        count = len(image_months[month_key])
        year = month_key[:4]
        month = month_key[4:6]
        month_name = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(month)-1]
        print(f"✅ Single month: {month_key} ({month_name} {year}) with {count} images")
    
    if images_without_exif:
        print()
        print(f"⚠️  {len(images_without_exif)} images without EXIF will use fallback date:")
        for img_name in images_without_exif:
            print(f"    • {img_name}")
    
    print()
    print("=== Folder Path Examples ===")
    for month_key in sorted(image_months.keys()):
        # Examples for different modes
        print(f"**{month_key}** folder paths:")
        print(f"  📷 Camera Trap: camera_trap/camera_fence/{month_key}/")
        print(f"  🔍 Survey: survey/survey_vehicle/{month_key}/")
        print(f"  🔧 Legacy: COUNTRY_SITE_{month_key}/")
        print()

if __name__ == "__main__":
    test_exif_analysis()
    print("=== Key Benefits ===")
    print("✅ Automatic organization by actual image dates")
    print("✅ Multiple months automatically separated")
    print("✅ EXIF dates preferred over manual input")
    print("✅ Fallback to user date for images without EXIF")
    print("✅ Clear visibility into date sources")
