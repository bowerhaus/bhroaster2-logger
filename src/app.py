#!/usr/bin/env python3

"""
Main entry point for the Coffee Roaster Data Logger application.
This script starts the web application with sensor data collection.
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.dirname(__file__))

from web.app import run_app

if __name__ == '__main__':
    try:
        run_app()
    except KeyboardInterrupt:
        print("\nShutting down Coffee Roaster Logger...")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)