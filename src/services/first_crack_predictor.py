import logging
import math
from datetime import datetime
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class FirstCrackPredictor:
    """
    First crack prediction system that analyzes existing roast data to predict when FC occurred.
    Separate from manual marking and real-time detection.
    """
    
    def __init__(self, config: Dict = None):
        """Initialize the first crack predictor with configuration parameters."""
        self.config = config or {}
        
        # Use the same thresholds as real-time detection for consistency
        self.temp_ror_threshold = self.config.get('TEMP_ROR_THRESHOLD', -1.0)  # °C/min drop
        self.voc_spike_threshold = self.config.get('VOC_SPIKE_THRESHOLD', 1.2)  # 20% increase
        self.co2_spike_threshold = self.config.get('CO2_SPIKE_THRESHOLD', 1.15)  # 15% increase
        self.humidity_spike_threshold = self.config.get('HUMIDITY_SPIKE_THRESHOLD', 1.1)  # 10% increase
        
        # Use the same weights as real-time detection
        self.temp_weight = self.config.get('TEMP_WEIGHT', 0.25)
        self.voc_weight = self.config.get('VOC_WEIGHT', 0.45)
        self.co2_weight = self.config.get('CO2_WEIGHT', 0.20)
        self.humidity_weight = self.config.get('HUMIDITY_WEIGHT', 0.10)
        
        # Analysis parameters
        self.min_temp_for_fc = self.config.get('MIN_TEMP_FOR_FC', 30)  # °C - same as real-time
        self.confidence_threshold = self.config.get('CONFIDENCE_THRESHOLD', 0.50)  # Same as real-time
        self.analysis_window = self.config.get('ANALYSIS_WINDOW_SIZE', 120)  # seconds - same as real-time
        
        logger.info(f"FirstCrackPredictor initialized with confidence threshold: {self.confidence_threshold}")
    
    def predict_first_crack(self, roast_data: List[Dict]) -> Optional[Dict]:
        """
        Analyze complete roast data to predict when first crack occurred.
        
        Args:
            roast_data: List of data points with timestamp, metric_type, value
            
        Returns:
            Dict with prediction results or None if no FC predicted
        """
        if not roast_data:
            return None
        
        # Group data by metric type and sort by timestamp
        temp_data = sorted([(dp['timestamp'], dp['value']) for dp in roast_data if dp['metric_type'] == 'temperature'])
        voc_data = sorted([(dp['timestamp'], dp['value']) for dp in roast_data if dp['metric_type'] == 'voc'])
        co2_data = sorted([(dp['timestamp'], dp['value']) for dp in roast_data if dp['metric_type'] == 'co2'])
        humidity_data = sorted([(dp['timestamp'], dp['value']) for dp in roast_data if dp['metric_type'] == 'humidity'])
        
        if not temp_data:
            logger.warning("No temperature data available for FC prediction")
            return None
        
        # Find the temperature range where FC is likely (160°C - 220°C)
        fc_candidates = []
        max_confidence = 0.0
        best_candidate_info = None
        
        for temp_time, temp_value in temp_data:
            if self.min_temp_for_fc <= temp_value <= 220:
                timestamp = temp_time
                confidence = self._analyze_fc_probability(
                    timestamp, temp_data, voc_data, co2_data, humidity_data
                )
                
                # Track the best candidate for debugging
                if confidence > max_confidence:
                    max_confidence = confidence
                    best_candidate_info = {
                        'timestamp': timestamp,
                        'confidence': confidence,
                        'temperature': temp_value
                    }
                
                if confidence >= self.confidence_threshold:
                    fc_candidates.append({
                        'timestamp': timestamp,
                        'confidence_score': confidence,
                        'temperature': temp_value
                    })
        
        logger.info(f"FC prediction analysis: {len(temp_data)} temp points, max confidence: {max_confidence:.3f} (threshold: {self.confidence_threshold})")
        if best_candidate_info:
            logger.info(f"Best candidate: {best_candidate_info['timestamp']} at {best_candidate_info['temperature']:.1f}°C with {best_candidate_info['confidence']:.3f} confidence")
        
        if not fc_candidates:
            logger.info(f"No FC candidates found above threshold {self.confidence_threshold}. Best confidence was {max_confidence:.3f}")
            return None
        
        # Return the highest confidence prediction
        best_prediction = max(fc_candidates, key=lambda x: x['confidence_score'])
        
        # Get detailed signal analysis for the best prediction
        signal_scores = self._get_detailed_analysis(
            best_prediction['timestamp'], temp_data, voc_data, co2_data, humidity_data
        )
        
        result = {
            'timestamp': best_prediction['timestamp'],
            'confidence_score': best_prediction['confidence_score'],
            'detection_method': 'predicted',
            'current_temperature': best_prediction['temperature'],
            'signal_scores': signal_scores
        }
        
        logger.info(f"FC predicted at {result['timestamp']} with {result['confidence_score']:.2f} confidence")
        return result
    
    def _analyze_fc_probability(self, timestamp: str, temp_data: List[Tuple], 
                               voc_data: List[Tuple], co2_data: List[Tuple], 
                               humidity_data: List[Tuple]) -> float:
        """Analyze probability of FC at given timestamp."""
        try:
            current_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            # Calculate scores for each signal
            temp_score = self._analyze_temp_pattern(current_time, temp_data)
            voc_score = self._analyze_voc_pattern(current_time, voc_data)
            co2_score = self._analyze_co2_pattern(current_time, co2_data)
            humidity_score = self._analyze_humidity_pattern(current_time, humidity_data)
            
            # Calculate weighted confidence
            total_confidence = (
                temp_score * self.temp_weight +
                voc_score * self.voc_weight +
                co2_score * self.co2_weight +
                humidity_score * self.humidity_weight
            )
            
            return min(1.0, max(0.0, total_confidence))
            
        except Exception as e:
            logger.error(f"Error analyzing FC probability: {e}")
            return 0.0
    
    def _analyze_temp_pattern(self, current_time: datetime, temp_data: List[Tuple]) -> float:
        """Analyze temperature rate of change pattern."""
        try:
            # Get temperature readings around the current time
            before_readings = []
            after_readings = []
            current_readings = []
            
            for timestamp_str, value in temp_data:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                time_diff = (timestamp - current_time).total_seconds()
                
                if -120 <= time_diff <= -30:  # 30-120 seconds before
                    before_readings.append((timestamp, value))
                elif -30 <= time_diff <= 30:   # Around current time
                    current_readings.append((timestamp, value))
                elif 30 <= time_diff <= 120:   # 30-120 seconds after
                    after_readings.append((timestamp, value))
            
            # Need some readings before and after for comparison
            if len(before_readings) < 2:
                return 0.0
            
            # Calculate rate of rise before current time
            before_ror = self._calculate_average_ror(before_readings)
            
            # Use more flexible scoring - look for any temperature pattern change
            score = 0.0
            
            # If we have after readings, compare before vs after RoR
            if len(after_readings) >= 2:
                after_ror = self._calculate_average_ror(after_readings)
                ror_change = before_ror - after_ror
                
                # Score based on RoR change magnitude (more lenient)
                if ror_change >= 2.0:
                    score = 1.0
                elif ror_change >= 1.0:
                    score = 0.8
                elif ror_change >= 0.3:
                    score = 0.6
                elif ror_change >= 0.0:  # Any slowdown
                    score = 0.4
                else:
                    score = 0.2
            else:
                # If no after readings, just check if RoR is reasonable for FC
                if 0 <= before_ror <= 8:  # Reasonable heating rate before FC
                    score = 0.5
                elif before_ror > 8:  # Very fast heating
                    score = 0.3
                else:  # Negative RoR (cooling)
                    score = 0.1
            
            logger.debug(f"Temp pattern: before_ror={before_ror:.2f}, score={score:.2f}")
            return score
                
        except Exception as e:
            logger.error(f"Error analyzing temp pattern: {e}")
            return 0.0
    
    def _analyze_voc_pattern(self, current_time: datetime, voc_data: List[Tuple]) -> float:
        """Analyze VOC spike pattern."""
        return self._analyze_spike_pattern(current_time, voc_data, self.voc_spike_threshold)
    
    def _analyze_co2_pattern(self, current_time: datetime, co2_data: List[Tuple]) -> float:
        """Analyze CO2 spike pattern."""
        return self._analyze_spike_pattern(current_time, co2_data, self.co2_spike_threshold)
    
    def _analyze_humidity_pattern(self, current_time: datetime, humidity_data: List[Tuple]) -> float:
        """Analyze humidity spike pattern."""
        return self._analyze_spike_pattern(current_time, humidity_data, self.humidity_spike_threshold)
    
    def _analyze_spike_pattern(self, current_time: datetime, data: List[Tuple], threshold: float) -> float:
        """Generic spike analysis for VOC, CO2, and humidity."""
        try:
            if not data:
                return 0.0
            
            # Get baseline (before) and spike (around) readings
            baseline_readings = []
            spike_readings = []
            
            for timestamp_str, value in data:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                time_diff = (timestamp - current_time).total_seconds()
                
                if -120 <= time_diff <= -30:  # Baseline period
                    baseline_readings.append(value)
                elif -30 <= time_diff <= 60:   # Spike detection period
                    spike_readings.append(value)
            
            if not baseline_readings or not spike_readings:
                return 0.0
            
            baseline_avg = sum(baseline_readings) / len(baseline_readings)
            spike_avg = sum(spike_readings) / len(spike_readings)
            
            if baseline_avg <= 0:
                return 0.0
            
            ratio = spike_avg / baseline_avg
            
            # Score based on spike magnitude
            if ratio >= threshold * 1.5:  # Very strong spike
                return 1.0
            elif ratio >= threshold:
                return 0.8
            elif ratio >= threshold * 0.8:
                return 0.4
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Error analyzing spike pattern: {e}")
            return 0.0
    
    def _calculate_average_ror(self, readings: List[Tuple]) -> float:
        """Calculate average rate of rise from temperature readings."""
        if len(readings) < 2:
            return 0.0
        
        ror_values = []
        for i in range(1, len(readings)):
            time_diff = (readings[i][0] - readings[i-1][0]).total_seconds() / 60  # minutes
            temp_diff = readings[i][1] - readings[i-1][1]  # °C
            
            if time_diff > 0:
                ror_values.append(temp_diff / time_diff)
        
        return sum(ror_values) / len(ror_values) if ror_values else 0.0
    
    def _get_detailed_analysis(self, timestamp: str, temp_data: List[Tuple], 
                              voc_data: List[Tuple], co2_data: List[Tuple], 
                              humidity_data: List[Tuple]) -> Dict:
        """Get detailed signal analysis for the predicted FC timestamp."""
        current_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        return {
            'temperature_ror': self._analyze_temp_pattern(current_time, temp_data),
            'voc_spike': self._analyze_voc_pattern(current_time, voc_data),
            'co2_pattern': self._analyze_co2_pattern(current_time, co2_data),
            'humidity_response': self._analyze_humidity_pattern(current_time, humidity_data)
        }