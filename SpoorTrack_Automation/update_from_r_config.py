#!/usr/bin/env python3
"""
Update SpoorTrack configuration with correct EarthRanger API details from existing R tools
"""

import json
from pathlib import Path
from secure_setup import SecureSpoorTrackConfig

def update_from_r_config():
    """Update configuration with details from working R Shiny tools"""
    
    print("Updating EarthRanger configuration from existing R tools...")
    print("=" * 60)
    
    config_manager = SecureSpoorTrackConfig()
    config = config_manager.load_config()
    
    if not config:
        print("❌ No configuration found. Run secure_setup.py first.")
        return False
    
    # Update with correct EarthRanger details from R tools
    print("Current configuration:")
    print(f"  Server: {config['earthranger']['server']}")
    
    # Set correct server URL based on R tools
    correct_server = "https://twiga.pamdas.org"
    config['earthranger']['server'] = correct_server
    
    print(f"Updated server to: {correct_server}")
    
    # Re-encode sensitive data for saving
    er_config = config['earthranger']
    if 'token' in er_config:
        er_config['token'] = config_manager.secure_encode(er_config['token'])
    if 'username' in er_config:
        er_config['username'] = config_manager.secure_encode(er_config['username'])
    if 'password' in er_config:
        er_config['password'] = config_manager.secure_encode(er_config['password'])
    
    if config.get('email') and 'password' in config['email']:
        config['email']['password'] = config_manager.secure_encode(config['email']['password'])
    
    # Save updated config
    if config_manager.save_config(config):
        print("✅ Configuration updated successfully!")
        
        # Decrypt for testing
        if 'token' in er_config:
            er_config['token'] = config_manager.secure_decode(er_config['token'])
        if 'username' in er_config:
            er_config['username'] = config_manager.secure_decode(er_config['username'])
        if 'password' in er_config:
            er_config['password'] = config_manager.secure_decode(er_config['password'])
        
        if config.get('email') and 'password' in config['email']:
            config['email']['password'] = config_manager.secure_decode(config['email']['password'])
        
        # Test the connection with correct URL
        print("\n🧪 Testing connection with updated configuration...")
        
        if config_manager.test_connection(config):
            print("🎉 SUCCESS! EarthRanger connection working!")
            print("\n📋 Next steps:")
            print("1. Run test report: python test_report.py")
            print("2. Review the test output") 
            print("3. Enable automation: python enable_automation.py")
            return True
        else:
            print("❌ Connection still failing. Please check:")
            print("- Your EarthRanger token is valid")
            print("- You have access to the SpoorTrack data")
            print("- Your token hasn't expired")
            return False
    else:
        print("❌ Failed to save configuration")
        return False

def show_r_config_details():
    """Show the configuration details found in R tools"""
    print("Configuration details from your working R Shiny tools:")
    print("=" * 55)
    print("🌐 EarthRanger Instance: twiga.pamdas.org")
    print("🔗 API Base URL: https://twiga.pamdas.org/api/v1.0/")
    print("🔑 Authentication: Bearer token")
    print("📊 Endpoints used:")
    print("   - /api/v1.0/activity/events/ (for giraffe encounters)")
    print("   - /api/v1.0/subjects/ (for collar subjects)")
    print("\nThis matches the standard EarthRanger API structure ✅")
    print()

if __name__ == "__main__":
    show_r_config_details()
    success = update_from_r_config()
    
    if not success:
        print("\n🛠️ Manual troubleshooting:")
        print("1. Check your EarthRanger token is still valid")
        print("2. Try logging into https://twiga.pamdas.org/ in browser")
        print("3. Verify you can see SpoorTrack collar data there")
