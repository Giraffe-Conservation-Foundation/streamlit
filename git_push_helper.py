#!/usr/bin/env python3
"""
Git Push Helper Script
Manually handle git operations when terminal is unresponsive
"""

import subprocess
import os
import sys
from pathlib import Path

def run_git_command(command, description):
    """Run a git command and return the result"""
    try:
        print(f"\n🔄 {description}")
        print(f"Running: {command}")
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        
        if result.returncode == 0:
            print(f"✅ Success!")
            if result.stdout.strip():
                print(f"Output: {result.stdout.strip()}")
        else:
            print(f"❌ Error (return code: {result.returncode})")
            if result.stderr.strip():
                print(f"Error: {result.stderr.strip()}")
            if result.stdout.strip():
                print(f"Output: {result.stdout.strip()}")
        
        return result.returncode == 0, result.stdout, result.stderr
        
    except Exception as e:
        print(f"❌ Exception running command: {e}")
        return False, "", str(e)

def main():
    """Main function to handle git operations"""
    print("🚀 Git Push Helper Script")
    print("=" * 50)
    
    # Change to the correct directory
    os.chdir(Path(__file__).parent)
    print(f"Working directory: {os.getcwd()}")
    
    # Check git status
    success, stdout, stderr = run_git_command("git status --porcelain", "Checking git status")
    
    if success:
        if stdout.strip():
            print(f"\n📋 Changes detected:")
            for line in stdout.strip().split('\n'):
                print(f"  {line}")
        else:
            print(f"\n✨ No changes detected")
            return
    
    # Show detailed status
    success, stdout, stderr = run_git_command("git status", "Detailed git status")
    
    # Add all changes
    success, stdout, stderr = run_git_command("git add -A", "Adding all changes")
    
    if not success:
        print("❌ Failed to add changes")
        return
    
    # Commit changes
    commit_message = """remove: Delete Source Dashboard page from navigation

- Remove pages/6_🌍_Source_Dashboard.py to eliminate Source Dashboard from sidebar
- Source Dashboard functionality replaced by Unit Check dashboard
- Cleans up navigation after implementing new Unit Check feature"""
    
    success, stdout, stderr = run_git_command(
        f'git commit -m "{commit_message}"',
        "Committing changes"
    )
    
    if not success:
        if "nothing to commit" in stderr.lower() or "nothing to commit" in stdout.lower():
            print("✨ Nothing to commit - all changes already committed")
        else:
            print("❌ Failed to commit changes")
            return
    
    # Push to origin
    success, stdout, stderr = run_git_command("git push origin main", "Pushing to GitHub")
    
    if success:
        print("\n🎉 Successfully pushed changes to GitHub!")
        print("The Source Dashboard should be removed from the navigation shortly.")
    else:
        print("\n❌ Failed to push to GitHub")
        print("You may need to check your authentication or network connection")

if __name__ == "__main__":
    main()