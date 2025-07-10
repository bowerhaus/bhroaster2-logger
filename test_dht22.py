#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import json
import time
import logging
from sensors.dht22 import DHT22Sensor

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_dht22():
    """Test DHT22 sensor reading"""
    
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Find DHT22 sensor config
    dht22_config = None
    for sensor_config in config['sensors']:
        if sensor_config['type'] == 'DHT22':
            dht22_config = sensor_config
            break
    
    if not dht22_config:
        logger.error("No DHT22 sensor found in config.json")
        return False
    
    # Create and initialize sensor
    sensor = DHT22Sensor(dht22_config['name'], dht22_config)
    
    if not sensor.initialize():
        logger.error("Failed to initialize DHT22 sensor")
        return False
    
    logger.info(f"Testing DHT22 sensor: {sensor.name}")
    logger.info(f"GPIO Pin: {sensor.gpio_pin}")
    logger.info(f"Metrics: {sensor.get_metrics()}")
    logger.info(f"Mock mode: {sensor.mock_mode}")
    
    # Take 10 readings
    successful_readings = 0
    
    for i in range(10):
        logger.info(f"Reading {i+1}/10...")
        
        data = sensor.read()
        if data:
            logger.info(f"  Temperature: {data['temperature']}°C")
            logger.info(f"  Humidity: {data['humidity']}%")
            successful_readings += 1
        else:
            logger.warning("  Failed to read data")
        
        time.sleep(2)  # DHT22 needs 2 seconds between readings
    
    logger.info(f"Test completed: {successful_readings}/10 successful readings")
    logger.info(f"Sensor health: {'OK' if sensor.is_healthy() else 'ERROR'}")
    logger.info(f"Error count: {sensor.error_count}")
    
    # Cleanup
    sensor.cleanup()
    
    return successful_readings > 0

if __name__ == "__main__":
    try:
        success = test_dht22()
        if success:
            logger.info("DHT22 test completed successfully!")
            sys.exit(0)
        else:
            logger.error("DHT22 test failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        sys.exit(1)