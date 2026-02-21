#!/usr/bin/env python3
"""Check ecoscope API for patch_event method"""

from ecoscope.io import EarthRangerIO
import inspect

# Get all methods
methods = [m for m in dir(EarthRangerIO) if not m.startswith('_')]
print("Available methods in EarthRangerIO:")
for m in sorted(methods):
    print(f"  {m}")

print(f"\nhas patch_event: {hasattr(EarthRangerIO, 'patch_event')}")
print(f"has post_event: {hasattr(EarthRangerIO, 'post_event')}")

# Check for update-related methods
update_methods = [m for m in methods if 'patch' in m.lower() or 'update' in m.lower()]
print(f"\nUpdate-related methods: {update_methods}")
