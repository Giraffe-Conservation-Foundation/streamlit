#!/usr/bin/env python3
"""Inspect ecoscope's EarthRangerIO object structure"""

import getpass
from ecoscope.io import EarthRangerIO

username = input("Username: ").strip()
password = getpass.getpass("Password: ")

er_io = EarthRangerIO(
    server="https://twiga.pamdas.org",
    username=username,
    password=password
)

print("✅ Connected via ecoscope\n")
print("=" * 60)
print("EarthRangerIO attributes:")
print("=" * 60)

# Get all attributes
attrs = [attr for attr in dir(er_io) if not attr.startswith('__')]
for attr in sorted(attrs):
    try:
        val = getattr(er_io, attr)
        if not callable(val):
            print(f"  {attr}: {type(val).__name__}")
    except:
        pass

print("\n" + "=" * 60)
print("Checking for common session/client attributes:")
print("=" * 60)

checks = ['session', '_session', 'client', '_client', 'erclient', 
          'service', 'http', 'auth', 'token', 'headers']

for check in checks:
    if hasattr(er_io, check):
        val = getattr(er_io, check)
        print(f"✅ Has '{check}': {type(val).__name__}")
        
        # If it's an object, show its attributes
        if not callable(val) and hasattr(val, '__dict__'):
            sub_attrs = [a for a in dir(val) if not a.startswith('_')][:5]
            if sub_attrs:
                print(f"   Sub-attributes: {', '.join(sub_attrs)}")
    else:
        print(f"❌ No '{check}'")

print("\n" + "=" * 60)
print("Checking methods that might help:")
print("=" * 60)

methods = ['get', 'post', 'patch', 'put', 'delete', 'request']
for method in methods:
    if hasattr(er_io, method):
        print(f"✅ Has method: {method}()")
