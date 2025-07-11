from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import json
import logging
import os
import sys
from datetime import datetime

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.models import DatabaseManager
from sensors.managed_dht22 import ManagedDHT22Sensor
from sensors.managed_sht31 import ManagedSHT31Sensor
from sensors.sensor_manager import sensor_manager
from services.data_collector import DataCollector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set data collector to debug
logging.getLogger('services.data_collector').setLevel(logging.DEBUG)
logging.getLogger('sensors.managed_dht22').setLevel(logging.DEBUG)
logging.getLogger('sensors.sensor_manager').setLevel(logging.DEBUG)

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
    
    # Debug: Log first few data points
    if roast_data:
        logger.info(f"Roast {roast_id} has {len(roast_data)} data points")
        for i, point in enumerate(roast_data[:3]):
            logger.info(f"  Point {i}: {point['timestamp']} - {point['metric_type']} = {point['value']}")
    
    return render_template('roast_detail.html',
                         roast_session=roast_session,
                         roast_data=roast_data)

@app.route('/api/roasts', methods=['GET'])
def get_roasts():
    """API endpoint to get all roast sessions"""
    roasts = db_manager.get_roast_sessions()
    return jsonify(roasts)

@app.route('/api/roasts', methods=['POST'])
def start_roast():
    """API endpoint to start a new roast session"""
    global data_collector
    
    # Use timestamp as name
    name = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Check if there's already an active roast
    active_session = db_manager.get_active_roast_session()
    if active_session:
        return jsonify({'error': 'Another roast is already active'}), 400
    
    try:
        roast_id = db_manager.create_roast_session(name)
        
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
            'start_time': datetime.now().isoformat()
        })
        
        return jsonify({'roast_id': roast_id, 'name': name})
        
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
    return jsonify(data)

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
    
    # Get current active session status
    active_session = db_manager.get_active_roast_session()
    is_active = active_session and active_session['id'] == roast_id
    
    return jsonify({
        'data': new_data,
        'is_active': is_active,
        'timestamp': datetime.now().isoformat()
    })

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
    global db_manager, data_collector
    
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