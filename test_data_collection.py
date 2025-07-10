#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import json
import time
import logging
from datetime import datetime
from database.models import DatabaseManager
from sensors.dht22 import DHT22Sensor
from services.data_collector import DataCollector

# Mock SocketIO for testing
class MockSocketIO:
    def emit(self, event, data):
        print(f"SocketIO Event: {event} - Data: {data}")

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_data_collection():
    """Test the complete data collection process"""
    
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Initialize database
    db_manager = DatabaseManager(config['database']['path'])
    
    # Initialize sensors
    sensors = {}
    for sensor_config in config['sensors']:
        if sensor_config['type'] == 'DHT22':
            sensor = DHT22Sensor(sensor_config['name'], sensor_config)
            if sensor.initialize():
                sensors[sensor_config['name']] = sensor
                logger.info(f"Initialized sensor: {sensor_config['name']}")
    
    if not sensors:
        logger.error("No sensors initialized!")
        return False
    
    # Initialize data collector
    mock_socketio = MockSocketIO()
    data_collector = DataCollector(sensors, db_manager, mock_socketio, sample_rate=1)
    
    # Create a test roast session
    roast_name = f"Test Roast {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    roast_id = db_manager.create_roast_session(roast_name)
    logger.info(f"Created test roast session: {roast_id}")
    
    # Start data collection
    logger.info("Starting data collection...")
    data_collector.start_collection(roast_id)
    
    # Let it collect data for 10 seconds
    logger.info("Collecting data for 10 seconds...")
    time.sleep(10)
    
    # Stop data collection
    logger.info("Stopping data collection...")
    data_collector.stop_collection()
    
    # Stop the roast session
    db_manager.end_roast_session(roast_id)
    
    # Check results
    data_points = db_manager.get_roast_data(roast_id)
    logger.info(f"Collected {len(data_points)} data points")
    
    if data_points:
        logger.info("Sample data points:")
        for i, point in enumerate(data_points[:5]):
            logger.info(f"  {i+1}. {point['timestamp']} - {point['sensor_name']} - {point['metric_type']}: {point['value']}{point['unit']}")
        return True
    else:
        logger.error("No data points collected!")
        return False

if __name__ == "__main__":
    try:
        success = test_data_collection()
        if success:
            print("\n✅ Data collection test PASSED!")
        else:
            print("\n❌ Data collection test FAILED!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)