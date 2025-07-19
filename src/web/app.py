from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import json
import logging
import os
import sys
from datetime import datetime, timedelta

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.models import DatabaseManager
from sensors.managed_dht22 import ManagedDHT22Sensor
from sensors.managed_sht31 import ManagedSHT31Sensor
from sensors.managed_sgp30 import ManagedSGP30Sensor
from sensors.sensor_manager import sensor_manager
from services.data_collector import DataCollector
from services.first_crack_detector import FirstCrackDetector
from services.first_crack_predictor import FirstCrackPredictor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set data collector to debug
logging.getLogger('services.data_collector').setLevel(logging.DEBUG)
logging.getLogger('sensors.managed_dht22').setLevel(logging.DEBUG)
logging.getLogger('sensors.sensor_manager').setLevel(logging.DEBUG)
logging.getLogger('database.models').setLevel(logging.DEBUG)

app = Flask(__name__, 
           template_folder='../../templates',
           static_folder='../../static')
app.config['SECRET_KEY'] = 'coffee-roaster-secret-key'

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables
db_manager = None
sensors = {}
data_collector = None
first_crack_predictor = None

def load_config():
    """Load configuration from config.json"""
    config_path = os.path.join(os.path.dirname(__file__), '../../config.json')
    with open(config_path, 'r') as f:
        return json.load(f)

def initialize_sensors(config):
    """Initialize all configured sensors"""
    global sensors
    
    for sensor_config in config['sensors']:
        sensor_type = sensor_config['type']
        sensor_name = sensor_config['name']
        
        if sensor_type == 'DHT22':
            sensor = ManagedDHT22Sensor(sensor_name, sensor_config)
            if sensor.initialize():
                sensors[sensor_name] = sensor
                logger.info(f"Initialized sensor: {sensor_name}")
            else:
                logger.error(f"Failed to initialize sensor: {sensor_name}")
        elif sensor_type == 'SHT31':
            sensor = ManagedSHT31Sensor(sensor_name, sensor_config)
            if sensor.initialize():
                sensors[sensor_name] = sensor
                logger.info(f"Initialized sensor: {sensor_name}")
            else:
                logger.error(f"Failed to initialize sensor: {sensor_name}")
        elif sensor_type == 'SGP30':
            sensor = ManagedSGP30Sensor(sensor_name, sensor_config)
            if sensor.initialize():
                sensors[sensor_name] = sensor
                logger.info(f"Initialized sensor: {sensor_name}")
            else:
                logger.error(f"Failed to initialize sensor: {sensor_name}")
        else:
            logger.error(f"Unknown sensor type: {sensor_type}")

@app.route('/')
def index():
    """Main dashboard showing list of roast sessions"""
    roast_sessions = db_manager.get_roast_sessions()
    active_session = db_manager.get_active_roast_session()
    
    # Calculate duration for each session
    for session in roast_sessions:
        if session.get('end_time'):
            try:
                start_time = datetime.fromisoformat(session['start_time'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(session['end_time'].replace('Z', '+00:00'))
                duration_seconds = (end_time - start_time).total_seconds()
                session['duration_minutes'] = int(duration_seconds // 60)
                session['duration_seconds'] = int(duration_seconds % 60)
            except:
                session['duration_minutes'] = 0
                session['duration_seconds'] = 0
        else:
            session['duration_minutes'] = None
            session['duration_seconds'] = None
    
    return render_template('index.html', 
                         roast_sessions=roast_sessions,
                         active_session=active_session)

@app.route('/roast/<roast_id>')
def roast_detail(roast_id):
    """Show detailed view of a specific roast"""
    roast_session = db_manager.get_roast_session(roast_id)
    if not roast_session:
        return "Roast not found", 404
    
    roast_data = db_manager.get_roast_data(roast_id)
    enhanced_data = add_computed_metrics(roast_data)
    
    # Debug: Log first few data points
    if enhanced_data:
        computed_count = len([p for p in enhanced_data if p['metric_type'] == 'computed'])
        logger.info(f"Roast {roast_id} has {len(enhanced_data)} data points (including {computed_count} computed)")
        for i, point in enumerate(enhanced_data[:5]):
            logger.info(f"  Point {i}: {point['timestamp']} - {point['metric_type']} = {point['value']}")
    
    return render_template('roast_detail.html',
                         roast_session=roast_session,
                         roast_data=enhanced_data)

@app.route('/api/roasts', methods=['GET'])
def get_roasts():
    """API endpoint to get all roast sessions"""
    roaster_id = request.args.get('roaster_id')
    roasts = db_manager.get_roast_sessions(roaster_id=roaster_id)
    return jsonify(roasts)

@app.route('/api/roasts', methods=['POST'])
def start_roast():
    """API endpoint to start a new roast session"""
    global data_collector
    
    data = request.get_json() or {}
    roaster_id = data.get('roaster_id', 'BHR2')  # Default to BHR2
    
    # Use timestamp as name
    name = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Check if there's already an active roast
    active_session = db_manager.get_active_roast_session()
    if active_session:
        return jsonify({'error': 'Another roast is already active'}), 400
    
    try:
        roast_id = db_manager.create_roast_session(name, roaster_id)
        
        # Start data collection
        if data_collector:
            logger.info(f"Starting data collection for roast {roast_id}")
            success = data_collector.start_collection(roast_id)
            logger.info(f"Data collection started: {success}")
        else:
            logger.error("Data collector not initialized!")
        
        # Emit event to all connected clients
        socketio.emit('roast_started', {
            'roast_id': roast_id,
            'name': name,
            'roaster_id': roaster_id,
            'start_time': datetime.now().isoformat()
        })
        
        return jsonify({'roast_id': roast_id, 'name': name, 'roaster_id': roaster_id})
        
    except Exception as e:
        logger.error(f"Failed to start roast: {e}")
        return jsonify({'error': 'Failed to start roast'}), 500

@app.route('/api/roasts/<roast_id>/stop', methods=['PUT'])
def stop_roast(roast_id):
    """API endpoint to stop a roast session"""
    global data_collector
    
    try:
        if db_manager.end_roast_session(roast_id):
            # Stop data collection
            if data_collector:
                logger.info(f"Stopping data collection for roast {roast_id}")
                success = data_collector.stop_collection()
                logger.info(f"Data collection stopped: {success}")
            else:
                logger.error("Data collector not initialized!")
            
            # Emit event to all connected clients
            socketio.emit('roast_stopped', {
                'roast_id': roast_id,
                'end_time': datetime.now().isoformat()
            })
            
            return jsonify({'message': 'Roast stopped successfully'})
        else:
            return jsonify({'error': 'Roast not found or already stopped'}), 404
            
    except Exception as e:
        logger.error(f"Failed to stop roast: {e}")
        return jsonify({'error': 'Failed to stop roast'}), 500

@app.route('/api/roasts/<roast_id>/data', methods=['GET'])
def get_roast_data(roast_id):
    """API endpoint to get data for a specific roast"""
    data = db_manager.get_roast_data(roast_id)
    enhanced_data = add_computed_metrics(data)
    return jsonify(enhanced_data)

def calculate_computed_metric(temp, humidity):
    """Calculate absolute humidity: AH = (6.112 * exp((17.67 * T)/(T+243.5)) * RH * 2.1674)/((273.15+T))"""
    import math
    if temp is not None and humidity is not None:
        # T is temperature in Celsius, RH is relative humidity in %
        T = temp
        RH = humidity
        
        # Calculate absolute humidity in g/m³
        result = (6.112 * math.exp((17.67 * T)/(T + 243.5)) * RH * 2.1674) / (273.15 + T)
        logger.debug(f"Absolute humidity: T={temp}°C, RH={humidity}% -> {result:.2f} g/m³")
        return result
    return None

def add_computed_metrics(data):
    """Add computed metrics to data based on temperature and humidity readings"""
    enhanced_data = []
    temp_readings = []
    humidity_readings = []
    
    # Collect temperature and humidity readings separately
    for data_point in data:
        if data_point['metric_type'] == 'temperature':
            temp_readings.append((data_point['timestamp'], data_point['value']))
        elif data_point['metric_type'] == 'humidity':
            humidity_readings.append((data_point['timestamp'], data_point['value']))
        enhanced_data.append(data_point)
    
    # Sort readings by timestamp
    temp_readings.sort()
    humidity_readings.sort()
    
    # Match temperature and humidity readings that are close in time (within 1 second)
    computed_count = 0
    temp_idx = 0
    humidity_idx = 0
    
    while temp_idx < len(temp_readings) and humidity_idx < len(humidity_readings):
        temp_time, temp_value = temp_readings[temp_idx]
        humidity_time, humidity_value = humidity_readings[humidity_idx]
        
        # Parse timestamps for comparison
        temp_dt = datetime.fromisoformat(temp_time.replace('Z', '+00:00'))
        humidity_dt = datetime.fromisoformat(humidity_time.replace('Z', '+00:00'))
        
        time_diff = abs((temp_dt - humidity_dt).total_seconds())
        
        if time_diff <= 1.0:  # Within 1 second
            computed_value = calculate_computed_metric(temp_value, humidity_value)
            if computed_value is not None:
                # Use the later timestamp for the computed value
                computed_timestamp = temp_time if temp_dt > humidity_dt else humidity_time
                enhanced_data.append({
                    'timestamp': computed_timestamp,
                    'metric_type': 'computed',
                    'value': computed_value
                })
                computed_count += 1
            temp_idx += 1
            humidity_idx += 1
        elif temp_dt < humidity_dt:
            temp_idx += 1
        else:
            humidity_idx += 1
    
    logger.debug(f"Generated {computed_count} computed metrics from {len(temp_readings)} temp and {len(humidity_readings)} humidity readings")
    
    # Sort by timestamp to maintain chronological order
    enhanced_data.sort(key=lambda x: x['timestamp'])
    return enhanced_data

@app.route('/api/roasts/<roast_id>/live-data', methods=['GET'])
def get_live_data(roast_id):
    """API endpoint to get live data updates since a timestamp"""
    since_timestamp = request.args.get('since', '')
    
    # Get new data since the timestamp
    if since_timestamp:
        new_data = db_manager.get_data_since(roast_id, since_timestamp)
    else:
        # If no timestamp provided, get the latest data point
        latest_data = db_manager.get_latest_data_point(roast_id)
        new_data = [latest_data] if latest_data else []
    
    # Add computed metrics to the data
    enhanced_data = add_computed_metrics(new_data)
    
    # Check for first crack detection if this is an active roast
    first_crack_detected = None
    active_session = db_manager.get_active_roast_session()
    is_active = active_session and active_session['id'] == roast_id
    
    if is_active and first_crack_predictor and enhanced_data:
        # Get all roast data for live prediction with lookahead
        all_roast_data = db_manager.get_roast_data(roast_id)
        if all_roast_data:
            all_enhanced_data = add_computed_metrics(all_roast_data)
            
            # Use predictor for live detection (allows lookahead and updates)
            fc_result = first_crack_predictor.predict_first_crack(all_enhanced_data)
            
            if fc_result:
                # Check if this is a new/updated prediction
                existing_fc = db_manager.get_first_crack_event(roast_id)
                
                # Store as historical prediction (same as post-roast analysis)
                # This ensures live predictions exactly match historical ones
                existing_prediction = db_manager.get_first_crack_prediction(roast_id)
                
                if not existing_prediction or existing_prediction['confidence_score'] < fc_result['confidence_score']:
                    success = db_manager.add_first_crack_prediction(
                        roast_id=roast_id,
                        timestamp=fc_result['timestamp'],
                        confidence_score=fc_result['confidence_score'],
                        signal_scores=fc_result['signal_scores'],
                        predicted_temperature=fc_result['current_temperature']
                    )
                    
                    if success:
                        first_crack_detected = fc_result
                        action = "UPDATED" if existing_prediction else "PREDICTED"
                        logger.info(f"🔮 FIRST CRACK {action} for roast {roast_id} at {fc_result['timestamp']} "
                                  f"(confidence: {fc_result['confidence_score']:.2f})")
                        
                        # Emit real-time notification for live prediction updates
                        socketio.emit('first_crack_predicted', {
                            'roast_id': roast_id,
                            'timestamp': fc_result['timestamp'],
                            'confidence_score': fc_result['confidence_score'],
                            'current_temperature': fc_result['current_temperature'],
                            'detection_method': 'predicted'
                        })
    
    # Get temperature alert threshold from config
    config = load_config()
    max_temp_alert = config.get('alerts', {}).get('MAX_TEMPERATURE_ALERT', 125)
    
    # Check if current temperature exceeds alert threshold
    temp_alert = False
    latest_temp = None
    for data_point in reversed(enhanced_data):
        if data_point['metric_type'] == 'temperature':
            latest_temp = data_point['value']
            temp_alert = latest_temp >= max_temp_alert
            break
    
    # If no new data, check the latest temperature from database
    if latest_temp is None and not enhanced_data:
        latest_data = db_manager.get_latest_data_point(roast_id)
        if latest_data and latest_data['metric_type'] == 'temperature':
            latest_temp = latest_data['value']
            temp_alert = latest_temp >= max_temp_alert
    
    # Get first crack info (both manual and predicted)
    first_crack_summary = db_manager.get_first_crack_summary(roast_id)
    
    # Generate FC prediction if active roast and no prediction exists yet
    if is_active and not first_crack_summary['predicted'] and first_crack_predictor:
        # Get all roast data for prediction analysis
        all_roast_data = db_manager.get_roast_data(roast_id)
        if all_roast_data:
            enhanced_all_data = add_computed_metrics(all_roast_data)
            prediction_result = first_crack_predictor.predict_first_crack(enhanced_all_data)
            
            if prediction_result:
                # Store prediction in database
                success = db_manager.add_first_crack_prediction(
                    roast_id=roast_id,
                    timestamp=prediction_result['timestamp'],
                    confidence_score=prediction_result['confidence_score'],
                    signal_scores=prediction_result['signal_scores'],
                    predicted_temperature=prediction_result['current_temperature']
                )
                
                if success:
                    # Update the summary to include the new prediction
                    first_crack_summary['predicted'] = db_manager.get_first_crack_prediction(roast_id)
                    logger.info(f"🔮 FC prediction generated for active roast {roast_id}: {prediction_result['timestamp']} (confidence: {prediction_result['confidence_score']:.2f})")
    
    return jsonify({
        'data': enhanced_data,
        'is_active': is_active,
        'temperature_alert': temp_alert,
        'latest_temperature': latest_temp,
        'max_temp_threshold': max_temp_alert,
        'first_crack_detected': first_crack_detected,
        'first_crack_event': first_crack_summary['manual'],
        'first_crack_prediction': first_crack_summary['predicted'],
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/roasts/<roast_id>/first-crack', methods=['GET'])
def get_first_crack(roast_id):
    """API endpoint to get first crack event for a roast"""
    first_crack_event = db_manager.get_first_crack_event(roast_id)
    if first_crack_event:
        return jsonify(first_crack_event)
    else:
        return jsonify({'error': 'No first crack event found'}), 404

@app.route('/api/roasts/<roast_id>/first-crack', methods=['POST'])
def mark_first_crack_manual(roast_id):
    """API endpoint to manually mark first crack"""
    try:
        # First, verify the roast exists
        roast_session = db_manager.get_roast_session(roast_id)
        if not roast_session:
            logger.error(f"Attempted to mark first crack for non-existent roast: {roast_id}")
            return jsonify({'error': f'Roast session {roast_id} not found'}), 404
        
        data = request.get_json() or {}
        timestamp = data.get('timestamp', datetime.now().isoformat())
        notes = data.get('notes', 'Manually marked')
        
        logger.info(f"Marking first crack for roast {roast_id} ({roast_session['name']}) at {timestamp}")
        
        # Get current temperature if available
        latest_data = db_manager.get_latest_data_point(roast_id)
        current_temp = None
        if latest_data and latest_data['metric_type'] == 'temperature':
            current_temp = latest_data['value']
        
        logger.debug(f"Current temperature for FC: {current_temp}")
        
        success = db_manager.add_first_crack_event(
            roast_id=roast_id,
            timestamp=timestamp,
            detection_method='manual',
            confidence_score=1.0,
            current_temperature=current_temp,
            notes=notes
        )
        
        logger.info(f"First crack event creation success: {success}")
        
        if success:
            # Emit real-time notification
            socketio.emit('first_crack_detected', {
                'roast_id': roast_id,
                'timestamp': timestamp,
                'confidence_score': 1.0,
                'detection_method': 'manual',
                'current_temperature': current_temp
            })
            
            logger.info(f"First crack marked successfully for roast {roast_id}")
            return jsonify({'message': 'First crack marked successfully', 'timestamp': timestamp})
        else:
            logger.error(f"Database returned false when adding first crack event for roast {roast_id}")
            return jsonify({'error': 'Failed to mark first crack - database operation failed'}), 400
            
    except Exception as e:
        logger.error(f"Exception when marking first crack manually for roast {roast_id}: {e}", exc_info=True)
        return jsonify({'error': f'Failed to mark first crack: {str(e)}'}), 500

@app.route('/api/roasts/<roast_id>/first-crack', methods=['DELETE'])
def delete_first_crack(roast_id):
    """API endpoint to delete first crack event"""
    try:
        success = db_manager.delete_first_crack_event(roast_id)
        if success:
            return jsonify({'message': 'First crack event deleted successfully'})
        else:
            return jsonify({'error': 'No first crack event found to delete'}), 404
            
    except Exception as e:
        logger.error(f"Failed to delete first crack: {e}")
        return jsonify({'error': 'Failed to delete first crack'}), 500

@app.route('/api/roasts/<roast_id>/first-crack-prediction', methods=['GET'])
def get_first_crack_prediction(roast_id):
    """API endpoint to get first crack prediction for a roast"""
    prediction = db_manager.get_first_crack_prediction(roast_id)
    if prediction:
        return jsonify(prediction)
    else:
        return jsonify({'error': 'No first crack prediction found'}), 404

@app.route('/api/roasts/<roast_id>/first-crack-prediction', methods=['POST'])
def generate_first_crack_prediction(roast_id):
    """API endpoint to generate first crack prediction for a roast"""
    try:
        # Verify the roast exists
        roast_session = db_manager.get_roast_session(roast_id)
        if not roast_session:
            return jsonify({'error': f'Roast session {roast_id} not found'}), 404
        
        # Get all roast data for analysis
        roast_data = db_manager.get_roast_data(roast_id)
        if not roast_data:
            return jsonify({'error': 'No roast data available for prediction'}), 400
        
        # Add computed metrics to the data for analysis
        enhanced_data = add_computed_metrics(roast_data)
        
        logger.info(f"Generating FC prediction for roast {roast_id} with {len(enhanced_data)} data points")
        
        # Generate prediction
        if first_crack_predictor:
            prediction_result = first_crack_predictor.predict_first_crack(enhanced_data)
            
            if prediction_result:
                # Store prediction in database
                success = db_manager.add_first_crack_prediction(
                    roast_id=roast_id,
                    timestamp=prediction_result['timestamp'],
                    confidence_score=prediction_result['confidence_score'],
                    signal_scores=prediction_result['signal_scores'],
                    predicted_temperature=prediction_result['current_temperature']
                )
                
                if success:
                    logger.info(f"FC prediction generated for roast {roast_id}: {prediction_result['timestamp']} (confidence: {prediction_result['confidence_score']:.2f})")
                    return jsonify({
                        'message': 'First crack prediction generated successfully',
                        'prediction': prediction_result
                    })
                else:
                    return jsonify({'error': 'Failed to save prediction to database'}), 500
            else:
                return jsonify({'error': 'No first crack could be predicted from the data'}), 404
        else:
            return jsonify({'error': 'First crack predictor not initialized'}), 500
            
    except Exception as e:
        logger.error(f"Failed to generate FC prediction: {e}", exc_info=True)
        return jsonify({'error': f'Failed to generate prediction: {str(e)}'}), 500

@app.route('/api/roasts/<roast_id>/first-crack-prediction', methods=['DELETE'])
def delete_first_crack_prediction(roast_id):
    """API endpoint to delete first crack prediction"""
    try:
        success = db_manager.delete_first_crack_prediction(roast_id)
        if success:
            return jsonify({'message': 'First crack prediction deleted successfully'})
        else:
            return jsonify({'error': 'No first crack prediction found to delete'}), 404
            
    except Exception as e:
        logger.error(f"Failed to delete FC prediction: {e}")
        return jsonify({'error': 'Failed to delete first crack prediction'}), 500

@app.route('/api/roasts/<roast_id>/first-crack-summary', methods=['GET'])
def get_first_crack_summary(roast_id):
    """API endpoint to get both manual FC event and prediction"""
    try:
        summary = db_manager.get_first_crack_summary(roast_id)
        return jsonify(summary)
    except Exception as e:
        logger.error(f"Failed to get FC summary: {e}")
        return jsonify({'error': 'Failed to get first crack summary'}), 500

@app.route('/api/config', methods=['GET'])
def get_config():
    """API endpoint to get UI configuration"""
    config = load_config()
    return jsonify({
        'ui': config.get('ui', {}),
        'alerts': config.get('alerts', {}),
        'first_crack': config.get('first_crack', {}),
        'roaster_ids': config.get('roaster_ids', ['BHR2'])
    })

@app.route('/api/roasts/<roast_id>/roaster', methods=['PUT'])
def update_roast_roaster(roast_id):
    """API endpoint to update roaster_id for a completed roast session"""
    try:
        data = request.get_json()
        if not data or 'roaster_id' not in data:
            return jsonify({'error': 'roaster_id is required'}), 400
        
        roaster_id = data['roaster_id']
        success = db_manager.update_roast_roaster_id(roast_id, roaster_id)
        
        if success:
            return jsonify({'message': 'Roaster ID updated successfully'})
        else:
            return jsonify({'error': 'Failed to update roaster ID (roast not found or is active)'}), 400
            
    except Exception as e:
        logger.error(f"Failed to update roaster ID: {e}")
        return jsonify({'error': 'Failed to update roaster ID'}), 500

@app.route('/api/roasts/<roast_id>', methods=['DELETE'])
def delete_roast(roast_id):
    """API endpoint to delete a roast session"""
    try:
        # Check if roast is currently active
        active_session = db_manager.get_active_roast_session()
        if active_session and active_session['id'] == roast_id:
            return jsonify({'error': 'Cannot delete active roast session'}), 400
        
        success = db_manager.delete_roast_session(roast_id)
        if success:
            return jsonify({'message': 'Roast deleted successfully'})
        else:
            return jsonify({'error': 'Roast not found'}), 404
            
    except Exception as e:
        logger.error(f"Failed to delete roast: {e}")
        return jsonify({'error': 'Failed to delete roast'}), 500

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info('🔗 SocketIO Client connected successfully')
    
    # Send current active roast if any
    active_session = db_manager.get_active_roast_session()
    if active_session:
        emit('roast_active', active_session)

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info('❌ SocketIO Client disconnected')

def run_app():
    """Initialize and run the Flask application"""
    global db_manager, data_collector, first_crack_predictor
    
    try:
        # Load configuration
        config = load_config()
        
        # Initialize database
        db_path = config['database']['path']
        db_manager = DatabaseManager(db_path)
        
        # Initialize sensors
        initialize_sensors(config)
        
        # Start sensor manager
        sensor_manager.start_reading()
        
        # Initialize data collector
        sample_rate = config['logging']['sample_rate']
        data_collector = DataCollector(sensors, db_manager, socketio, sample_rate)
        
        # Initialize first crack predictor (used for both live and historical analysis)
        fc_config = config.get('first_crack', {})
        first_crack_predictor = FirstCrackPredictor(fc_config)
        logger.info(f"FirstCrackPredictor initialized for unified live/historical analysis with config: {fc_config}")
        
        # Check for active roasts and close them (app restart should end active roasts)
        active_session = db_manager.get_active_roast_session()
        if active_session:
            roast_id = active_session['id']
            logger.info(f"🔍 Found active roast on startup: {active_session['name']} (ID: {roast_id})")
            logger.info(f"🏁 App restart detected - automatically completing active roast")
            
            # Always mark active roasts as completed on app restart
            db_manager.end_roast_session(roast_id)
            logger.info(f"✅ Completed roast session: {roast_id}")
        else:
            logger.info("💤 No active roast sessions found on startup")
        
        # Start the application
        host = config['web']['host']
        port = config['web']['port']
        
        logger.info(f"Starting web application on {host}:{port}")
        logger.info(f"Initialized {len(sensors)} sensors: {list(sensors.keys())}")
        logger.info(f"Data collection rate: {sample_rate} second(s)")
        logger.info(f"Data collector initialized: {data_collector is not None}")
        
        try:
            socketio.run(app, host=host, port=port, debug=True)
        finally:
            # Clean up sensor manager
            sensor_manager.stop_reading()
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise

if __name__ == '__main__':
    run_app()