import time
import logging
from typing import Dict, Optional
from .base import SensorBase
from .sensor_manager import sensor_manager

try:
    import board
    import adafruit_sgp30
    HAS_HARDWARE = True
except ImportError:
    HAS_HARDWARE = False

logger = logging.getLogger(__name__)


class ManagedSGP30Sensor(SensorBase):
    """SGP30 sensor for VOC and CO2 readings that uses SensorManager for thread-safe readings"""
    
    def __init__(self, name: str, config: Dict):
        super().__init__(name, config)
        self.i2c_address = config.get('i2c_address', 0x58)  # Default SGP30 address
        self.sgp30_device = None
        self.mock_mode = not HAS_HARDWARE
        self.manager_key = f"sgp30_{name}"
        self.baseline_co2 = config.get('baseline_co2', 0x8973)  # Default baseline
        self.baseline_tvoc = config.get('baseline_tvoc', 0x8AAE)  # Default baseline
        self.warm_up_time = 15  # SGP30 needs 15 seconds to warm up
        self.initialization_time = None
        
        if self.mock_mode:
            logger.warning(f"SGP30 sensor {name} running in mock mode - hardware libraries not available")
    
    def initialize(self) -> bool:
        """Initialize SGP30 sensor and add to sensor manager"""
        try:
            if self.mock_mode:
                logger.warning(f"SGP30 sensor {self.name} initialized in MOCK MODE - no hardware detected")
                sensor_manager.add_sensor(self.manager_key, self)
                self.initialization_time = time.time()
                return True
                
            # Initialize I2C bus
            i2c = board.I2C()
            self.sgp30_device = adafruit_sgp30.Adafruit_SGP30(i2c)
            
            # Initialize the sensor
            logger.info(f"SGP30 sensor {self.name} initializing - this may take a moment...")
            self.sgp30_device.iaq_init()
            
            # Set baseline if provided
            if self.baseline_co2 and self.baseline_tvoc:
                self.sgp30_device.set_iaq_baseline(self.baseline_co2, self.baseline_tvoc)
                logger.info(f"SGP30 baseline set: CO2={self.baseline_co2:04x}, TVOC={self.baseline_tvoc:04x}")
            
            # Record initialization time for warm-up period
            self.initialization_time = time.time()
            
            logger.info(f"SGP30 sensor {self.name} initialized on I2C address 0x{self.i2c_address:02x}")
            logger.info(f"Sensor will warm up for {self.warm_up_time} seconds...")
            
            # Add to sensor manager
            sensor_manager.add_sensor(self.manager_key, self)
            return True
            
        except Exception as e:
            self.log_error(f"Failed to initialize: {e}")
            return False
    
    def is_warmed_up(self) -> bool:
        """Check if sensor has completed warm-up period"""
        if self.initialization_time is None:
            return False
        return (time.time() - self.initialization_time) >= self.warm_up_time
    
    def read(self) -> Optional[Dict[str, float]]:
        """Read VOC and CO2 from SGP30 - called by sensor manager"""
        try:
            if self.mock_mode:
                # Return mock data for testing
                import random
                # Simulate warm-up period in mock mode
                if not self.is_warmed_up():
                    return {
                        'co2': 999.0,  # Mock CO2 level during warmup (distinguishable from real 400)
                        'voc': 99.0    # Mock VOC level during warmup (distinguishable from real 0)
                    }
                return {
                    'co2': round(800.0 + random.uniform(0, 400), 0),  # Mock CO2 in ppm (800-1200 range)
                    'voc': round(100.0 + random.uniform(0, 100), 0)   # Mock VOC in ppb (100-200 range)
                }
            
            if not self.sgp30_device:
                return None
            
            # Check if sensor is still warming up
            if not self.is_warmed_up():
                elapsed = time.time() - self.initialization_time if self.initialization_time else 0
                logger.info(f"SGP30 {self.name} still warming up: {elapsed:.1f}s/{self.warm_up_time}s")
                # During warm-up, SGP30 returns default values
                return {
                    'co2': 400.0,  # Default CO2 level during warmup
                    'voc': 0.0     # Default VOC level during warmup
                }
            
            # Read from SGP30
            logger.info(f"SGP30 {self.name} reading from hardware after warm-up")
            co2_eq_ppm = self.sgp30_device.eCO2
            tvoc_ppb = self.sgp30_device.TVOC
            
            logger.info(f"SGP30 raw reading: CO2={co2_eq_ppm}, TVOC={tvoc_ppb}")
            
            if co2_eq_ppm is None or tvoc_ppb is None:
                self.log_error("Failed to read sensor data - returned None")
                return None
            
            # Validate readings
            if co2_eq_ppm < 400 or co2_eq_ppm > 60000:
                self.log_error(f"CO2 out of expected range: {co2_eq_ppm} ppm")
                # Don't return None for out-of-range, just log warning
                # SGP30 can have wide variations especially during startup
            
            if tvoc_ppb < 0 or tvoc_ppb > 60000:
                self.log_error(f"TVOC out of expected range: {tvoc_ppb} ppb")
                # Don't return None for out-of-range, just log warning
            
            self.last_reading = {
                'co2': float(co2_eq_ppm),
                'voc': float(tvoc_ppb)
            }
            self.last_reading_time = time.time()
            self.reset_error_count()
            
            return self.last_reading
            
        except Exception as e:
            self.log_error(f"Error reading sensor: {e}")
            return None
    
    def get_cached_reading(self) -> Optional[Dict[str, float]]:
        """Get cached reading from sensor manager - called by data collector"""
        cached = sensor_manager.get_reading(self.manager_key)
        logger.debug(f"Getting cached reading for {self.manager_key}: {cached}")
        if cached and cached.get('success'):
            return cached.get('data')
        return None
    
    def get_baseline(self) -> Optional[Dict[str, int]]:
        """Get current baseline values for saving/restoration"""
        try:
            if self.mock_mode or not self.sgp30_device:
                return None
            
            co2_baseline, tvoc_baseline = self.sgp30_device.get_iaq_baseline()
            return {
                'co2_baseline': co2_baseline,
                'tvoc_baseline': tvoc_baseline
            }
        except Exception as e:
            self.log_error(f"Error getting baseline: {e}")
            return None
    
    def cleanup(self):
        """Clean up sensor resources"""
        # Log baseline for future use if available
        baseline = self.get_baseline()
        if baseline:
            logger.info(f"SGP30 sensor {self.name} final baseline: CO2={baseline['co2_baseline']:04x}, TVOC={baseline['tvoc_baseline']:04x}")
        
        logger.info(f"SGP30 sensor {self.name} cleaned up")