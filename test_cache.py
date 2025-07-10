#!/usr/bin/env python3
"""Test script to verify sensor cache is working"""

import sys
import os
import time
import json

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from sensors.managed_dht22 import ManagedDHT22Sensor
from sensors.sensor_manager import sensor_manager

def test_cache():
    """Test that sensor cache preserves good readings"""
    
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Initialize sensor
    sensor_config = config['sensors'][0]  # DHT22
    sensor = ManagedDHT22Sensor(sensor_config['name'], sensor_config)
    
    if not sensor.initialize():
        print("Failed to initialize sensor")
        return False
    
    # Start sensor manager
    sensor_manager.start_reading()
    
    print("Testing cache for 10 seconds...")
    print("Sensor manager should read every 2 seconds")
    print("Cache should preserve good readings even when sensor fails")
    print()
    
    for i in range(10):
        time.sleep(1)
        
        # Try to get cached reading (like data collector does)
        cached_data = sensor.get_cached_reading()
        
        if cached_data:
            print(f"Second {i+1}: Cache hit - {cached_data}")
        else:
            print(f"Second {i+1}: Cache miss - None")
    
    # Stop sensor manager
    sensor_manager.stop_reading()
    
    print("\nTest complete!")
    return True

if __name__ == "__main__":
    test_cache()