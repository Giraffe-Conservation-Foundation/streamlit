#!/usr/bin/env python3
"""
Launcher script for the Giraffe Conservation Image Management System
"""

import sys
import os
import subprocess
from pathlib import Path

def main():
    """Main launcher function"""
    
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.absolute()
    
    # Change to the application directory
    os.chdir(script_dir)
    
    # Check if we're in a virtual environment
    venv_python = script_dir / ".venv" / "Scripts" / "python.exe"
    
    if venv_python.exists():
        python_executable = str(venv_python)
        print(f"Using virtual environment Python: {python_executable}")
    else:
        python_executable = sys.executable
        print(f"Using system Python: {python_executable}")
    
    print("Starting Giraffe Conservation Image Management System...")
    print("=" * 60)
    print("🦒 Welcome to the Giraffe Image Management System!")
    print("🌐 The app will open in your default web browser")
    print("🔄 Press Ctrl+C to stop the application")
    print("=" * 60)
    
    try:
        # Launch Streamlit
        cmd = [
            python_executable, 
            "-m", "streamlit", "run", "app.py",
            "--server.headless", "false",
            "--server.port", "8501",
            "--server.address", "localhost"
        ]
        
        subprocess.run(cmd, check=True)
        
    except KeyboardInterrupt:
        print("\n🛑 Application stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running application: {e}")
        print("\nPlease check that all dependencies are installed:")
        print("pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
