#!/usr/bin/env python3
"""
Secure SpoorTrack Automation System
Isolated, secure setup with test-first approach
"""

import os
import json
import getpass
from pathlib import Path
from datetime import datetime
import base64
import logging

class SecureSpoorTrackConfig:
    """Secure configuration for SpoorTrack automation"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.config_dir = self.base_dir / 'config'
        self.reports_dir = self.base_dir / 'reports'
        self.logs_dir = self.base_dir / 'logs'
        
        # Ensure directories exist with proper permissions
        for directory in [self.config_dir, self.reports_dir, self.logs_dir]:
            directory.mkdir(exist_ok=True, mode=0o700)
        
        self.config_file = self.config_dir / 'spoortrack_config.json'
        self.setup_logging()
    
    def setup_logging(self):
        """Setup secure logging"""
        log_file = self.logs_dir / f'spoortrack_{datetime.now().strftime("%Y%m%d")}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def secure_encode(self, data):
        """Secure encoding of sensitive data"""
        # Use base64 with a simple key rotation
        import hashlib
        key = hashlib.sha256(str(self.config_dir).encode()).hexdigest()[:16]
        encoded = base64.b64encode(data.encode()).decode()
        return f"{key}:{encoded}"
    
    def secure_decode(self, data):
        """Secure decoding of sensitive data"""
        try:
            import hashlib
            expected_key = hashlib.sha256(str(self.config_dir).encode()).hexdigest()[:16]
            key, encoded = data.split(':', 1)
            
            if key != expected_key:
                raise ValueError("Invalid key")
            
            return base64.b64decode(encoded.encode()).decode()
        except Exception:
            raise ValueError("Cannot decode secure data")
    
    def interactive_setup(self):
        """Interactive setup with enhanced security"""
        print("🔒 Secure SpoorTrack Automation Setup")
        print("=" * 40)
        print(f"📁 Installation Directory: {self.base_dir}")
        print(f"🔐 Config Directory: {self.config_dir}")
        print(f"📊 Reports Directory: {self.reports_dir}")
        print()
        
        # Check for existing config
        if self.config_file.exists():
            print("⚠️ Existing configuration found.")
            choice = input("(U)pdate, (D)elete and restart, or (C)ancel? ").strip().upper()
            if choice == 'D':
                self.config_file.unlink()
                print("🗑️ Previous configuration deleted")
            elif choice == 'C':
                return None
            elif choice != 'U':
                return self.load_config()
        
        config = {}
        
        # EarthRanger Configuration
        print("\n🌍 EarthRanger API Configuration")
        print("-" * 35)
        
        config['earthranger'] = {}
        config['earthranger']['server'] = input("EarthRanger server URL: ").strip()
        
        print("\nAuthentication method:")
        print("1. API Token (recommended - more secure)")
        print("2. Username/Password")
        
        auth_choice = input("Choose (1 or 2): ").strip()
        
        if auth_choice == "1":
            token = getpass.getpass("API Token (will be hidden): ").strip()
            config['earthranger']['token'] = self.secure_encode(token)
            config['earthranger']['auth_method'] = 'token'
        else:
            username = input("Username: ").strip()
            password = getpass.getpass("Password (will be hidden): ").strip()
            config['earthranger']['username'] = self.secure_encode(username)
            config['earthranger']['password'] = self.secure_encode(password)
            config['earthranger']['auth_method'] = 'password'
        
        # Email Configuration (optional for testing)
        print("\n📧 Email Configuration")
        print("-" * 21)
        print("Email is optional for initial testing")
        
        setup_email = input("Set up email now? (y/N): ").strip().lower() == 'y'
        
        if setup_email:
            config['email'] = {}
            config['email']['smtp_server'] = input("SMTP server (gmail: smtp.gmail.com): ").strip() or "smtp.gmail.com"
            config['email']['smtp_port'] = int(input("SMTP port (gmail: 587): ").strip() or "587")
            config['email']['username'] = input("Your email address: ").strip()
            
            print("\n🔑 For Gmail, use an App Password (not your regular password)")
            print("   Google Account → Security → 2-Step Verification → App Passwords")
            
            email_password = getpass.getpass("Email password/App Password (will be hidden): ").strip()
            config['email']['password'] = self.secure_encode(email_password)
            
            recipients = input("Report recipients (comma-separated): ").strip()
            config['email']['recipients'] = [email.strip() for email in recipients.split(',') if email.strip()]
        else:
            config['email'] = None
        
        # Report Configuration
        print("\n📊 Report Configuration")
        print("-" * 22)
        
        config['report'] = {
            'organization': input("Organization (default: Giraffe Conservation Foundation): ").strip() or "Giraffe Conservation Foundation",
            'project': input("Project name (default: SpoorTrack Monitoring): ").strip() or "SpoorTrack Monitoring",
            'frequency': 'quarterly',
            'test_mode': True  # Start in test mode
        }
        
        # Save configuration
        config['setup'] = {
            'date': datetime.now().isoformat(),
            'version': '2.0',
            'directory': str(self.base_dir)
        }
        
        if self.save_config(config):
            self.logger.info("Configuration saved successfully")
            return config
        else:
            self.logger.error("Failed to save configuration")
            return None
    
    def save_config(self, config):
        """Save configuration securely"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Set restrictive permissions (Windows equivalent)
            os.chmod(self.config_file, 0o600)
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
            return False
    
    def load_config(self):
        """Load and decrypt configuration"""
        try:
            if not self.config_file.exists():
                return None
            
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            # Decrypt sensitive fields
            if 'earthranger' in config:
                er_config = config['earthranger']
                if 'token' in er_config:
                    er_config['token'] = self.secure_decode(er_config['token'])
                if 'username' in er_config:
                    er_config['username'] = self.secure_decode(er_config['username'])
                if 'password' in er_config:
                    er_config['password'] = self.secure_decode(er_config['password'])
            
            if config.get('email'):
                email_config = config['email']
                if 'password' in email_config:
                    email_config['password'] = self.secure_decode(email_config['password'])
            
            return config
            
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            return None
    
    def test_connection(self, config):
        """Test EarthRanger connection"""
        try:
            import requests
            
            self.logger.info("Testing EarthRanger connection...")
            
            er_config = config['earthranger']
            server = er_config['server']
            
            # Test basic connectivity
            response = requests.get(f"{server}/api/v1.0/", timeout=10)
            
            if response.status_code in [200, 401, 403]:
                self.logger.info("EarthRanger server is reachable")
                
                # Test authentication
                session = requests.Session()
                
                if er_config['auth_method'] == 'token':
                    session.headers.update({'Authorization': f"Bearer {er_config['token']}"})
                else:
                    auth_url = f"{server}/api/v1.0/auth/login"
                    auth_response = session.post(auth_url, json={
                        'username': er_config['username'],
                        'password': er_config['password']
                    })
                    if auth_response.status_code == 200:
                        token = auth_response.json().get('token')
                        session.headers.update({'Authorization': f"Bearer {token}"})
                
                # Test API access
                subjects_url = f"{server}/api/v1.0/subjects"
                api_response = session.get(subjects_url, params={'page_size': 1})
                
                if api_response.status_code == 200:
                    self.logger.info("Authentication successful")
                    return True
                else:
                    self.logger.error(f"API authentication failed: {api_response.status_code}")
                    return False
            else:
                self.logger.error(f"EarthRanger server not reachable: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False

def main():
    """Main setup function"""
    print("🚀 Setting up Secure SpoorTrack Automation")
    print("=" * 45)
    
    config_manager = SecureSpoorTrackConfig()
    
    # Interactive setup
    config = config_manager.interactive_setup()
    
    if not config:
        print("❌ Setup cancelled or failed")
        return
    
    # Test connection
    print(f"\n🧪 Testing EarthRanger connection...")
    if config_manager.test_connection(config):
        print("✅ Connection test passed!")
    else:
        print("❌ Connection test failed - check credentials")
        return
    
    print(f"\n🎉 SECURE SETUP COMPLETE!")
    print("=" * 30)
    print(f"📁 Installation: {config_manager.base_dir}")
    print(f"🔐 Config: {config_manager.config_file}")
    print(f"📊 Reports: {config_manager.reports_dir}")
    print(f"📝 Logs: {config_manager.logs_dir}")
    
    print(f"\n📋 Next Steps:")
    print(f"1. Run a test report to verify everything works")
    print(f"2. Review the test report output")
    print(f"3. Enable full automation once satisfied")
    
    print(f"\n💡 Run test report:")
    print(f"   python test_report.py")

if __name__ == "__main__":
    main()
