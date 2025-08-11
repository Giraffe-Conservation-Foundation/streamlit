#!/usr/bin/env python3
"""
Password Hash Generator for Funding Summary Dashboard
Run this script to generate a secure hash for your password
"""

import hashlib
import getpass
import os

def generate_password_hash():
    """Generate SHA-256 hash for password"""
    print("=== Funding Summary Password Generator ===")
    print("This will generate a secure hash for your funding dashboard password.")
    print()
    
    while True:
        password = getpass.getpass("Enter new password: ")
        confirm = getpass.getpass("Confirm password: ")
        
        if password == confirm:
            if len(password) < 8:
                print("❌ Password must be at least 8 characters long")
                continue
            if not any(c.isupper() for c in password):
                print("❌ Password must contain at least one uppercase letter")
                continue
            if not any(c.islower() for c in password):
                print("❌ Password must contain at least one lowercase letter")
                continue
            if not any(c.isdigit() for c in password):
                print("❌ Password must contain at least one number")
                continue
            if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
                print("❌ Password must contain at least one special character")
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
    print("🔒 The entered password will not be stored anywhere.")
    
    # Clear password from memory
    password = None
    confirm = None

if __name__ == "__main__":
    try:
        generate_password_hash()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled.")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        # Clear any sensitive data from memory
        import gc
        gc.collect()
