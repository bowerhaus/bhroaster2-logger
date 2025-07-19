#!/usr/bin/env python3
"""
One-time script to truncate existing roasts to maximum time limit.
Run this script after adding the max_roast_time_minutes configuration.
"""

import sys
import os
import json
import logging
from datetime import datetime

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database.models import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config():
    """Load configuration from config.json"""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    with open(config_path, 'r') as f:
        return json.load(f)

def main():
    """Main function to truncate roasts"""
    try:
        # Load configuration
        config = load_config()
        max_time_minutes = config.get('session', {}).get('max_roast_time_minutes', 16)
        
        logger.info(f"Starting roast truncation with max time: {max_time_minutes} minutes")
        
        # Initialize database manager
        db_path = config['database']['path']
        db_manager = DatabaseManager(db_path)
        
        # Run truncation
        results = db_manager.truncate_roasts_to_max_time(max_time_minutes)
        
        # Print results
        print(f"\n=== Roast Truncation Results ===")
        print(f"Total roasts processed: {results['processed']}")
        print(f"Roasts truncated: {results['truncated']}")
        print(f"Errors encountered: {results['errors']}")
        
        if results['truncated'] > 0:
            print(f"\n=== Truncated Roasts Details ===")
            for detail in results['details']:
                if 'error' in detail:
                    print(f"ERROR: {detail['error']}")
                else:
                    print(f"Roast: {detail['name']} ({detail['roast_id'][:8]}...)")
                    print(f"  Start: {detail['start_time']}")
                    print(f"  Original End: {detail['original_end_time']}")
                    print(f"  New End: {detail['new_end_time']}")
                    print(f"  Data Points: {detail['deleted_points']} removed, {detail['remaining_points']} remaining")
                    print()
        
        if results['errors'] == 0:
            print("✅ Truncation completed successfully!")
        else:
            print(f"⚠️  Truncation completed with {results['errors']} errors. Check logs for details.")
            
    except Exception as e:
        logger.error(f"Failed to run truncation: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()