import time
import logging
from typing import Dict, Optional
from .base import SensorBase
from .sensor_manager import sensor_manager

try:
    import board
    import adafruit_sht31d
    HAS_HARDWARE = True
except ImportError:
    HAS_HARDWARE = False

logger = logging.getLogger(__name__)


class ManagedSHT31Sensor(SensorBase):
    """SHT31 sensor that uses SensorManager for thread-safe readings"""
    
    def __init__(self, name: str, config: Dict):
        super().__init__(name, config)
        self.i2c_address = config.get('i2c_address', 0x44)  # Default SHT31 address
        self.sht31_device = None
        self.mock_mode = not HAS_HARDWARE
        self.manager_key = f"sht31_{name}"
        
        if self.mock_mode:
            logger.warning(f"SHT31 sensor {name} running in mock mode - hardware libraries not available")
    
    def initialize(self) -> bool:
        """Initialize SHT31 sensor and add to sensor manager"""
        try:
            if self.mock_mode:
                logger.info(f"SHT31 sensor {self.name} initialized in mock mode")
                # Add mock sensor to manager
                sensor_manager.add_sensor(self.manager_key, self)
                return True
                
            # Initialize I2C bus
            i2c = board.I2C()
            self.sht31_device = adafruit_sht31d.SHT31D(i2c, address=self.i2c_address)
            
            # Test read to verify sensor is connected
            test_temp = self.sht31_device.temperature
            test_humidity = self.sht31_device.relative_humidity
            
            if test_temp is not None and test_humidity is not None:
                logger.info(f"SHT31 sensor {self.name} initialized on I2C address 0x{self.i2c_address:02x}")
                logger.info(f"Initial reading: {test_temp:.1f}°C, {test_humidity:.1f}%")
                
                # Add to sensor manager
                sensor_manager.add_sensor(self.manager_key, self)
                return True
            else:
                logger.error(f"SHT31 sensor {self.name} test read failed")
                return False
            
        except Exception as e:
            self.log_error(f"Failed to initialize: {e}")
            return False
    
    def read(self) -> Optional[Dict[str, float]]:
        """Read temperature and humidity from SHT31 - called by sensor manager"""
        try:
            if self.mock_mode:
                # Return mock data for testing
                import random
                return {
                    'temperature': round(20.0 + random.uniform(-2, 10), 1),
                    'humidity': round(45.0 + random.uniform(-5, 15), 1)
                }
            
            if not self.sht31_device:
                return None
            
            # Read from SHT31 - much more reliable than DHT22
            temperature = self.sht31_device.temperature
            humidity = self.sht31_device.relative_humidity
            
            if temperature is None or humidity is None:
                self.log_error("Failed to read sensor data - returned None")
                return None
            
            # Validate readings (SHT31 has wider valid range than DHT22)
            if temperature < -40 or temperature > 125:
                self.log_error(f"Temperature out of range: {temperature}°C")
                return None
                
            if humidity < 0 or humidity > 100:
                self.log_error(f"Humidity out of range: {humidity}%")
                return None
            
            self.last_reading = {
                'temperature': round(temperature, 1),
                'humidity': round(humidity, 1)
            }
            self.last_reading_time = time.time()
            self.reset_error_count()
            
            return self.last_reading
            
        except Exception as e:
            # SHT31 should have much fewer communication errors
            self.log_error(f"Error reading sensor: {e}")
            return None
    
    def get_cached_reading(self) -> Optional[Dict[str, float]]:
        """Get cached reading from sensor manager - called by data collector"""
        cached = sensor_manager.get_reading(self.manager_key)
        logger.debug(f"Getting cached reading for {self.manager_key}: {cached}")
        if cached and cached.get('success'):
            return cached.get('data')
        return None
    
    def cleanup(self):
        """Clean up sensor resources"""
        # SHT31 doesn't require explicit cleanup like DHT22
        logger.info(f"SHT31 sensor {self.name} cleaned up")