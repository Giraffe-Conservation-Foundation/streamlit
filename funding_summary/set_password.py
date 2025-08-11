#!/usr/bin/env python3
"""
Password Hash Generator for Funding Summary Dashboard
Run this script to generate a secure hash for your password
"""

import hashlib
import getpass

def generate_password_hash():
    """Generate SHA-256 hash for password"""
    print("=== Funding Summary Password Generator ===")
    print("This will generate a secure hash for your funding dashboard password.")
    print()
    
    while True:
        password = getpass.getpass("Enter new password: ")
        confirm = getpass.getpass("Confirm password: ")
        
        if password == confirm:
            if len(password) < 6:
                print("❌ Password must be at least 6 characters long")
                continue
            break
        else:
            print("❌ Passwords don't match. Please try again.")
    
    # Generate hash
    hash_value = hashlib.sha256(password.encode()).hexdigest()
    
    print("\n✅ Password hash generated successfully!")
    print(f"Hash: {hash_value}")
    print()
    print("To update the funding dashboard:")
    print("1. Open funding_summary/app.py")
    print("2. Find the line: FUNDING_PASSWORD_HASH = \"...\"")
    print(f"3. Replace the hash with: \"{hash_value}\"")
    print()
    print("⚠️  Keep this hash secure and don't share it!")

if __name__ == "__main__":
    generate_password_hash()
