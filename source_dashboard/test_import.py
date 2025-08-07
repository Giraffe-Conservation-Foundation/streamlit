#!/usr/bin/env python3
"""
Test script to debug the import issue with app.py
"""

try:
    import app
    print("✅ Successfully imported app module")
    print(f"Available attributes: {[attr for attr in dir(app) if not attr.startswith('_')]}")
    
    if hasattr(app, 'main'):
        print("✅ main function found in app module")
        print(f"main function: {app.main}")
    else:
        print("❌ main function NOT found in app module")
        
except ImportError as e:
    print(f"❌ ImportError: {e}")
except SyntaxError as e:
    print(f"❌ SyntaxError: {e}")
except Exception as e:
    print(f"❌ Other error: {e}")
