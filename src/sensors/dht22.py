import time
import logging
from typing import Dict, Optional
from .base import SensorBase

try:
    import board
    import digitalio
    import adafruit_dht
    HAS_HARDWARE = True
except ImportError:
    HAS_HARDWARE = False

logger = logging.getLogger(__name__)


class DHT22Sensor(SensorBase):
    """DHT22 temperature and humidity sensor"""
    
    def __init__(self, name: str, config: Dict):
        super().__init__(name, config)
        self.gpio_pin = config.get('gpio_pin', 4)
        self.dht_device = None
        self.mock_mode = not HAS_HARDWARE
        
        if self.mock_mode:
            logger.warning(f"DHT22 sensor {name} running in mock mode - hardware libraries not available")
    
    def initialize(self) -> bool:
        """Initialize DHT22 sensor"""
        try:
            if self.mock_mode:
                logger.info(f"DHT22 sensor {self.name} initialized in mock mode")
                return True
                
            # Map GPIO pin number to board pin
            pin_map = {
                4: board.D4,
                17: board.D17,
                18: board.D18,
                27: board.D27,
                22: board.D22,
                23: board.D23,
                24: board.D24,
                25: board.D25,
            }
            
            if self.gpio_pin not in pin_map:
                raise ValueError(f"GPIO pin {self.gpio_pin} not supported")
                
            self.dht_device = adafruit_dht.DHT22(pin_map[self.gpio_pin])
            logger.info(f"DHT22 sensor {self.name} initialized on GPIO pin {self.gpio_pin}")
            return True
            
        except Exception as e:
            self.log_error(f"Failed to initialize: {e}")
            return False
    
    def read(self) -> Optional[Dict[str, float]]:
        """Read temperature and humidity from DHT22"""
        try:
            if self.mock_mode:
                # Return mock data for testing
                import random
                return {
                    'temperature': round(20.0 + random.uniform(-2, 10), 1),
                    'humidity': round(45.0 + random.uniform(-5, 15), 1)
                }
            
            if not self.dht_device:
                if not self.initialize():
                    return None
            
            temperature = self.dht_device.temperature
            humidity = self.dht_device.humidity
            
            if temperature is None or humidity is None:
                self.log_error("Failed to read sensor data - returned None")
                return None
            
            # Validate readings
            if temperature < -40 or temperature > 80:
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
            
        except RuntimeError as e:
            # DHT sensors can be flaky, this is normal
            if "timeout" in str(e).lower():
                logger.debug(f"DHT22 {self.name} read timeout (normal)")
            else:
                self.log_error(f"Runtime error: {e}")
            return None
            
        except Exception as e:
            self.log_error(f"Unexpected error reading sensor: {e}")
            return None
    
    def cleanup(self):
        """Clean up sensor resources"""
        if self.dht_device and hasattr(self.dht_device, 'deinit'):
            try:
                self.dht_device.deinit()
                logger.info(f"DHT22 sensor {self.name} cleaned up")
            except Exception as e:
                logger.warning(f"Error cleaning up DHT22 sensor {self.name}: {e}")