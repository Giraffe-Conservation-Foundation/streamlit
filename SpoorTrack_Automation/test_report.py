#!/usr/bin/env python3
"""
SpoorTrack Performance Report Generator
=====================================

Generates performance reports for all deployed SpoorTrack units using ecoscope API.
Analyzes battery levels, transmission rates, and location data quality.

Usage:
    python test_report.py

Requirements:
    pip install pandas matplotlib reportlab ecoscope geopandas

Author: Giraffe Conservation Foundation
Date: August 2025
"""

# Remove streamlit import for standalone use
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import numpy as np
from io import BytesIO
import getpass
import sys
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Handle imports for both standalone and streamlit use
try:
    from ecoscope.io.earthranger import EarthRangerIO
    ECOSCOPE_AVAILABLE = True
    print("✅ Ecoscope package available")
except ImportError as e:
    ECOSCOPE_AVAILABLE = False
    print(f"⚠️ Ecoscope package not available: {e}")

# PDF generation imports
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    REPORTLAB_AVAILABLE = True
    print("✅ ReportLab package available")
except ImportError as e:
    REPORTLAB_AVAILABLE = False
    print(f"⚠️ ReportLab not available: {e}")

class SpoorTrackPerformanceReport:
    """Generate comprehensive SpoorTrack performance reports"""
    
    def __init__(self, server_url="https://twiga.pamdas.org"):
        self.server_url = server_url
        self.er = None
        self.data = {}
        
    def authenticate(self, username=None, password=None):
        """Authenticate with EarthRanger using ecoscope"""
        if not ECOSCOPE_AVAILABLE:
            raise Exception("Ecoscope package is required but not available.")
        
        try:
            # Get credentials if not provided
            if not username:
                username = input("EarthRanger Username: ")
            if not password:
                password = getpass.getpass("EarthRanger Password: ")
            
            print("🔐 Authenticating with EarthRanger...")
            
            self.er = EarthRangerIO(
                server=self.server_url,
                username=username,
                password=password
            )
            
            # Test connection with subjects (avoid geospatial issues)
            try:
                test_subjects = self.er.get_subjects(limit=1)
                print("✅ Authentication successful!")
                return True
            except Exception as geo_error:
                if "geospatial method" in str(geo_error) or "geometry column" in str(geo_error):
                    print("✅ Authentication successful! (Geometry config differences ignored)")
                    return True
                else:
                    raise geo_error
                    
        except Exception as e:
            print(f"❌ Authentication failed: {str(e)}")
            return False
    
    def find_spoortrack_sources(self):
        """Find all deployed SpoorTrack sources (manufac==spoortrack)"""
        try:
            print("🔍 Searching for SpoorTrack sources...")
            
            # Get all sources from EarthRanger
            sources_df = self.er.get_sources()
            
            # Debug: Show structure of sources DataFrame
            print(f"📊 Total sources found: {len(sources_df)}")
            print(f"📊 Source columns: {list(sources_df.columns)}")
            
            # Check for available manufacturers
            if 'manufacturer' in sources_df.columns:
                manufacturers = sources_df['manufacturer'].dropna().unique()
                print(f"📊 Available manufacturers: {sorted(manufacturers)}")
            
            # Check for manufacturer_id
            if 'manufacturer_id' in sources_df.columns:
                manufacturer_ids = sources_df['manufacturer_id'].dropna().unique()
                print(f"📊 Available manufacturer_ids: {sorted(manufacturer_ids)}")
            
            # Search for SpoorTrack in multiple possible fields
            spoortrack_sources = []
            
            for idx, row in sources_df.iterrows():
                # Check various fields that might contain SpoorTrack
                manufacturer = str(row.get('manufacturer', ''))
                manufacturer_id = str(row.get('manufacturer_id', ''))
                model = str(row.get('model', ''))
                name = str(row.get('name', ''))
                
                # Look for SpoorTrack (case insensitive) in any relevant field
                if any('spoortrack' in field.lower() for field in [manufacturer, manufacturer_id, model, name]):
                    is_deployed = not row.get('inactive', False)  # Active sources are deployed
                    
                    spoortrack_sources.append({
                        'id': row.get('id'),
                        'name': row.get('name', 'Unknown'),
                        'manufacturer': manufacturer,
                        'manufacturer_id': manufacturer_id,
                        'model': model,
                        'is_deployed': is_deployed
                    })
            
            # Filter for only deployed sources
            deployed_sources = [s for s in spoortrack_sources if s['is_deployed']]
            
            print(f"🎯 Found {len(spoortrack_sources)} SpoorTrack sources ({len(deployed_sources)} deployed)")
            
            return deployed_sources
            
        except Exception as e:
            print(f"❌ Error finding SpoorTrack sources: {str(e)}")
            return []
    
    def get_source_observations(self, source_id, days_back=90):
        """Get recent observations for a source"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days_back)
            
            print(f"📡 Getting observations for source {source_id}...")
            
            # Get observations using ecoscope with improved error handling
            try:
                observations = self.er.get_source_observations(
                    source_ids=[source_id],  # Use plural and list format
                    since=start_time.isoformat(),  # Use 'since' instead of 'start_time'
                    until=end_time.isoformat(),    # Use 'until' instead of 'end_time'
                    relocations=False  # Return raw DataFrame instead of Relocations object
                )
                
                if observations is not None and not observations.empty:
                    print(f"✅ Retrieved {len(observations)} observations for source {source_id}")
                else:
                    print(f"⚠️ No observations found for source {source_id}")
                    
                return observations
                
            except Exception as api_error:
                # Try alternative parameter names if the first approach fails
                print(f"⚠️ Trying alternative API parameters for source {source_id}")
                try:
                    observations = self.er.get_source_observations(
                        source_id=source_id,  # Try singular form
                        start_time=start_time.isoformat(),
                        end_time=end_time.isoformat()
                    )
                    return observations if observations is not None else pd.DataFrame()
                except Exception as alt_error:
                    print(f"❌ Both API calls failed for source {source_id}: {str(alt_error)}")
                    return pd.DataFrame()
            
        except Exception as e:
            print(f"❌ Error getting observations for source {source_id}: {str(e)}")
            return pd.DataFrame()  # Return empty DataFrame on error
    
    def analyze_source_performance(self, source, observations_df):
        """Analyze performance metrics for a single source"""
        analysis = {
            'source_name': source['name'],
            'source_id': source['id'],
            'manufacturer': source['manufacturer'],
            'model': source['model'],
            'total_observations': 0,
            'days_analyzed': 90,  # Fixed to match the 90-day period
            'observations_per_day': 0,
            'mean_battery_voltage': None,
            'battery_status': 'Unknown',
            'location_success_rate': 0,
            'date_range': 'No data',
            'last_transmission': 'Unknown'
        }
        
        if not observations_df.empty:
            analysis['total_observations'] = len(observations_df)
            
            # Calculate observations per day - fix the bug in date range calculation
            if 'recorded_at' in observations_df.columns:
                # Convert to datetime if needed
                if not pd.api.types.is_datetime64_any_dtype(observations_df['recorded_at']):
                    observations_df['recorded_at'] = pd.to_datetime(observations_df['recorded_at'], errors='coerce')
                
                dates = observations_df['recorded_at'].dropna()
                if not dates.empty:
                    # Use the actual analysis period (90 days) instead of calculated range
                    analysis['observations_per_day'] = round(len(observations_df) / analysis['days_analyzed'], 1)
                    analysis['date_range'] = f"{dates.min().strftime('%Y-%m-%d')} to {dates.max().strftime('%Y-%m-%d')}"
                    analysis['last_transmission'] = dates.max().strftime('%Y-%m-%d %H:%M')
                else:
                    # Handle case with no valid dates
                    analysis['observations_per_day'] = 0
            
            # Battery analysis with improved error handling
            battery_columns = [col for col in observations_df.columns if 'battery' in col.lower() or 'voltage' in col.lower()]
            
            if battery_columns:
                # Use the first battery-related column found
                battery_col = battery_columns[0]
                battery_values = pd.to_numeric(observations_df[battery_col], errors='coerce').dropna()
                
                if not battery_values.empty:
                    analysis['mean_battery_voltage'] = round(battery_values.mean(), 2)
                    
                    # Categorize battery status based on mean voltage
                    if analysis['mean_battery_voltage'] >= 3.5:
                        analysis['battery_status'] = 'Good'
                    elif analysis['mean_battery_voltage'] >= 3.0:
                        analysis['battery_status'] = 'Warning'
                    else:
                        analysis['battery_status'] = 'Critical'
            
            # Location accuracy analysis with improved validation
            if 'longitude' in observations_df.columns and 'latitude' in observations_df.columns:
                # Convert to numeric and handle errors
                lons = pd.to_numeric(observations_df['longitude'], errors='coerce')
                lats = pd.to_numeric(observations_df['latitude'], errors='coerce')
                
                valid_locations = observations_df[
                    (lons.notna()) & 
                    (lats.notna()) &
                    (lons != 0) & 
                    (lats != 0) &
                    (lons.between(-180, 180)) &  # Valid longitude range
                    (lats.between(-90, 90))      # Valid latitude range
                ]
                
                if len(observations_df) > 0:
                    analysis['location_success_rate'] = round((len(valid_locations) / len(observations_df)) * 100, 1)
        
        return analysis
    
    def generate_performance_report(self, days_back=30):
        """Generate comprehensive performance report for all deployed SpoorTrack sources"""
        try:
            print("🚀 Starting SpoorTrack Performance Report Generation...")
            
            # Find all deployed SpoorTrack sources
            sources = self.find_spoortrack_sources()
            if not sources:
                print("⚠️ No deployed SpoorTrack sources found")
                return None
            
            # Analyze each source
            print(f"📊 Analyzing {len(sources)} deployed SpoorTrack sources...")
            
            analyses = []
            for i, source in enumerate(sources, 1):
                print(f"  🔍 Analyzing {i}/{len(sources)}: {source['name']}")
                
                observations = self.get_source_observations(source['id'], days_back)
                analysis = self.analyze_source_performance(source, observations)
                analyses.append(analysis)
            
            # Store results
            self.data = {
                'sources': sources,
                'analyses': analyses,
                'report_date': datetime.now(),
                'days_analyzed': days_back
            }
            
            print("✅ Performance analysis completed!")
            return analyses
            
        except Exception as e:
            print(f"❌ Error generating performance report: {str(e)}")
            return None
    
    def create_performance_summary(self):
        """Create summary statistics"""
        if not self.data or not self.data['analyses']:
            return None
        
        analyses = self.data['analyses']
        
        # Calculate summary statistics
        total_sources = len(analyses)
        total_observations = sum(a['total_observations'] for a in analyses)
        
        # Mean observations per day across all sources
        obs_per_day_values = [a['observations_per_day'] for a in analyses if a['observations_per_day'] > 0]
        mean_obs_per_day = round(np.mean(obs_per_day_values), 2) if obs_per_day_values else 0
        
        # Battery status distribution
        battery_statuses = [a['battery_status'] for a in analyses if a['battery_status'] != 'Unknown']
        battery_summary = {
            'Good': len([s for s in battery_statuses if s == 'Good']),
            'Warning': len([s for s in battery_statuses if s == 'Warning']),
            'Critical': len([s for s in battery_statuses if s == 'Critical']),
            'Unknown': total_sources - len(battery_statuses)
        }
        
        # Mean battery voltage
        battery_voltages = [a['mean_battery_voltage'] for a in analyses if a['mean_battery_voltage'] is not None]
        mean_battery_voltage = round(np.mean(battery_voltages), 2) if battery_voltages else None
        
        # Location success rate
        location_rates = [a['location_success_rate'] for a in analyses if a['location_success_rate'] > 0]
        mean_location_success = round(np.mean(location_rates), 1) if location_rates else 0
        
        return {
            'total_sources': total_sources,
            'total_observations': total_observations,
            'mean_observations_per_day': mean_obs_per_day,
            'battery_summary': battery_summary,
            'mean_battery_voltage': mean_battery_voltage,
            'mean_location_success_rate': mean_location_success
        }
    
    def generate_pdf_report(self, filename=None):
        """Generate PDF report using ReportLab"""
        if not REPORTLAB_AVAILABLE:
            print("❌ ReportLab not available. Cannot generate PDF.")
            return None
        
        if not self.data:
            print("❌ No data available. Run generate_performance_report() first.")
            return None
        
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            # Ensure reports directory exists
            reports_dir = os.path.join(os.path.dirname(__file__), 'reports')
            os.makedirs(reports_dir, exist_ok=True)
            filename = os.path.join(reports_dir, f"spoortrack_performance_report_{timestamp}.pdf")
        
        try:
            print(f"📄 Generating PDF report: {filename}")
            
            # Create PDF buffer
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=30,
                alignment=TA_CENTER
            )
            
            story.append(Paragraph("SpoorTrack Performance Report", title_style))
            story.append(Paragraph(f"Giraffe Conservation Foundation", styles['Normal']))
            story.append(Paragraph(f"Generated: {self.data['report_date'].strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            story.append(Paragraph(f"Analysis Period: {self.data['days_analyzed']} days", styles['Normal']))
            story.append(Spacer(1, 20))
            
            # Summary section
            summary = self.create_performance_summary()
            if summary:
                story.append(Paragraph("Executive Summary", styles['Heading2']))
                
                summary_data = [
                    ['Metric', 'Value'],
                    ['Total Deployed Sources', str(summary['total_sources'])],
                    ['Total Observations', f"{summary['total_observations']:,}"],
                    ['Mean Observations/Day', str(summary['mean_observations_per_day'])],
                    ['Mean Battery Voltage', f"{summary['mean_battery_voltage']:.2f}V" if summary['mean_battery_voltage'] else 'N/A'],
                    ['Mean Location Success Rate', f"{summary['mean_location_success_rate']}%"],
                ]
                
                summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
                summary_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(summary_table)
                story.append(Spacer(1, 20))
                
                # Battery status summary
                story.append(Paragraph("Battery Status Distribution", styles['Heading3']))
                battery_data = [
                    ['Status', 'Count'],
                    ['🟢 Good', str(summary['battery_summary']['Good'])],
                    ['🟡 Warning', str(summary['battery_summary']['Warning'])],
                    ['🔴 Critical', str(summary['battery_summary']['Critical'])],
                    ['❓ Unknown', str(summary['battery_summary']['Unknown'])],
                ]
                
                battery_table = Table(battery_data, colWidths=[2*inch, 1*inch])
                battery_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                story.append(battery_table)
                story.append(PageBreak())
            
            # Individual source details
            story.append(Paragraph("Individual Source Performance", styles['Heading2']))
            
            for analysis in self.data['analyses']:
                # Source header
                story.append(Paragraph(f"Source: {analysis['source_name']}", styles['Heading3']))
                
                # Source details table
                source_data = [
                    ['Parameter', 'Value'],
                    ['Source ID', analysis['source_id']],
                    ['Manufacturer', analysis['manufacturer']],
                    ['Model', analysis['model']],
                    ['Total Observations', f"{analysis['total_observations']:,}"],
                    ['Observations per Day', str(analysis['observations_per_day'])],
                    ['Battery Voltage (Mean)', f"{analysis['mean_battery_voltage']:.2f}V" if analysis['mean_battery_voltage'] else 'N/A'],
                    ['Battery Status', analysis['battery_status']],
                    ['Location Success Rate', f"{analysis['location_success_rate']}%"],
                    ['Last Transmission', analysis['last_transmission']],
                    ['Date Range', analysis['date_range']],
                ]
                
                source_table = Table(source_data, colWidths=[2.5*inch, 3*inch])
                source_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                ]))
                
                story.append(source_table)
                story.append(Spacer(1, 15))
            
            # Build PDF
            doc.build(story)
            buffer.seek(0)
            
            # Save to file
            with open(filename, 'wb') as f:
                f.write(buffer.getvalue())
            
            print(f"✅ PDF report generated: {filename}")
            return filename
            
        except Exception as e:
            print(f"❌ Error generating PDF: {str(e)}")
            return None
    
    def print_console_report(self):
        """Print formatted report to console in R-like tabular format"""
        if not self.data:
            print("❌ No data available. Run generate_performance_report() first.")
            return
        
        print("\n" + "="*90)
        print("SPOORTRACK PERFORMANCE REPORT - LAST QUARTER (90 DAYS)")
        print("Giraffe Conservation Foundation")
        print("="*90)
        
        print(f"Report Generated: {self.data['report_date'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Analysis Period: {self.data['days_analyzed']} days")
        print(f"Total Sources Analyzed: {len(self.data['analyses'])}")
        print("")
        
        # Create R-like data frame output
        self.print_r_style_table()
        
        # Summary statistics
        summary = self.create_performance_summary()
        if summary:
            print("\n" + "="*90)
            print("SUMMARY STATISTICS")
            print("="*90)
            print(f"Total Observations: {summary['total_observations']:,}")
            print(f"Mean Observations/Day: {summary['mean_observations_per_day']}")
            print(f"Mean Battery Voltage: {summary['mean_battery_voltage']:.2f}V" if summary['mean_battery_voltage'] else "Mean Battery Voltage: N/A")
            print(f"Mean Location Success: {summary['mean_location_success_rate']}%")
            print("")
            
            print("Battery Status Distribution:")
            for status, count in summary['battery_summary'].items():
                if count > 0:
                    print(f"  {status}: {count} sources")

    def print_r_style_table(self):
        """Print data in R-like data.frame format"""
        if not self.data or not self.data['analyses']:
            print("No data available")
            return
        
        # Define column headers and widths
        headers = [
            ("Source_Name", 25),
            ("Source_ID", 12),
            ("Total_Obs", 10),
            ("Obs_Per_Day", 12),
            ("Mean_Battery_V", 15),
            ("Battery_Status", 15),
            ("Location_Success_%", 18),
            ("Last_Transmission", 20)
        ]
        
        # Print header
        print("Source Performance Data (n = {}):".format(len(self.data['analyses'])))
        print("")
        
        # Print column headers
        header_line = ""
        separator_line = ""
        for header, width in headers:
            header_line += f"{header:<{width}} "
            separator_line += "-" * width + " "
        
        print(header_line)
        print(separator_line)
        
        # Print data rows
        for i, analysis in enumerate(self.data['analyses'], 1):
            row = ""
            
            # Source Name (truncated if too long)
            source_name = analysis['source_name'][:24] if len(analysis['source_name']) > 24 else analysis['source_name']
            row += f"{source_name:<25} "
            
            # Source ID
            row += f"{analysis['source_id']:<12} "
            
            # Total Observations
            row += f"{analysis['total_observations']:<10} "
            
            # Observations per day
            row += f"{analysis['observations_per_day']:<12} "
            
            # Mean battery voltage
            if analysis['mean_battery_voltage']:
                row += f"{analysis['mean_battery_voltage']:.2f}V{'':<10} "
            else:
                row += f"{'N/A':<15} "
            
            # Battery status (simplified)
            battery_simple = analysis['battery_status'].replace('🟢 ', '').replace('🟡 ', '').replace('🔴 ', '').replace('❓ ', '')
            row += f"{battery_simple:<15} "
            
            # Location success rate
            row += f"{analysis['location_success_rate']}%{'':<15} "
            
            # Last transmission (date only)
            last_trans = analysis['last_transmission']
            if isinstance(last_trans, str) and len(last_trans) > 10:
                last_trans = last_trans.split()[0]  # Take date part only
            row += f"{last_trans:<20}"
            
            print(row)
        
        print("")
        print(f"[1] Data frame with {len(self.data['analyses'])} rows and {len(headers)} columns")
        print(f"[2] Analysis period: {self.data['days_analyzed']} days (Quarter: {self.data['report_date'].strftime('%Y Q%q')})")
        print(f"[3] Generated: {self.data['report_date'].strftime('%Y-%m-%d %H:%M:%S')}")

def main():
    """Main function for standalone execution"""
    print("🦒 SpoorTrack Performance Report Generator")
    print("=" * 45)
    print("Analyzes performance of all deployed SpoorTrack sources")
    print("Reports mean battery voltage and observations per day\n")
    
    if not ECOSCOPE_AVAILABLE:
        print("❌ Ecoscope package is required but not available.")
        print("Install with: pip install ecoscope")
        return
    
    # Initialize report generator
    reporter = SpoorTrackPerformanceReport()
    
    # Authenticate
    if not reporter.authenticate():
        print("❌ Authentication failed. Exiting.")
        return
    
    # Generate report for last quarter (90 days)
    analyses = reporter.generate_performance_report(days_back=90)
    
    if analyses:
        # Print console report
        reporter.print_console_report()
        
        # Generate PDF if available
        if REPORTLAB_AVAILABLE:
            pdf_file = reporter.generate_pdf_report()
            if pdf_file:
                print(f"\n📄 PDF report saved: {pdf_file}")
        else:
            print(f"\n⚠️ Install reportlab for PDF generation: pip install reportlab")
        
        print(f"\n✅ Report generation completed!")
        
    else:
        print(f"\n❌ Report generation failed.")

if __name__ == "__main__":
    main()
