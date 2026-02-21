"""Export with specific species and location filters

This shows how to filter your exports by:
- Species/genus
- Location (country, location ID, GPS coordinates)
- Date ranges
- Combined filters
"""

import json
import csv
from datetime import datetime
from pywildbook import WildbookClient
from pywildbook.queries import (
    match_all,
    filter_by_species,
    filter_by_location,
    filter_by_year_range,
    filter_by_date_range,
    combine_queries,
    filter_by_sex,
    missing,
    exists
)


def export_to_csv(data, filename):
    """Helper to export data to CSV"""
    if not data:
        print("  No data to export")
        return
    
    fieldnames = sorted(set().union(*[item.keys() for item in data]))
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"  ✓ Exported {len(data)} records to {filename}")


def main():
    print("=" * 70)
    print("Export with Species and Location Filters")
    print("=" * 70)
    print()
    
    client = WildbookClient()
    client.login()
    print(f"✓ Connected to: {client.base_url}\n")
    
    # =======================================================================
    # SPECIES FILTERS
    # =======================================================================
    
    print("=" * 70)
    print("1. Filter by Species Only")
    print("=" * 70)
    
    # Method 1: Just species name
    query1 = filter_by_species('camelopardalis')
    results = client.search_encounters(query1, size=50)
    print(f"Species 'camelopardalis': {results.get('total', 0)} encounters")
    export_to_csv(results.get('hits', []), 'export_camelopardalis.csv')
    print()
    
    # Method 2: Full binomial name (auto-splits)
    query2 = filter_by_species('Giraffa camelopardalis')
    results = client.search_encounters(query2, size=50)
    print(f"Giraffa camelopardalis: {results.get('total', 0)} encounters")
    export_to_csv(results.get('hits', []), 'export_giraffa_camelopardalis.csv')
    print()
    
    # Method 3: Genus and species separately
    query3 = filter_by_species('camelopardalis', genus='Giraffa')
    results = client.search_encounters(query3, size=50)
    print(f"Genus='Giraffa', species='camelopardalis': {results.get('total', 0)} encounters")
    print()
    
    # Method 4: Just genus (search any Giraffa)
    query4 = filter_by_species('Giraffa')
    results = client.search_encounters(query4, size=50)
    print(f"Any Giraffa: {results.get('total', 0)} encounters")
    print()
    
    # =======================================================================
    # LOCATION FILTERS
    # =======================================================================
    
    print("=" * 70)
    print("2. Filter by Location")
    print("=" * 70)
    
    # Method 1: By country
    query_kenya = filter_by_location(country='Kenya')
    results = client.search_encounters(query_kenya, size=50)
    print(f"Country='Kenya': {results.get('total', 0)} encounters")
    export_to_csv(results.get('hits', []), 'export_kenya.csv')
    print()
    
    # Method 2: By location ID
    query_loc_id = filter_by_location(location_id='LOC123')
    results = client.search_encounters(query_loc_id, size=50)
    print(f"Location ID='LOC123': {results.get('total', 0)} encounters")
    print()
    
    # Method 3: By GPS bounding box (e.g., around Nairobi area)
    query_gps = filter_by_location(
        bounding_box={
            'top_left': {'lat': -1.0, 'lon': 36.5},      # Northwest corner
            'bottom_right': {'lat': -1.5, 'lon': 37.0}   # Southeast corner
        }
    )
    results = client.search_encounters(query_gps, size=50)
    print(f"GPS bounding box: {results.get('total', 0)} encounters")
    export_to_csv(results.get('hits', []), 'export_gps_area.csv')
    print()
    
    # Method 4: Multiple countries
    query_multi = filter_by_location(country=['Kenya', 'Tanzania', 'Uganda'])
    results = client.search_encounters(query_multi, size=50)
    print(f"Multiple countries: {results.get('total', 0)} encounters")
    print()
    
    # =======================================================================
    # COMBINED FILTERS
    # =======================================================================
    
    print("=" * 70)
    print("3. Combine Species + Location + Date")
    print("=" * 70)
    
    # Example: Giraffes in Kenya from 2020-2026
    species = filter_by_species('Giraffa')
    location = filter_by_location(country='Kenya')
    date_range = filter_by_year_range(2020, 2026)
    
    combined = combine_queries(species, location, date_range, operator='must')
    results = client.search_encounters(combined, size=100)
    
    print(f"Giraffes in Kenya (2020-2026): {results.get('total', 0)} encounters")
    export_to_csv(results.get('hits', []), 'export_kenya_giraffes_2020_2026.csv')
    
    # Save this query for reuse
    with open('kenya_giraffes_query.json', 'w') as f:
        json.dump(combined, f, indent=2)
    print(f"  ✓ Query saved to kenya_giraffes_query.json")
    print()
    
    # =======================================================================
    # MORE COMPLEX FILTERS
    # =======================================================================
    
    print("=" * 70)
    print("4. Complex Filtered Exports")
    print("=" * 70)
    
    # Example: Female giraffes in specific area without individual ID
    filters = combine_queries(
        filter_by_species('Giraffa'),
        filter_by_location(country='Kenya'),
        filter_by_sex('female'),
        missing('individualId'),
        operator='must'
    )
    results = client.search_encounters(filters, size=100)
    print(f"Unidentified female Giraffes in Kenya: {results.get('total', 0)}")
    export_to_csv(results.get('hits', []), 'export_unidentified_females_kenya.csv')
    print()
    
    # Example: Recent sightings in date range
    recent = combine_queries(
        filter_by_species('Giraffa camelopardalis'),
        filter_by_date_range(start_date='2023-01-01', end_date='2026-02-17'),
        operator='must'
    )
    results = client.search_encounters(recent, size=100)
    print(f"Recent Giraffa camelopardalis (2023-present): {results.get('total', 0)}")
    export_to_csv(results.get('hits', []), 'export_recent_giraffes.csv')
    print()
    
    # =======================================================================
    # GET ALL RESULTS FOR SPECIFIC FILTER
    # =======================================================================
    
    print("=" * 70)
    print("5. Export ALL Results for a Specific Filter")
    print("=" * 70)
    
    # Define your filter
    my_filter = combine_queries(
        filter_by_species('Giraffa'),
        filter_by_year_range(2023, 2026),
        operator='must'
    )
    
    # Get all results with pagination
    print("Fetching all results (this may take a moment)...")
    all_results = []
    offset = 0
    batch_size = 100
    
    while True:
        batch = client.search_encounters(my_filter, from_=offset, size=batch_size)
        hits = batch.get('hits', [])
        
        if not hits:
            break
        
        all_results.extend(hits)
        offset += batch_size
        print(f"  Retrieved {len(all_results)} so far...")
        
        # Stop if we got everything
        if len(all_results) >= batch.get('total', 0):
            break
        
        # Safety limit
        if len(all_results) >= 1000:
            print("  (Stopped at 1000 for safety)")
            break
    
    print(f"✓ Total retrieved: {len(all_results)} encounters")
    export_to_csv(all_results, 'export_ALL_giraffes_2023_2026.csv')
    print()
    
    # =======================================================================
    # REFERENCE: COMMON FILTER PATTERNS
    # =======================================================================
    
    print("=" * 70)
    print("Quick Reference: Common Filter Patterns")
    print("=" * 70)
    print("""
SPECIES:
  filter_by_species('Giraffa')                    # Any Giraffa
  filter_by_species('camelopardalis')             # By species name
  filter_by_species('Giraffa camelopardalis')     # Full binomial
  filter_by_species('camelopardalis', genus='Giraffa')  # Explicit

LOCATION:
  filter_by_location(country='Kenya')
  filter_by_location(country=['Kenya', 'Tanzania'])
  filter_by_location(location_id='LOC123')
  filter_by_location(bounding_box={'top_left': {...}, 'bottom_right': {...}})

DATE:
  filter_by_year_range(2020, 2023)
  filter_by_date_range('2023-01-01', '2023-12-31')
  filter_by_date_range(start_date='2023-01-01')  # Open-ended

OTHER:
  filter_by_sex('female')
  missing('individualId')                         # No ID assigned
  exists('individualId')                          # Has ID assigned

COMBINE:
  combine_queries(filter1, filter2, operator='must')      # AND
  combine_queries(filter1, filter2, operator='should')    # OR
  combine_queries(filter1, filter2, operator='must_not')  # NOT
    """)
    
    print("=" * 70)
    print("✓ Export examples complete!")
    print("=" * 70)
    
    client.logout()


if __name__ == '__main__':
    main()
