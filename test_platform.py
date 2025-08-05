#!/usr/bin/env python3
"""
Test script to verify Twiga Tools platform functionality
Tests that individual apps can be loaded without set_page_config conflicts
"""

import sys
import os
from pathlib import Path
import re

def test_set_page_config_removal():
    """Test that set_page_config calls are properly handled in individual apps"""
    current_dir = Path(__file__).parent
    
    apps_to_test = [
        current_dir / "wildbook_id_generator" / "app.py",
        current_dir / "image_management" / "app.py",
        current_dir / "nanw_dashboard" / "app.py"
    ]
    
    print("🧪 Testing set_page_config removal in individual apps...")
    print("=" * 60)
    
    all_passed = True
    
    for app_path in apps_to_test:
        if app_path.exists():
            print(f"\n📱 Testing: {app_path.parent.name}/{app_path.name}")
            
            try:
                with open(app_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Check for uncommented set_page_config calls
                lines = content.split('\n')
                config_lines = []
                
                for i, line in enumerate(lines, 1):
                    if 'st.set_page_config(' in line and not line.strip().startswith('#'):
                        config_lines.append((i, line.strip()))
                
                if config_lines:
                    print(f"   ❌ Found uncommented set_page_config calls:")
                    for line_num, line_content in config_lines:
                        print(f"      Line {line_num}: {line_content}")
                    all_passed = False
                else:
                    print(f"   ✅ No uncommented set_page_config calls found")
                    
            except Exception as e:
                print(f"   ❌ Error reading file: {e}")
                all_passed = False
        else:
            print(f"   ⚠️  File not found: {app_path}")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All tests passed! Individual apps should work in unified platform.")
    else:
        print("❌ Some tests failed. Check the issues above.")
    
    return all_passed

def test_main_app_config():
    """Test that main app has proper set_page_config"""
    current_dir = Path(__file__).parent
    main_app = current_dir / "twiga_tools.py"
    
    print(f"\n🧪 Testing main app configuration...")
    print("=" * 60)
    
    if main_app.exists():
        try:
            with open(main_app, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Check for set_page_config in main app
            if 'st.set_page_config(' in content:
                print("✅ Main app has set_page_config configuration")
                
                # Check if it's only called once
                config_count = content.count('st.set_page_config(')
                if config_count == 1:
                    print(f"✅ set_page_config called exactly once ({config_count} times)")
                else:
                    print(f"⚠️  set_page_config called {config_count} times (should be 1)")
                
                return True
            else:
                print("❌ Main app missing set_page_config")
                return False
                
        except Exception as e:
            print(f"❌ Error reading main app: {e}")
            return False
    else:
        print("❌ Main app not found")
        return False

def test_code_filtering_logic():
    """Test the code filtering logic used in the main app"""
    print(f"\n🧪 Testing code filtering logic...")
    print("=" * 60)
    
    # Sample code with set_page_config
    test_code = '''
import streamlit as st

st.set_page_config(
    page_title="Test App",
    page_icon="🦒"
)

st.title("Test Application")
st.write("Hello World")
'''
    
    # Apply the same filtering logic used in twiga_tools.py
    lines = test_code.split('\n')
    filtered_lines = []
    skip_config = False
    
    for line in lines:
        if 'st.set_page_config(' in line:
            skip_config = True
            continue
        elif skip_config and ')' in line and not line.strip().startswith('#'):
            skip_config = False
            continue
        elif not skip_config:
            filtered_lines.append(line)
    
    cleaned_code = '\n'.join(filtered_lines)
    
    # Check if set_page_config was removed
    if 'st.set_page_config(' not in cleaned_code:
        print("✅ Code filtering logic works correctly")
        print("✅ set_page_config calls are properly removed at runtime")
        return True
    else:
        print("❌ Code filtering logic failed")
        print("❌ set_page_config calls were not removed")
        return False

if __name__ == "__main__":
    print("🦒 Twiga Tools Platform Test Suite")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(test_set_page_config_removal())
    results.append(test_main_app_config())
    results.append(test_code_filtering_logic())
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 ALL TESTS PASSED ({passed}/{total})")
        print("✅ Twiga Tools platform should work without set_page_config conflicts!")
        sys.exit(0)
    else:
        print(f"❌ SOME TESTS FAILED ({passed}/{total})")
        print("🔧 Please review the issues above before deploying.")
        sys.exit(1)
