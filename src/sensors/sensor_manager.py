import threading
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class SensorManager:
    """Manages sensor readings in the main thread to avoid GPIO conflicts"""
    
    def __init__(self):
        self.sensors = {}
        self.cached_readings = {}
        self.reading_thread = None
        self.stop_event = threading.Event()
        self.running = False
        
    def add_sensor(self, sensor_key: str, sensor):
        """Add a sensor to be managed"""
        self.sensors[sensor_key] = sensor
        self.cached_readings[sensor_key] = None
        logger.info(f"Added sensor to manager: {sensor_key}")
    
    def start_reading(self):
        """Start the sensor reading thread"""
        if self.running:
            logger.warning("Sensor reading already running")
            return
            
        self.running = True
        self.stop_event.clear()
        self.reading_thread = threading.Thread(target=self._reading_loop)
        self.reading_thread.daemon = True
        self.reading_thread.start()
        logger.info("Started sensor reading thread")
    
    def stop_reading(self):
        """Stop the sensor reading thread"""
        if not self.running:
            return
            
        self.running = False
        self.stop_event.set()
        
        if self.reading_thread:
            self.reading_thread.join(timeout=5)
            
        logger.info("Stopped sensor reading thread")
    
    def get_reading(self, sensor_key: str) -> Optional[Dict[str, float]]:
        """Get cached reading for a sensor"""
        cached = self.cached_readings.get(sensor_key)
        logger.debug(f"Raw cached reading for {sensor_key}: {cached}")
        if cached is None:
            logger.debug(f"Available cache keys: {list(self.cached_readings.keys())}")
        return cached
    
    def _reading_loop(self):
        """Main sensor reading loop - runs in dedicated thread"""
        logger.info("Sensor reading loop started")
        
        while self.running and not self.stop_event.is_set():
            try:
                for sensor_name, sensor in self.sensors.items():
                    try:
                        # Read from sensor
                        data = sensor.read()
                        
                        if data:
                            # Only update cache on successful reads
                            self.cached_readings[sensor_name] = {
                                'data': data,
                                'timestamp': datetime.now(),
                                'success': True
                            }
                            logger.info(f"Sensor manager read from {sensor_name}: {data}")
                            logger.debug(f"Stored cache with key '{sensor_name}': {self.cached_readings[sensor_name]}")
                        else:
                            logger.warning(f"Sensor manager failed to read from {sensor_name} - keeping last good reading")
                            
                    except Exception as e:
                        logger.error(f"Error reading {sensor_name}: {e} - keeping last good reading")
                
                # Wait 2 seconds between readings (DHT22 requirement)
                if not self.stop_event.wait(timeout=2.0):
                    continue
                else:
                    break
                    
            except Exception as e:
                logger.error(f"Error in sensor reading loop: {e}")
                time.sleep(1)
        
        logger.info("Sensor reading loop ended")


# Global sensor manager instance
sensor_manager = SensorManager()