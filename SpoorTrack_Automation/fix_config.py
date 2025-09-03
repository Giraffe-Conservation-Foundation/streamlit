#!/usr/bin/env python3
"""
Fix EarthRanger URL in configuration
"""

import json
from pathlib import Path
from secure_setup import SecureSpoorTrackConfig

def fix_url():
    """Fix the EarthRanger URL to include https://"""
    
    config_manager = SecureSpoorTrackConfig()
    config = config_manager.load_config()
    
    if not config:
        print("No configuration found")
        return
    
    current_url = config['earthranger']['server']
    print(f"Current URL: {current_url}")
    
    # Fix URL if missing protocol
    if not current_url.startswith(('http://', 'https://')):
        fixed_url = f"https://{current_url}"
        config['earthranger']['server'] = fixed_url
        print(f"Fixed URL: {fixed_url}")
        
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
        
        # Save fixed config
        if config_manager.save_config(config):
            print("Configuration updated successfully!")
            
            # Test the connection
            print("Testing connection with fixed URL...")
            
            # Decrypt for testing
            if 'token' in er_config:
                er_config['token'] = config_manager.secure_decode(er_config['token'])
            if 'username' in er_config:
                er_config['username'] = config_manager.secure_decode(er_config['username'])
            if 'password' in er_config:
                er_config['password'] = config_manager.secure_decode(er_config['password'])
            
            if config.get('email') and 'password' in config['email']:
                config['email']['password'] = config_manager.secure_decode(config['email']['password'])
            
            if config_manager.test_connection(config):
                print("SUCCESS! Connection test passed!")
                print("You can now run: python test_report.py")
            else:
                print("Connection test failed - please check your credentials")
        else:
            print("Failed to save configuration")
    else:
        print("URL already has protocol - testing connection...")
        if config_manager.test_connection(config):
            print("SUCCESS! Connection test passed!")
        else:
            print("Connection test failed")

if __name__ == "__main__":
    fix_url()
