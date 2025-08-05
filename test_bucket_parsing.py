#!/usr/bin/env python3
"""Test script for bucket parsing functionality"""

def extract_countries_sites_from_buckets(bucket_names):
    """Extract country and site combinations from bucket names following gcf_country_site pattern"""
    countries_sites = {}
    
    for bucket_name in bucket_names:
        # Check if bucket follows the gcf_country_site pattern
        if bucket_name.lower().startswith('gcf'):
            parts = bucket_name.lower().split('_')
            # Expected pattern: gcf_country_site or variations with separators
            if len(parts) >= 3:
                # Extract country and site from bucket name
                country = parts[1].upper()  # Convert to uppercase for consistency
                site = parts[2].upper()     # Convert to uppercase for consistency
                
                # Add to countries_sites dictionary
                if country not in countries_sites:
                    countries_sites[country] = []
                
                if site not in countries_sites[country]:
                    countries_sites[country].append(site)
            
            # Also handle patterns with dashes (gcf-country-site)
            elif '-' in bucket_name:
                parts = bucket_name.lower().split('-')
                if len(parts) >= 3:
                    country = parts[1].upper()
                    site = parts[2].upper()
                    
                    if country not in countries_sites:
                        countries_sites[country] = []
                    
                    if site not in countries_sites[country]:
                        countries_sites[country].append(site)
    
    # Sort countries and sites for consistent display
    for country in countries_sites:
        countries_sites[country].sort()
    
    return countries_sites

if __name__ == "__main__":
    # Test with example bucket names
    test_buckets = [
        'gcf_ago_llnp',
        'gcf_ago_ionp', 
        'gcf_nam_ehgr',
        'gcf_nam_uiifa',
        'gcf_nam_nanw',
        'gcf_ken_mmnr',
        'gcf_ken_runp',
        'gcf-tza-tarangire',  # Test dash format
        'other_bucket',        # Should be ignored
        'gcf_uga_mfnp'        # Uganda example
    ]

    result = extract_countries_sites_from_buckets(test_buckets)
    print('✅ Extracted countries and sites:')
    for country, sites in sorted(result.items()):
        print(f'   {country}: {sites}')
    print(f'\n📊 Total: {len(result)} countries, {sum(len(sites) for sites in result.values())} locations')
    
    print('\n🔍 Bucket processing details:')
    for bucket in test_buckets:
        if bucket.lower().startswith('gcf'):
            if '_' in bucket and len(bucket.split('_')) >= 3:
                parts = bucket.split('_')
                print(f'   ✅ {bucket} → {parts[1].upper()}-{parts[2].upper()}')
            elif '-' in bucket and len(bucket.split('-')) >= 3:
                parts = bucket.split('-')
                print(f'   ✅ {bucket} → {parts[1].upper()}-{parts[2].upper()}')
            else:
                print(f'   ⚠️ {bucket} → invalid pattern')
        else:
            print(f'   ❌ {bucket} → not GCF pattern (ignored)')
