import logging
import math
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class FirstCrackDetector:
    """
    Multi-signal first crack detection system using temperature, VOC, CO2, and humidity data.
    """
    
    def __init__(self, config: Dict = None):
        """Initialize the first crack detector with configuration parameters."""
        self.config = config or {}
        
        # Detection thresholds - can be overridden by config
        self.temp_ror_threshold = self.config.get('TEMP_ROR_THRESHOLD', -2.0)  # °C/min drop
        self.voc_spike_threshold = self.config.get('VOC_SPIKE_THRESHOLD', 1.3)  # 30% increase
        self.co2_spike_threshold = self.config.get('CO2_SPIKE_THRESHOLD', 1.2)  # 20% increase
        self.humidity_spike_threshold = self.config.get('HUMIDITY_SPIKE_THRESHOLD', 1.15)  # 15% increase
        
        # Detection weights
        self.temp_weight = self.config.get('TEMP_WEIGHT', 0.30)
        self.voc_weight = self.config.get('VOC_WEIGHT', 0.40)
        self.co2_weight = self.config.get('CO2_WEIGHT', 0.20)
        self.humidity_weight = self.config.get('HUMIDITY_WEIGHT', 0.10)
        
        # Analysis parameters
        self.window_size = self.config.get('ANALYSIS_WINDOW_SIZE', 120)  # seconds
        self.confidence_threshold = self.config.get('CONFIDENCE_THRESHOLD', 0.75)
        self.min_temp_for_fc = self.config.get('MIN_TEMP_FOR_FC', 180)  # °C - minimum temp to start looking for FC
        
        logger.info(f"FirstCrackDetector initialized with confidence threshold: {self.confidence_threshold}")
    
    def analyze_data_point(self, data_points: List[Dict], current_timestamp: str) -> Optional[Dict]:
        """
        Analyze current data points to detect first crack.
        
        Args:
            data_points: List of recent data points with timestamp, metric_type, value
            current_timestamp: Current timestamp to analyze
            
        Returns:
            Dict with detection results or None if no first crack detected
        """
        # Group data by metric type
        temp_data = [(dp['timestamp'], dp['value']) for dp in data_points if dp['metric_type'] == 'temperature']
        voc_data = [(dp['timestamp'], dp['value']) for dp in data_points if dp['metric_type'] == 'voc']
        co2_data = [(dp['timestamp'], dp['value']) for dp in data_points if dp['metric_type'] == 'co2']
        humidity_data = [(dp['timestamp'], dp['value']) for dp in data_points if dp['metric_type'] == 'humidity']
        
        # Check if we have enough data and minimum temperature
        if not temp_data:
            return None
            
        current_temp = temp_data[-1][1] if temp_data else 0
        if current_temp < self.min_temp_for_fc:
            return None
        
        # Calculate confidence scores for each signal
        temp_score = self._analyze_temperature_ror(temp_data, current_timestamp)
        voc_score = self._analyze_voc_spike(voc_data, current_timestamp)
        co2_score = self._analyze_co2_pattern(co2_data, current_timestamp)
        humidity_score = self._analyze_humidity_response(humidity_data, current_timestamp)
        
        # Calculate weighted confidence score
        total_confidence = (
            temp_score * self.temp_weight +
            voc_score * self.voc_weight +
            co2_score * self.co2_weight +
            humidity_score * self.humidity_weight
        )
        
        logger.debug(f"FC Analysis at {current_timestamp}: "
                    f"temp={temp_score:.2f}, voc={voc_score:.2f}, "
                    f"co2={co2_score:.2f}, humidity={humidity_score:.2f}, "
                    f"total={total_confidence:.2f}")
        
        # Check if confidence exceeds threshold
        if total_confidence >= self.confidence_threshold:
            return {
                'timestamp': current_timestamp,
                'confidence_score': total_confidence,
                'detection_method': 'automatic',
                'signal_scores': {
                    'temperature_ror': temp_score,
                    'voc_spike': voc_score,
                    'co2_pattern': co2_score,
                    'humidity_response': humidity_score
                },
                'current_temperature': current_temp
            }
        
        return None
    
    def _analyze_temperature_ror(self, temp_data: List[Tuple], current_timestamp: str) -> float:
        """Analyze temperature rate of change for first crack stall/drop pattern."""
        if len(temp_data) < 4:  # Need at least 4 points for RoR calculation
            return 0.0
        
        try:
            # Calculate rate of rise over last 60 seconds
            current_time = datetime.fromisoformat(current_timestamp.replace('Z', '+00:00'))
            recent_data = []
            
            for timestamp_str, value in temp_data:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                if (current_time - timestamp).total_seconds() <= 60:
                    recent_data.append((timestamp, value))
            
            if len(recent_data) < 3:
                return 0.0
            
            # Sort by timestamp
            recent_data.sort()
            
            # Calculate average RoR over the period
            time_diffs = []
            temp_diffs = []
            
            for i in range(1, len(recent_data)):
                time_diff = (recent_data[i][0] - recent_data[i-1][0]).total_seconds() / 60  # minutes
                temp_diff = recent_data[i][1] - recent_data[i-1][1]  # °C
                if time_diff > 0:
                    time_diffs.append(time_diff)
                    temp_diffs.append(temp_diff / time_diff)  # °C/min
            
            if not temp_diffs:
                return 0.0
            
            avg_ror = sum(temp_diffs) / len(temp_diffs)
            
            # Score based on temperature stall/drop (negative RoR indicates first crack)
            if avg_ror <= self.temp_ror_threshold:
                return 1.0  # Strong indication
            elif avg_ror <= 0:
                return 0.7  # Moderate indication
            elif avg_ror <= 2:
                return 0.3  # Weak indication (slow rise)
            else:
                return 0.0  # No indication
                
        except Exception as e:
            logger.error(f"Error analyzing temperature RoR: {e}")
            return 0.0
    
    def _analyze_voc_spike(self, voc_data: List[Tuple], current_timestamp: str) -> float:
        """Analyze VOC spike pattern indicating first crack."""
        if len(voc_data) < 5:
            return 0.0
        
        try:
            current_time = datetime.fromisoformat(current_timestamp.replace('Z', '+00:00'))
            
            # Get baseline (30-90 seconds ago) and current (last 30 seconds)
            baseline_values = []
            current_values = []
            
            for timestamp_str, value in voc_data:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                seconds_ago = (current_time - timestamp).total_seconds()
                
                if 30 <= seconds_ago <= 90:
                    baseline_values.append(value)
                elif seconds_ago <= 30:
                    current_values.append(value)
            
            if not baseline_values or not current_values:
                return 0.0
            
            baseline_avg = sum(baseline_values) / len(baseline_values)
            current_avg = sum(current_values) / len(current_values)
            
            if baseline_avg <= 0:
                return 0.0
            
            ratio = current_avg / baseline_avg
            
            # Score based on VOC spike magnitude
            if ratio >= self.voc_spike_threshold:
                # Scale score based on spike magnitude
                score = min(1.0, (ratio - 1.0) / 0.5)  # Max score at 50% increase
                return score
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Error analyzing VOC spike: {e}")
            return 0.0
    
    def _analyze_co2_pattern(self, co2_data: List[Tuple], current_timestamp: str) -> float:
        """Analyze CO2 release pattern during first crack."""
        if len(co2_data) < 5:
            return 0.0
        
        try:
            current_time = datetime.fromisoformat(current_timestamp.replace('Z', '+00:00'))
            
            # Similar analysis to VOC but with different thresholds
            baseline_values = []
            current_values = []
            
            for timestamp_str, value in co2_data:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                seconds_ago = (current_time - timestamp).total_seconds()
                
                if 30 <= seconds_ago <= 90:
                    baseline_values.append(value)
                elif seconds_ago <= 30:
                    current_values.append(value)
            
            if not baseline_values or not current_values:
                return 0.0
            
            baseline_avg = sum(baseline_values) / len(baseline_values)
            current_avg = sum(current_values) / len(current_values)
            
            if baseline_avg <= 0:
                return 0.0
            
            ratio = current_avg / baseline_avg
            
            # Score based on CO2 increase
            if ratio >= self.co2_spike_threshold:
                score = min(1.0, (ratio - 1.0) / 0.3)  # Max score at 30% increase
                return score
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Error analyzing CO2 pattern: {e}")
            return 0.0
    
    def _analyze_humidity_response(self, humidity_data: List[Tuple], current_timestamp: str) -> float:
        """Analyze humidity response to first crack water vapor release."""
        if len(humidity_data) < 5:
            return 0.0
        
        try:
            current_time = datetime.fromisoformat(current_timestamp.replace('Z', '+00:00'))
            
            # Look for humidity spike in last 30 seconds vs previous baseline
            baseline_values = []
            current_values = []
            
            for timestamp_str, value in humidity_data:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                seconds_ago = (current_time - timestamp).total_seconds()
                
                if 30 <= seconds_ago <= 90:
                    baseline_values.append(value)
                elif seconds_ago <= 30:
                    current_values.append(value)
            
            if not baseline_values or not current_values:
                return 0.0
            
            baseline_avg = sum(baseline_values) / len(baseline_values)
            current_avg = sum(current_values) / len(current_values)
            
            if baseline_avg <= 0:
                return 0.0
            
            ratio = current_avg / baseline_avg
            
            # Score based on humidity increase
            if ratio >= self.humidity_spike_threshold:
                score = min(1.0, (ratio - 1.0) / 0.2)  # Max score at 20% increase
                return score
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Error analyzing humidity response: {e}")
            return 0.0