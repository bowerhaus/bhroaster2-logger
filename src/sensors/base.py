from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import time
import logging

logger = logging.getLogger(__name__)


class SensorBase(ABC):
    """Base class for all sensors"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.last_reading = None
        self.last_reading_time = None
        self.error_count = 0
        
    @abstractmethod
    def read(self) -> Optional[Dict[str, float]]:
        """Read sensor data and return dictionary of metric_name: value"""
        pass
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize sensor hardware, return True if successful"""
        pass
    
    def get_metrics(self) -> list:
        """Return list of metrics this sensor provides"""
        return self.config.get('metrics', [])
    
    def is_healthy(self) -> bool:
        """Check if sensor is functioning properly"""
        return self.error_count < 5
    
    def reset_error_count(self):
        """Reset error counter"""
        self.error_count = 0
        
    def log_error(self, error_msg: str):
        """Log sensor error and increment counter"""
        logger.error(f"Sensor {self.name}: {error_msg}")
        self.error_count += 1