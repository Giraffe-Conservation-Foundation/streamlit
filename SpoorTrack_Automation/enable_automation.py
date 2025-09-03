#!/usr/bin/env python3
"""
Enable SpoorTrack Automation
Activates full quarterly automation after test report approval
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
import logging

class AutomationEnabler:
    """Enable full automation after testing"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.config_dir = self.base_dir / 'config'
        self.logs_dir = self.base_dir / 'logs'
        
        # Setup logging
        log_file = self.logs_dir / f'automation_setup_{datetime.now().strftime("%Y%m%d_%H%M")}.log'
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_config(self):
        """Load configuration"""
        try:
            from secure_setup import SecureSpoorTrackConfig
            config_manager = SecureSpoorTrackConfig()
            return config_manager.load_config()
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return None
    
    def update_config_for_automation(self, config):
        """Update config to enable full automation"""
        try:
            # Remove test mode
            config['report']['test_mode'] = False
            config['report']['automation_enabled'] = True
            config['report']['automation_enabled_date'] = datetime.now().isoformat()
            
            # Save updated config
            from secure_setup import SecureSpoorTrackConfig
            config_manager = SecureSpoorTrackConfig()
            
            # Re-encode sensitive data for saving
            er_config = config['earthranger']
            if 'token' in er_config:
                er_config['token'] = config_manager.secure_encode(er_config['token'])
            if 'username' in er_config:
                er_config['username'] = config_manager.secure_encode(er_config['username'])
            if 'password' in er_config:
                er_config['password'] = config_manager.secure_encode(er_config['password'])
            
            if config.get('email'):
                email_config = config['email']
                if 'password' in email_config:
                    email_config['password'] = config_manager.secure_encode(email_config['password'])
            
            success = config_manager.save_config(config)
            
            # Decrypt back for use
            if 'token' in er_config:
                er_config['token'] = config_manager.secure_decode(er_config['token'])
            if 'username' in er_config:
                er_config['username'] = config_manager.secure_decode(er_config['username'])
            if 'password' in er_config:
                er_config['password'] = config_manager.secure_decode(er_config['password'])
            
            if config.get('email') and 'password' in config['email']:
                config['email']['password'] = config_manager.secure_decode(config['email']['password'])
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error updating config: {e}")
            return False
    
    def create_full_reporter(self):
        """Create the full quarterly reporter script"""
        reporter_script = self.base_dir / 'quarterly_reporter.py'
        
        content = '''#!/usr/bin/env python3
"""
Full SpoorTrack Quarterly Reporter
Generates comprehensive quarterly reports automatically
"""

import os
import sys
import json
import requests
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from pathlib import Path
import logging

class QuarterlySpoorTrackReporter:
    """Full quarterly SpoorTrack reporter"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.config_dir = self.base_dir / 'config'
        self.reports_dir = self.base_dir / 'reports'
        self.logs_dir = self.base_dir / 'logs'
        
        # Setup logging
        self.setup_logging()
        self.config = self.load_config()
        
    def setup_logging(self):
        """Setup comprehensive logging"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.logs_dir / f'quarterly_report_{timestamp}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_config(self):
        """Load configuration"""
        try:
            from secure_setup import SecureSpoorTrackConfig
            config_manager = SecureSpoorTrackConfig()
            return config_manager.load_config()
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return None
    
    def connect_to_earthranger(self):
        """Connect to EarthRanger API"""
        try:
            if not self.config:
                raise Exception("No configuration found")
            
            er_config = self.config['earthranger']
            server = er_config['server']
            
            self.logger.info(f"Connecting to EarthRanger: {server}")
            
            self.session = requests.Session()
            self.session.timeout = 60
            
            # Authenticate
            if er_config['auth_method'] == 'token':
                self.session.headers.update({'Authorization': f"Bearer {er_config['token']}"})
            else:
                auth_url = f"{server}/api/v1.0/auth/login"
                response = self.session.post(auth_url, json={
                    'username': er_config['username'],
                    'password': er_config['password']
                })
                response.raise_for_status()
                token = response.json().get('token')
                self.session.headers.update({'Authorization': f"Bearer {token}"})
            
            self.server_url = server
            self.logger.info("✅ EarthRanger connection established")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ EarthRanger connection failed: {e}")
            return False
    
    def generate_quarterly_report(self):
        """Generate full quarterly report"""
        try:
            self.logger.info("🚀 Starting quarterly SpoorTrack report generation...")
            
            # Connect to EarthRanger
            if not self.connect_to_earthranger():
                return False
            
            # Calculate quarterly date range
            now = datetime.now()
            quarter_start = datetime(now.year, ((now.month - 1) // 3) * 3 + 1, 1)
            if quarter_start.month == 1:
                previous_quarter_start = datetime(now.year - 1, 10, 1)
            else:
                previous_quarter_start = datetime(now.year, quarter_start.month - 3, 1)
            
            self.logger.info(f"📅 Analyzing quarter: {previous_quarter_start.strftime('%Y-%m-%d')} to {quarter_start.strftime('%Y-%m-%d')}")
            
            # Get all SpoorTrack units
            units = self.find_all_spoortrack_units()
            if not units:
                self.logger.warning("⚠️ No SpoorTrack units found")
                return False
            
            self.logger.info(f"📊 Analyzing {len(units)} SpoorTrack units...")
            
            # Analyze all units for the quarter
            quarterly_analyses = []
            for i, unit in enumerate(units, 1):
                self.logger.info(f"  🔍 Analyzing unit {i}/{len(units)}: {unit.get('name')}")
                observations = self.get_quarterly_observations(unit['id'], previous_quarter_start, quarter_start)
                analysis = self.analyze_unit_quarterly_performance(unit, observations, previous_quarter_start, quarter_start)
                quarterly_analyses.append(analysis)
            
            # Generate comprehensive report
            report_file = self.create_comprehensive_report(quarterly_analyses, previous_quarter_start, quarter_start)
            
            # Create visualizations
            charts_file = self.create_quarterly_charts(quarterly_analyses)
            
            # Send email report
            if self.config.get('email'):
                self.send_quarterly_email(report_file, charts_file, quarterly_analyses)
            
            self.logger.info("✅ Quarterly report generation completed successfully!")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error generating quarterly report: {e}")
            self.send_error_notification(str(e))
            return False
    
    def find_all_spoortrack_units(self):
        """Find all SpoorTrack units (full search)"""
        try:
            subjects_url = f"{self.server_url}/api/v1.0/subjects"
            all_subjects = []
            page = 1
            
            while True:
                response = self.session.get(subjects_url, params={
                    'page': page,
                    'page_size': 100
                })
                response.raise_for_status()
                data = response.json()
                subjects = data.get('results', [])
                
                if not subjects:
                    break
                
                all_subjects.extend(subjects)
                
                if not data.get('next'):
                    break
                page += 1
            
            # Filter for SpoorTrack units
            spoortrack_units = []
            for subject in all_subjects:
                name = subject.get('name', '').lower()
                
                if 'spoortrack' in name and not any(exclude in name for exclude in ['eartag', 'ear tag', 'ear-tag']):
                    spoortrack_units.append(subject)
                    continue
                
                device_props = subject.get('device_status_properties', {})
                if isinstance(device_props, dict):
                    manufacturer = device_props.get('manufacturer', '').lower()
                    if 'spoortrack' in manufacturer:
                        spoortrack_units.append(subject)
            
            return spoortrack_units
            
        except Exception as e:
            self.logger.error(f"❌ Error finding SpoorTrack units: {e}")
            return []
    
    def get_quarterly_observations(self, subject_id, start_date, end_date):
        """Get all observations for the quarter"""
        try:
            obs_url = f"{self.server_url}/api/v1.0/observations"
            all_observations = []
            page = 1
            
            while True:
                response = self.session.get(obs_url, params={
                    'subject_id': subject_id,
                    'start_time': start_date.isoformat(),
                    'end_time': end_date.isoformat(),
                    'page': page,
                    'page_size': 100
                })
                response.raise_for_status()
                
                data = response.json()
                observations = data.get('results', [])
                
                if not observations:
                    break
                
                all_observations.extend(observations)
                
                if not data.get('next'):
                    break
                page += 1
            
            return all_observations
            
        except Exception as e:
            self.logger.error(f"❌ Error getting quarterly observations for {subject_id}: {e}")
            return []
    
    def analyze_unit_quarterly_performance(self, unit, observations, start_date, end_date):
        """Comprehensive quarterly analysis for a unit"""
        analysis = {
            'unit_name': unit.get('name', 'Unknown'),
            'unit_id': unit.get('id'),
            'quarter_period': f"{start_date.strftime('%Y Q%m')}",
            'total_observations': len(observations),
            'expected_observations': (end_date - start_date).days * 24,  # Assuming hourly
            'transmission_success_rate': 0,
            'battery_trend': 'Unknown',
            'battery_voltages': [],
            'location_success_rate': 0,
            'performance_score': 0
        }
        
        if observations:
            # Transmission success rate
            expected = analysis['expected_observations']
            actual = len(observations)
            analysis['transmission_success_rate'] = min(100, (actual / expected) * 100) if expected > 0 else 0
            
            # Battery analysis
            battery_voltages = []
            for obs in observations:
                additional = obs.get('additional', {})
                for key, value in additional.items():
                    if 'battery' in key.lower() or 'volt' in key.lower():
                        if isinstance(value, (int, float)) and 2.0 <= value <= 5.0:
                            battery_voltages.append(value)
                            break
            
            analysis['battery_voltages'] = battery_voltages
            if battery_voltages:
                if len(battery_voltages) > 1:
                    trend = battery_voltages[-1] - battery_voltages[0]
                    if trend > 0.1:
                        analysis['battery_trend'] = 'Improving'
                    elif trend < -0.1:
                        analysis['battery_trend'] = 'Declining'
                    else:
                        analysis['battery_trend'] = 'Stable'
                
                latest_voltage = battery_voltages[-1] if battery_voltages else 0
                analysis['latest_battery_voltage'] = latest_voltage
            
            # Location accuracy
            valid_locations = 0
            for obs in observations:
                location = obs.get('location', {})
                lat = location.get('latitude')
                lon = location.get('longitude')
                if lat and lon and lat != 0 and lon != 0:
                    valid_locations += 1
            
            analysis['location_success_rate'] = (valid_locations / len(observations)) * 100 if observations else 0
            
            # Overall performance score (0-100)
            transmission_score = min(100, analysis['transmission_success_rate'])
            location_score = analysis['location_success_rate']
            battery_score = 100 if analysis.get('latest_battery_voltage', 0) >= 3.5 else 50 if analysis.get('latest_battery_voltage', 0) >= 3.0 else 0
            
            analysis['performance_score'] = (transmission_score + location_score + battery_score) / 3
        
        return analysis
    
    def create_comprehensive_report(self, analyses, start_date, end_date):
        """Create comprehensive quarterly report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = self.reports_dir / f'spoortrack_quarterly_report_{timestamp}.txt'
        
        with open(report_file, 'w') as f:
            config = self.config or {}
            report_config = config.get('report', {})
            
            f.write("=" * 80 + "\\n")
            f.write(f"SPOORTRACK QUARTERLY PERFORMANCE REPORT\\n")
            f.write(f"{report_config.get('organization', 'Organization')}\\n")
            f.write(f"{report_config.get('project', 'SpoorTrack Monitoring')}\\n")
            f.write("=" * 80 + "\\n\\n")
            
            f.write(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n")
            f.write(f"Quarter Analyzed: {start_date.strftime('%Y Q%m')}\\n")
            f.write(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\\n")
            f.write(f"Total Units: {len(analyses)}\\n")
            f.write(f"Data Source: Live EarthRanger API\\n\\n")
            
            # Executive Summary
            f.write("EXECUTIVE SUMMARY\\n")
            f.write("-" * 20 + "\\n")
            
            total_obs = sum(a['total_observations'] for a in analyses)
            avg_performance = sum(a['performance_score'] for a in analyses) / len(analyses) if analyses else 0
            high_performers = len([a for a in analyses if a['performance_score'] >= 80])
            low_performers = len([a for a in analyses if a['performance_score'] < 50])
            
            f.write(f"Quarter Performance Score: {avg_performance:.1f}/100\\n")
            f.write(f"Total Observations Received: {total_obs:,}\\n")
            f.write(f"High Performing Units (≥80%): {high_performers}\\n")
            f.write(f"Units Needing Attention (<50%): {low_performers}\\n\\n")
            
            # Detailed unit analyses
            f.write("DETAILED UNIT PERFORMANCE\\n")
            f.write("-" * 30 + "\\n\\n")
            
            for analysis in sorted(analyses, key=lambda x: x['performance_score'], reverse=True):
                f.write(f"Unit: {analysis['unit_name']}\\n")
                f.write(f"Performance Score: {analysis['performance_score']:.1f}/100\\n")
                f.write(f"Observations: {analysis['total_observations']:,}\\n")
                f.write(f"Transmission Rate: {analysis['transmission_success_rate']:.1f}%\\n")
                f.write(f"Location Accuracy: {analysis['location_success_rate']:.1f}%\\n")
                f.write(f"Battery Status: {analysis['battery_trend']}\\n")
                if analysis.get('latest_battery_voltage'):
                    f.write(f"Latest Battery: {analysis['latest_battery_voltage']:.2f}V\\n")
                f.write("-" * 60 + "\\n\\n")
        
        self.logger.info(f"📄 Comprehensive report saved: {report_file}")
        return report_file
    
    def create_quarterly_charts(self, analyses):
        """Create quarterly performance charts"""
        try:
            # Create performance overview chart
            fig = go.Figure()
            
            unit_names = [a['unit_name'][:20] for a in analyses]  # Truncate long names
            performance_scores = [a['performance_score'] for a in analyses]
            
            fig.add_trace(go.Bar(
                x=unit_names,
                y=performance_scores,
                name='Performance Score',
                marker_color=['green' if score >= 80 else 'orange' if score >= 50 else 'red' for score in performance_scores]
            ))
            
            fig.update_layout(
                title='SpoorTrack Unit Performance - Quarterly Overview',
                xaxis_title='Units',
                yaxis_title='Performance Score (0-100)',
                height=500
            )
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            chart_file = self.reports_dir / f'quarterly_performance_chart_{timestamp}.html'
            fig.write_html(chart_file)
            
            self.logger.info(f"📊 Performance chart saved: {chart_file}")
            return chart_file
            
        except Exception as e:
            self.logger.error(f"❌ Error creating charts: {e}")
            return None
    
    def send_quarterly_email(self, report_file, chart_file, analyses):
        """Send quarterly report via email"""
        try:
            email_config = self.config['email']
            
            msg = MIMEMultipart()
            msg['From'] = email_config['username']
            msg['To'] = ', '.join(email_config['recipients'])
            msg['Subject'] = f"SpoorTrack Quarterly Report - {datetime.now().strftime('%Y Q%m')}"
            
            # Email body
            total_units = len(analyses)
            avg_performance = sum(a['performance_score'] for a in analyses) / len(analyses) if analyses else 0
            total_obs = sum(a['total_observations'] for a in analyses)
            
            body = f"""
SpoorTrack Quarterly Performance Report
{self.config['report']['organization']}

Quarter: {datetime.now().strftime('%Y Q%m')}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

SUMMARY:
========
Total Units Monitored: {total_units}
Average Performance Score: {avg_performance:.1f}/100
Total Observations: {total_obs:,}

High Performing Units: {len([a for a in analyses if a['performance_score'] >= 80])}
Units Needing Attention: {len([a for a in analyses if a['performance_score'] < 50])}

See attached files for detailed analysis and performance charts.

This report was automatically generated by the SpoorTrack monitoring system.
Data was pulled live from EarthRanger at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.

Next Report: {(datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')} (Quarterly)
"""
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach report file
            if report_file and report_file.exists():
                with open(report_file, 'rb') as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename= {report_file.name}')
                    msg.attach(part)
            
            # Attach chart file
            if chart_file and chart_file.exists():
                with open(chart_file, 'rb') as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename= {chart_file.name}')
                    msg.attach(part)
            
            # Send email
            server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
            server.starttls()
            server.login(email_config['username'], email_config['password'])
            text = msg.as_string()
            server.sendmail(email_config['username'], email_config['recipients'], text)
            server.quit()
            
            self.logger.info(f"📧 Quarterly report emailed to: {', '.join(email_config['recipients'])}")
            
        except Exception as e:
            self.logger.error(f"❌ Error sending quarterly email: {e}")
    
    def send_error_notification(self, error_msg):
        """Send error notification"""
        try:
            if not self.config.get('email'):
                return
            
            email_config = self.config['email']
            
            msg = MIMEMultipart()
            msg['From'] = email_config['username']
            msg['To'] = ', '.join(email_config['recipients'])
            msg['Subject'] = f"SpoorTrack Quarterly Report - ERROR - {datetime.now().strftime('%Y-%m-%d')}"
            
            body = f"""
SPOORTRACK QUARTERLY REPORT ERROR

Time: {datetime.now()}
Error: {error_msg}

The automated quarterly SpoorTrack report failed to generate.
Please check the system logs and retry manually if needed.

Log Location: {self.logs_dir}

This is an automated error notification.
"""
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
            server.starttls()
            server.login(email_config['username'], email_config['password'])
            text = msg.as_string()
            server.sendmail(email_config['username'], email_config['recipients'], text)
            server.quit()
            
            self.logger.info("📧 Error notification sent")
            
        except Exception as e:
            self.logger.error(f"❌ Could not send error notification: {e}")

def main():
    """Main quarterly report execution"""
    print(f"🚀 SpoorTrack Quarterly Report - {datetime.now()}")
    print("=" * 60)
    
    try:
        reporter = QuarterlySpoorTrackReporter()
        success = reporter.generate_quarterly_report()
        
        if success:
            print("✅ Quarterly report completed successfully!")
        else:
            print("❌ Quarterly report failed")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
        
        try:
            with open(reporter_script, 'w') as f:
                f.write(content)
            
            self.logger.info(f"✅ Created full quarterly reporter: {reporter_script}")
            return reporter_script
            
        except Exception as e:
            self.logger.error(f"❌ Error creating reporter script: {e}")
            return None
    
    def create_scheduler_script(self):
        """Create Windows scheduler script"""
        scheduler_script = self.base_dir / 'run_quarterly_scheduler.py'
        
        content = '''#!/usr/bin/env python3
"""
SpoorTrack Quarterly Scheduler
Runs quarterly reports automatically
"""

import schedule
import time
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def run_quarterly_report():
    """Execute the quarterly report"""
    try:
        print(f"🚀 Starting scheduled quarterly report at {datetime.now()}")
        
        script_path = Path(__file__).parent / 'quarterly_reporter.py'
        result = subprocess.run([sys.executable, str(script_path)], 
                              capture_output=True, text=True, timeout=3600)
        
        if result.returncode == 0:
            print("✅ Quarterly report completed successfully")
        else:
            print(f"❌ Quarterly report failed: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Error running quarterly report: {e}")

def main():
    """Main scheduler"""
    print("📅 SpoorTrack Quarterly Scheduler Started")
    print(f"⏰ Current time: {datetime.now()}")
    
    # Schedule for first day of each quarter at 9 AM
    schedule.every().quarter.do(run_quarterly_report)
    
    print("📊 Scheduled quarterly reports for 9 AM on first day of each quarter")
    print("⏳ Scheduler running... (Ctrl+C to stop)")
    
    while True:
        schedule.run_pending()
        time.sleep(3600)  # Check every hour

if __name__ == "__main__":
    main()
'''
        
        try:
            with open(scheduler_script, 'w') as f:
                f.write(content)
            
            self.logger.info(f"✅ Created scheduler script: {scheduler_script}")
            return scheduler_script
            
        except Exception as e:
            self.logger.error(f"❌ Error creating scheduler script: {e}")
            return None
    
    def create_windows_task(self, scheduler_script):
        """Create Windows Task Scheduler setup"""
        batch_file = self.base_dir / 'setup_windows_task.bat'
        
        content = f'''@echo off
echo Creating Windows Task Scheduler entry for SpoorTrack Quarterly Reports
echo.

set TASK_NAME=SpoorTrack Quarterly Reports
set SCRIPT_PATH={scheduler_script}
set PYTHON_PATH={sys.executable}

echo Task Name: %TASK_NAME%
echo Script: %SCRIPT_PATH%
echo Python: %PYTHON_PATH%
echo.

schtasks /create /tn "%TASK_NAME%" /tr "\\""%PYTHON_PATH%"\\" \\"%SCRIPT_PATH%\\"" /sc quarterly /st 09:00 /f

if %ERRORLEVEL% EQU 0 (
    echo ✅ Windows Task created successfully!
    echo.
    echo The task will run quarterly at 9:00 AM
    echo You can view/modify it in Task Scheduler (taskschd.msc)
) else (
    echo ❌ Failed to create Windows Task
    echo Please run as Administrator or create manually
)

echo.
pause
'''
        
        try:
            with open(batch_file, 'w') as f:
                f.write(content)
            
            self.logger.info(f"✅ Created Windows task setup: {batch_file}")
            return batch_file
            
        except Exception as e:
            self.logger.error(f"❌ Error creating Windows task setup: {e}")
            return None
    
    def enable_automation(self):
        """Enable full automation"""
        print("🔄 Enabling SpoorTrack Automation")
        print("=" * 35)
        
        # Load and verify config
        config = self.load_config()
        if not config:
            print("❌ No configuration found. Run secure_setup.py first.")
            return False
        
        # Check if test report was run
        reports_dir = self.base_dir / 'reports'
        test_reports = list(reports_dir.glob('spoortrack_test_report_*.txt'))
        
        if not test_reports:
            print("⚠️ No test report found.")
            print("It's recommended to run 'python test_report.py' first")
            proceed = input("Continue anyway? (y/N): ").strip().lower()
            if proceed != 'y':
                return False
        else:
            latest_test = max(test_reports, key=lambda x: x.stat().st_mtime)
            print(f"✅ Found test report: {latest_test.name}")
        
        # Confirm email setup if missing
        if not config.get('email'):
            print("⚠️ No email configuration found.")
            setup_email = input("Set up email for automated delivery? (y/N): ").strip().lower()
            if setup_email == 'y':
                print("Please run secure_setup.py to configure email")
                return False
        
        print("\\n📋 Automation will enable:")
        print("• Quarterly SpoorTrack performance reports")
        print("• Live data pulls from EarthRanger")
        print("• Comprehensive analysis of ALL units")
        print("• Automatic email delivery")
        print("• Windows Task Scheduler integration")
        
        confirm = input("\\nEnable full automation? (y/N): ").strip().lower()
        if confirm != 'y':
            print("❌ Automation not enabled")
            return False
        
        # Update configuration
        if not self.update_config_for_automation(config):
            print("❌ Failed to update configuration")
            return False
        
        # Create full reporter script
        reporter_script = self.create_full_reporter()
        if not reporter_script:
            print("❌ Failed to create reporter script")
            return False
        
        # Create scheduler
        scheduler_script = self.create_scheduler_script()
        if not scheduler_script:
            print("❌ Failed to create scheduler script")
            return False
        
        # Create Windows task setup
        batch_file = self.create_windows_task(scheduler_script)
        
        print("\\n🎉 AUTOMATION ENABLED SUCCESSFULLY!")
        print("=" * 40)
        print(f"📁 Installation: {self.base_dir}")
        print(f"📊 Reporter: {reporter_script}")
        print(f"⏰ Scheduler: {scheduler_script}")
        
        if batch_file:
            print(f"🪟 Windows Task: {batch_file}")
            print("\\n📅 To activate Windows Task Scheduler:")
            print(f"   Right-click and 'Run as Administrator': {batch_file}")
        
        print("\\n🔄 To start the scheduler manually:")
        print(f"   python {scheduler_script}")
        
        print("\\n✅ Your SpoorTrack monitoring is now fully automated!")
        print("Reports will be generated quarterly and emailed automatically.")
        
        return True

def main():
    """Main automation enabler"""
    enabler = AutomationEnabler()
    success = enabler.enable_automation()
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
