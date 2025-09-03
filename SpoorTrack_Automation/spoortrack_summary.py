#!/usr/bin/env python3
"""
SpoorTrack 30-Day Performance Summary - Simplified One-Off Report
===============================================================

Simple script to generate a one-time SpoorTrack performance report
for the last 30 days to assess structure and workflow.

Usage: python spoortrack_summary.py

Requirements: pip install ecoscope pandas
"""

import pandas as pd
from datetime import datetime, timedelta
import getpass
import sys
import os

print("🦒 SpoorTrack 30-Day Performance Summary")
print("=" * 50)
print("Simplified one-off report for workflow assessment\n")

def main():
    """Generate simplified 30-day SpoorTrack performance summary"""
    
    # Step 1: Test ecoscope availability
    try:
        from ecoscope.io.earthranger import EarthRangerIO
        print("✅ Ecoscope available")
    except ImportError:
        print("❌ Ecoscope not available. Please install: pip install ecoscope")
        return
    
    # Step 2: Get credentials
    print("\n🔑 EarthRanger Authentication")
    username = input("Username: ")
    password = getpass.getpass("Password: ")
    
    try:
        # Step 3: Connect to EarthRanger
        print("\n🔐 Connecting to EarthRanger...")
        er = EarthRangerIO(
            server="https://twiga.pamdas.org",
            username=username,
            password=password
        )
        print("✅ Connected successfully!")
        
        # Step 4: Find SpoorTrack sources
        print("\n🔍 Finding SpoorTrack sources...")
        sources_df = er.get_sources()
        print(f"📊 Total sources found: {len(sources_df)}")
        
        # Look for SpoorTrack sources
        spoortrack_sources = []
        for idx, row in sources_df.iterrows():
            manufacturer = str(row.get('manufacturer', ''))
            manufacturer_id = str(row.get('manufacturer_id', ''))
            name = str(row.get('name', ''))
            
            if any('spoortrack' in field.lower() for field in [manufacturer, manufacturer_id, name]):
                if not row.get('inactive', False):  # Only active sources
                    spoortrack_sources.append({
                        'id': row.get('id'),
                        'name': row.get('name', 'Unknown'),
                        'manufacturer': manufacturer,
                        'model': row.get('model', 'Unknown')
                    })
        
        print(f"✅ Found {len(spoortrack_sources)} active SpoorTrack sources")
        
        if not spoortrack_sources:
            print("⚠️ No SpoorTrack sources found")
            return
        
        # Step 5: Efficient batch observations analysis using get_source_observations
        print(f"\n📊 Analyzing performance metrics from observations table...")
        
        # Calculate date range for 30-day analysis
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        # Prepare for batch processing
        sources_to_analyze = spoortrack_sources[:10]  # First 10 for demo
        source_ids_to_analyze = [source['id'] for source in sources_to_analyze]
        
        print(f"🚀 Using efficient batch processing for {len(source_ids_to_analyze)} sources...")
        print(f"📅 Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        performance_data = []
        total_observations = 0
        total_battery_readings = 0
        battery_sum = 0
        
        try:
            # EFFICIENT: Single batch call for all sources
            print(f"⚡ Making single batch API call for all {len(source_ids_to_analyze)} sources...")
            
            all_observations = er.get_source_observations(
                source_ids=source_ids_to_analyze,
                since=start_date.isoformat(),
                until=end_date.isoformat(),
                include_source_details=True,
                relocations=False
            )
            
            print(f"✅ Retrieved {len(all_observations) if not all_observations.empty else 0} total observations in single call")
            
            # Process each source from the batch results
            for i, source in enumerate(sources_to_analyze, 1):
                print(f"  📡 Processing {i}/10: {source['name']}")
                
                # Filter observations for this specific source
                if not all_observations.empty:
                    source_observations = all_observations[all_observations['source'] == source['id']]
                else:
                    source_observations = pd.DataFrame()
                
                if not source_observations.empty:
                    obs_count = len(source_observations)
                    locations_per_day = round(obs_count / 30, 1)
                    
                    # Find battery voltage from multiple possible sources
                    mean_battery = None
                    battery_values = []
                    
                    # Method 1: Direct battery columns
                    battery_cols = [col for col in source_observations.columns if 'battery' in col.lower() or 'voltage' in col.lower()]
                    if battery_cols:
                        battery_data = pd.to_numeric(source_observations[battery_cols[0]], errors='coerce').dropna()
                        battery_values.extend(battery_data.tolist())
                    
                    # Method 2: Check additional data field for battery info
                    if 'additional' in source_observations.columns:
                        for _, obs in source_observations.iterrows():
                            if obs['additional'] and isinstance(obs['additional'], dict):
                                for battery_field in ['battery', 'battery_voltage', 'voltage', 'batt', 'battery_v']:
                                    if battery_field in obs['additional']:
                                        try:
                                            battery_val = float(obs['additional'][battery_field])
                                            if 0 < battery_val < 10:  # Reasonable voltage range
                                                battery_values.append(battery_val)
                                                break
                                        except (ValueError, TypeError):
                                            continue
                    
                    # Calculate mean battery if we found any values
                    if battery_values:
                        mean_battery = round(sum(battery_values) / len(battery_values), 2)
                        battery_sum += mean_battery
                        total_battery_readings += 1
                    
                    total_observations += obs_count
                    
                    # Determine status based on battery level
                    if mean_battery:
                        if mean_battery >= 3.5:
                            status = 'Good'
                        elif mean_battery >= 3.0:
                            status = 'Warning'
                        else:
                            status = 'Critical'
                    else:
                        status = 'Unknown'
                    
                    performance_data.append({
                        'name': source['name'],
                        'id': source['id'],
                        'observations': obs_count,
                        'locations_per_day': locations_per_day,
                        'mean_battery': mean_battery,
                        'battery_readings': len(battery_values),
                        'status': status
                    })
                    
                    battery_info = f"{mean_battery}V ({len(battery_values)} readings)" if mean_battery else "No battery data"
                    print(f"     📊 {obs_count:,} obs | {locations_per_day} locs/day | {battery_info}")
                    
                else:
                    print(f"     ⚠️ No observations found")
                    performance_data.append({
                        'name': source['name'],
                        'id': source['id'],
                        'observations': 0,
                        'locations_per_day': 0,
                        'mean_battery': None,
                        'battery_readings': 0,
                        'status': 'No Data'
                    })
        
        except Exception as e:
            print(f"❌ Batch processing failed: {str(e)}")
            print(f"🔄 Falling back to individual source processing...")
            
            # Fallback: Individual calls if batch fails
            for i, source in enumerate(sources_to_analyze, 1):
                print(f"  📡 Analyzing {i}/10: {source['name']}")
                
                try:
                    observations = er.get_source_observations(
                        source_ids=[source['id']], 
                        since=start_date.isoformat(),
                        until=end_date.isoformat(),
                        relocations=False
                    )
                    
                    if observations is not None and not observations.empty:
                        obs_count = len(observations)
                        locations_per_day = round(obs_count / 30, 1)
                        
                        # Find battery voltage columns
                        battery_cols = [col for col in observations.columns if 'battery' in col.lower() or 'voltage' in col.lower()]
                        mean_battery = None
                        
                        if battery_cols:
                            battery_values = pd.to_numeric(observations[battery_cols[0]], errors='coerce').dropna()
                            if not battery_values.empty:
                                mean_battery = round(battery_values.mean(), 2)
                                battery_sum += mean_battery
                                total_battery_readings += 1
                        
                        total_observations += obs_count
                        
                        performance_data.append({
                            'name': source['name'],
                            'id': source['id'],
                            'observations': obs_count,
                            'locations_per_day': locations_per_day,
                            'mean_battery': mean_battery,
                            'battery_readings': len(battery_values) if battery_cols and not battery_values.empty else 0,
                            'status': 'Good' if mean_battery and mean_battery >= 3.5 else 'Warning' if mean_battery and mean_battery >= 3.0 else 'Critical' if mean_battery else 'Unknown'
                        })
                    else:
                        performance_data.append({
                            'name': source['name'],
                            'id': source['id'],
                            'observations': 0,
                            'locations_per_day': 0,
                            'mean_battery': None,
                            'battery_readings': 0,
                            'status': 'No Data'
                        })
                        
                except Exception as e:
                    print(f"    ⚠️ Error getting observations for {source['name']}: {str(e)}")
                    performance_data.append({
                        'name': source['name'],
                        'id': source['id'],
                        'observations': 0,
                        'locations_per_day': 0,
                        'mean_battery': None,
                        'battery_readings': 0,
                        'status': 'Error'
                    })
        
        # Step 6: Enhanced performance report
        print(f"\n📋 Generating enhanced 30-day performance summary...")
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        print(f"📅 Analysis period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        print(f"📊 Analyzed {len(performance_data)} sources with observations data...\n")
        
        # Step 7: Enhanced summary table
        print("=" * 100)
        print("SPOORTRACK 30-DAY PERFORMANCE SUMMARY WITH METRICS")
        print("Giraffe Conservation Foundation")
        print("=" * 100)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Period: Last 30 days")
        print(f"Sources: {len(spoortrack_sources)} total SpoorTrack units ({len(performance_data)} analyzed)\n")
        
        # Enhanced tabular output with performance metrics
        print("Source Performance Analysis:")
        print("-" * 115)
        print(f"{'Source Name':<25} {'Source ID':<12} {'Total Obs':<10} {'Locs/Day':<10} {'Battery(V)':<12} {'Bat.Reads':<10} {'Status':<10}")
        print("-" * 115)
        
        for data in performance_data:
            name = data['name'][:24] if len(data['name']) > 24 else data['name']
            battery_str = f"{data['mean_battery']:.2f}" if data['mean_battery'] else "N/A"
            bat_reads = f"{data.get('battery_readings', 0)}"
            print(f"{name:<25} {data['id']:<12} {data['observations']:<10} {data['locations_per_day']:<10} {battery_str:<12} {bat_reads:<10} {data['status']:<10}")
        
        if len(spoortrack_sources) > len(performance_data):
            print(f"... and {len(spoortrack_sources) - len(performance_data)} more sources (not analyzed for metrics)")
        
        print("-" * 115)
        
        # Step 8: Enhanced summary statistics
        print(f"\nPERFORMANCE METRICS SUMMARY")
        print("-" * 50)
        
        # Calculate overall metrics
        valid_battery_data = [d for d in performance_data if d['mean_battery'] is not None]
        valid_location_data = [d for d in performance_data if d['observations'] > 0]
        
        if valid_battery_data:
            overall_mean_battery = round(sum(d['mean_battery'] for d in valid_battery_data) / len(valid_battery_data), 2)
            print(f"📋 Overall Mean Battery Voltage: {overall_mean_battery}V")
        else:
            print(f"📋 Overall Mean Battery Voltage: No data available")
        
        if valid_location_data:
            overall_mean_locations = round(sum(d['locations_per_day'] for d in valid_location_data) / len(valid_location_data), 1)
            total_observations_analyzed = sum(d['observations'] for d in valid_location_data)
            print(f"📍 Overall Mean Locations/Day: {overall_mean_locations}")
            print(f"📊 Total Observations Analyzed: {total_observations_analyzed:,}")
        else:
            print(f"📍 Overall Mean Locations/Day: No data available")
        
        # Battery status distribution
        status_counts = {}
        for data in performance_data:
            status = data['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"\n🔋 Battery Status Distribution:")
        for status, count in status_counts.items():
            print(f"   {status}: {count} sources")
        
        print(f"\n📈 SUMMARY STATISTICS")
        print(f"- Total SpoorTrack Sources Found: {len(spoortrack_sources)}")
        print(f"- Sources Analyzed for Metrics: {len(performance_data)}")
        print(f"- Analysis Period: 30 days")
        print(f"- Data Source: EarthRanger observations table")
        
        if len(spoortrack_sources) != 75:
            print(f"\n⚠️ NOTE: Expected ~75 SpoorTrack sources, found {len(spoortrack_sources)}")
            print(f"   This could be due to:")
            print(f"   - Different naming conventions in manufacturer fields")
            print(f"   - Inactive/decommissioned sources")
            print(f"   - Sources not yet deployed")
        
        print(f"\n✅ Enhanced performance analysis completed!")
        print(f"\n📊 METRICS INCLUDED:")
        print(f"   ✅ Mean battery voltage over time (from observations)")
        print(f"   ✅ Mean locations per day (from observations count)")
        print(f"   ✅ Source status classification")
        print(f"   ✅ Performance distribution analysis")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print(f"\n🎉 Workflow assessment complete!")
    else:
        print(f"\n❌ Report failed. Check credentials and connection.")
