import sys
import os

# Add parent directory to path to import the genetic_dashboard app
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Import the genetic dashboard
from genetic_dashboard.app import main

# Run the genetic dashboard
if __name__ == "__main__":
    main()
