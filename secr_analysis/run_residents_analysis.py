#!/usr/bin/env python3
"""
Python wrapper for residents-only mark-recapture analysis
Call R script from Python applications
"""

import subprocess
import json
from pathlib import Path


class ResidentsMRAnalysis:
    """Wrapper for running residents-only mark-recapture analysis"""
    
    def __init__(self, rscript_path=None, workflow_path=None):
        """
        Initialize the analysis wrapper
        
        Args:
            rscript_path: Path to Rscript.exe (default: standard Windows location)
            workflow_path: Path to the R script (default: same dir as this file)
        """
        if rscript_path is None:
            self.rscript_path = r"C:\Program Files\R\R-4.2.1\bin\Rscript.exe"
        else:
            self.rscript_path = rscript_path
            
        if workflow_path is None:
            # Default: look in same directory as this Python file
            this_dir = Path(__file__).parent
            self.workflow_path = this_dir / "residents_only_analysis_parameterized.R"
        else:
            self.workflow_path = Path(workflow_path)
    
    def run_analysis(self, data_directory, verbose=True):
        """
        Run the residents-only mark-recapture analysis
        
        Args:
            data_directory: Path to directory containing spatial_captures.csv 
                           and capture_history.csv
            verbose: Print R script output to console
        
        Returns:
            dict: Results from the analysis (parsed from JSON output file)
        
        Raises:
            FileNotFoundError: If R script or data files don't exist
            subprocess.CalledProcessError: If R script fails
        """
        data_dir = Path(data_directory)
        
        # Validate inputs
        if not Path(self.rscript_path).exists():
            raise FileNotFoundError(f"Rscript not found: {self.rscript_path}")
        
        if not self.workflow_path.exists():
            raise FileNotFoundError(f"R workflow not found: {self.workflow_path}")
        
        if not data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {data_dir}")
        
        # Expected data files
        captures_file = data_dir / "spatial_captures.csv"
        ch_file = data_dir / "capture_history.csv"
        
        if not captures_file.exists():
            raise FileNotFoundError(f"Required file not found: {captures_file}")
        if not ch_file.exists():
            raise FileNotFoundError(f"Required file not found: {ch_file}")
        
        # Run R script
        cmd = [
            str(self.rscript_path),
            str(self.workflow_path),
            str(data_dir)
        ]
        
        if verbose:
            print(f"Running: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        if verbose:
            print(result.stdout)
        
        if result.stderr:
            print("Warnings:", result.stderr)
        
        # Load and return results
        results_file = data_dir / "residents_only_results.json"
        if results_file.exists():
            with open(results_file, 'r') as f:
                return json.load(f)
        else:
            raise FileNotFoundError(f"Results file not created: {results_file}")
    
    def get_population_estimate(self, data_directory):
        """
        Quick method to get just the population estimate
        
        Returns:
            float: Total population estimate (residents + transients)
        """
        results = self.run_analysis(data_directory, verbose=False)
        return results['total_estimate']['N']


# Example usage
if __name__ == "__main__":
    import sys
    
    # Initialize the wrapper
    analyzer = ResidentsMRAnalysis()
    
    # Get data directory from command line or use default
    if len(sys.argv) > 1:
        data_dir = sys.argv[1]
    else:
        data_dir = "secr_data_central_tuli"
    
    print(f"Analyzing data from: {data_dir}\n")
    
    try:
        # Run the analysis
        results = analyzer.run_analysis(data_dir)
        
        # Print summary
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        print(f"Location: {results['location']}")
        print(f"Total individuals: {results['total_individuals']}")
        print(f"  Residents: {results['residents']}")
        print(f"  Transients: {results['transients']}")
        print(f"\nPopulation estimate: N = {results['total_estimate']['N']}")
        print(f"Resident estimate: N = {results['resident_estimate']['N']} "
              f"(95% CI: {results['resident_estimate']['CI_lower']} - "
              f"{results['resident_estimate']['CI_upper']})")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
