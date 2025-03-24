#!/usr/bin/env python3
"""Run all tests in the tests directory and its subdirectories using pytest.

Usage:
    ./run_tests.py
"""

import os
import sys
import subprocess

def main():
    """Run all tests using pytest."""
    # Add the project root to the Python path
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)
    
    # Make sure tests directory exists
    tests_dir = os.path.join(project_root, 'tests')
    if not os.path.exists(tests_dir):
        print(f"Error: Tests directory not found: {tests_dir}")
        sys.exit(1)
    
    # Run pytest
    print("Running tests with pytest...")
    pytest_args = [
        "pytest",
        "-v",
        "-c",
        tests_dir  # Path to tests directory
    ]
    
    # Run pytest as a subprocess
    print(f"command: {' '.join(pytest_args)}")
    result = subprocess.Popen(pytest_args)
    result.wait()

    # Exit with the same status code as pytest
    sys.exit(result.returncode)

if __name__ == '__main__':
    main()