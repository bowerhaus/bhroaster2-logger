import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
import json

logger = logging.getLogger(__name__)


class DataCollector:
    """Service for collecting sensor data at regular intervals"""
    
    def __init__(self, sensors: Dict[str, Any], db_manager, socketio, sample_rate: int = 1, config: Dict = None):
        self.sensors = sensors
        self.db_manager = db_manager
        self.socketio = socketio
        self.sample_rate = sample_rate
        self.active_roast_id = None
        self.collecting = False
        self.collection_thread = None
        self.stop_event = threading.Event()
        self.config = config or {}
        self.max_roast_time_minutes = self.config.get('session', {}).get('max_roast_time_minutes', 16)
        
    def start_collection(self, roast_id: str):
        """Start data collection for a roast session"""
        if self.collecting:
            logger.warning("Data collection already running")
            return False
            
        self.active_roast_id = roast_id
        self.collecting = True
        self.stop_event.clear()
        
        # Start collection thread
        self.collection_thread = threading.Thread(target=self._collection_loop)
        self.collection_thread.daemon = True
        self.collection_thread.start()
        
        logger.info(f"Started data collection for roast {roast_id}")
        return True
    
    def resume_collection(self, roast_id: str):
        """Resume data collection for an existing roast session"""
        logger.info(f"Resuming data collection for roast {roast_id}")
        return self.start_collection(roast_id)
    
    def stop_collection(self):
        """Stop data collection"""
        if not self.collecting:
            logger.warning("Data collection not running")
            return False
            
        self.collecting = False
        self.stop_event.set()
        
        # Wait for thread to finish
        if self.collection_thread:
            self.collection_thread.join(timeout=5)
            
        self.active_roast_id = None
        logger.info("Stopped data collection")
        return True
    
    def _collection_loop(self):
        """Main data collection loop"""
        logger.info("🔄 Data collection loop started")
        
        while self.collecting and not self.stop_event.is_set():
            try:
                logger.debug(f"🔄 Collection loop iteration - collecting: {self.collecting}")
                
                # Check if roast has exceeded max time
                if self._check_max_roast_time_exceeded():
                    logger.info(f"⏰ Max roast time ({self.max_roast_time_minutes} minutes) exceeded, stopping collection")
                    self._auto_stop_roast()
                    break
                
                self._collect_data_point()
                
                # Wait for next sample (returns True if stop event is set)
                if self.stop_event.wait(timeout=self.sample_rate):
                    break  # Stop event was set
                    
            except Exception as e:
                logger.error(f"Error in data collection loop: {e}")
                time.sleep(1)  # Brief pause on error
        
        logger.info("🛑 Data collection loop ended")
    
    def _collect_data_point(self):
        """Collect a single data point from all sensors"""
        if not self.active_roast_id:
            logger.warning("No active roast ID for data collection")
            return
            
        logger.debug(f"Collecting data point for roast {self.active_roast_id}")
        
        for sensor_name, sensor in self.sensors.items():
            try:
                logger.debug(f"Reading from sensor: {sensor_name}")
                # Use cached reading if available, otherwise direct read
                if hasattr(sensor, 'get_cached_reading'):
                    data = sensor.get_cached_reading()
                else:
                    data = sensor.read()
                logger.debug(f"Sensor read completed. Data: {data}")
                
                if data:
                    logger.debug(f"Got data from {sensor_name}: {data}")
                    for metric_type, value in data.items():
                        # Create unique timestamp for each data point
                        timestamp = datetime.now().isoformat()
                        
                        # Map metric types to units
                        unit_map = {
                            'temperature': '°C',
                            'humidity': '%',
                            'co2': 'ppm',
                            'voc': 'ppb'
                        }
                        unit = unit_map.get(metric_type, '')
                        
                        # Store in database
                        success = self.db_manager.add_data_point(
                            self.active_roast_id,
                            sensor_name,
                            metric_type,
                            value,
                            unit
                        )
                        
                        if success:
                            logger.info(f"Stored: {sensor_name} {metric_type}={value}{unit}")
                        else:
                            logger.warning(f"Failed to store data point: {sensor_name}")
                else:
                    logger.warning(f"No data from sensor: {sensor_name}")
                    
            except Exception as e:
                logger.error(f"Error collecting data from {sensor_name}: {e}")
                import traceback
                traceback.print_exc()
    
    def is_collecting(self) -> bool:
        """Check if data collection is active"""
        return self.collecting
    
    def get_active_roast_id(self) -> str:
        """Get the currently active roast ID"""
        return self.active_roast_id
    
    def _check_max_roast_time_exceeded(self) -> bool:
        """Check if the current roast has exceeded the maximum time limit"""
        if not self.active_roast_id:
            return False
        
        try:
            roast_session = self.db_manager.get_roast_session(self.active_roast_id)
            if not roast_session or not roast_session.get('start_time'):
                return False
            
            start_time = datetime.fromisoformat(roast_session['start_time'])
            current_time = datetime.now()
            elapsed_minutes = (current_time - start_time).total_seconds() / 60
            
            return elapsed_minutes >= self.max_roast_time_minutes
            
        except Exception as e:
            logger.error(f"Error checking max roast time: {e}")
            return False
    
    def _auto_stop_roast(self):
        """Automatically stop the roast when max time is exceeded"""
        try:
            if self.active_roast_id:
                # Stop data collection
                self.collecting = False
                
                # End the roast session in database
                success = self.db_manager.end_roast_session(self.active_roast_id)
                
                if success:
                    # Emit event to notify UI
                    if self.socketio:
                        self.socketio.emit('roast_auto_stopped', {
                            'roast_id': self.active_roast_id,
                            'reason': f'Maximum roast time exceeded ({self.max_roast_time_minutes} minutes)',
                            'timestamp': datetime.now().isoformat()
                        })
                    
                    logger.info(f"🔴 Auto-stopped roast {self.active_roast_id} - max time exceeded")
                else:
                    logger.error(f"Failed to auto-stop roast {self.active_roast_id}")
                    
        except Exception as e:
            logger.error(f"Error auto-stopping roast: {e}")