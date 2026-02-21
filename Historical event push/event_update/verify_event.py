#!/usr/bin/env python3
"""
Verify an event exists before trying to update it
"""

import getpass
from ecoscope.io import EarthRangerIO

print("🔍 Event Verification Tool")
print("=" * 60)

# Get event ID to verify
event_id = input("Enter Event UUID to verify: ").strip()

if not event_id:
    print("❌ No event ID provided")
    exit(1)

# Get credentials
username = input("Username: ").strip()
password = getpass.getpass("Password: ")

# Connect
print("\n🔐 Connecting to EarthRanger...")
try:
    er_io = EarthRangerIO(
        server="https://twiga.pamdas.org",
        username=username,
        password=password
    )
    print("✅ Connected!\n")
except Exception as e:
    print(f"❌ Connection failed: {e}")
    exit(1)

# Try to fetch the event
print(f"🔍 Looking for event: {event_id}")
try:
    events = er_io.get_events(event_ids=[event_id])
    
    if events.empty:
        print(f"\n❌ Event NOT FOUND")
        print(f"   The event ID {event_id} does not exist in EarthRanger")
        print(f"\n💡 To find valid event IDs, run: python get_event_ids.py")
    else:
        event = events.iloc[0]
        print(f"\n✅ Event FOUND!")
        print("=" * 60)
        print(f"Title: {event.get('title', 'N/A')}")
        print(f"Event Type: {event.get('event_type', 'N/A')}")
        print(f"Time: {event.get('time', 'N/A')}")
        print(f"State: {event.get('state', 'N/A')}")
        print(f"Priority: {event.get('priority', 'N/A')}")
        
        if 'event_details' in event and event['event_details']:
            print(f"\nEvent Details:")
            for key, value in event['event_details'].items():
                print(f"  {key}: {value}")
        
        print("\n✅ This event can be updated!")
        print(f"\n💡 To update this event:")
        print(f"   1. Edit single_event_test.csv")
        print(f"   2. Set event_id to: {event_id}")
        print(f"   3. Set the fields you want to update")
        print(f"   4. Run: python test_update.py")
        
except Exception as e:
    print(f"\n❌ Error fetching event: {e}")
    import traceback
    traceback.print_exc()
