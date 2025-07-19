import sqlite3
import uuid
from datetime import datetime
from typing import List, Dict, Optional
import logging
import os

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database operations for roast data"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.ensure_database_dir()
        self.init_database()
    
    def ensure_database_dir(self):
        """Create database directory if it doesn't exist"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
    
    def init_database(self):
        """Initialize database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create roast_sessions table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS roast_sessions (
                        id TEXT PRIMARY KEY,
                        start_time TEXT NOT NULL,
                        end_time TEXT,
                        name TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'active',
                        roaster_id TEXT NOT NULL DEFAULT 'BHR2',
                        first_crack_time TEXT,
                        first_crack_detected_by TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Add roaster_id column to existing tables (migration)
                cursor.execute("PRAGMA table_info(roast_sessions)")
                columns = [column[1] for column in cursor.fetchall()]
                if 'roaster_id' not in columns:
                    cursor.execute('ALTER TABLE roast_sessions ADD COLUMN roaster_id TEXT NOT NULL DEFAULT "BHR2"')
                    logger.info("Added roaster_id column to roast_sessions table")
                
                # Create data_points table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS data_points (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        roast_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        sensor_name TEXT NOT NULL,
                        metric_type TEXT NOT NULL,
                        value REAL NOT NULL,
                        unit TEXT NOT NULL,
                        FOREIGN KEY (roast_id) REFERENCES roast_sessions (id)
                    )
                ''')
                
                # Create first_crack_events table (manual markings)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS first_crack_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        roast_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        detection_method TEXT NOT NULL,
                        confidence_score REAL,
                        signal_scores TEXT,
                        current_temperature REAL,
                        notes TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (roast_id) REFERENCES roast_sessions (id)
                    )
                ''')
                
                # Create first_crack_predictions table (automated predictions)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS first_crack_predictions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        roast_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        confidence_score REAL NOT NULL,
                        signal_scores TEXT,
                        predicted_temperature REAL,
                        prediction_algorithm TEXT DEFAULT 'multi_signal_v1',
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (roast_id) REFERENCES roast_sessions (id)
                    )
                ''')
                
                # Create indexes for performance
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_data_points_roast_id 
                    ON data_points (roast_id)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_data_points_timestamp 
                    ON data_points (timestamp)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_first_crack_events_roast_id 
                    ON first_crack_events (roast_id)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_first_crack_predictions_roast_id 
                    ON first_crack_predictions (roast_id)
                ''')
                
                conn.commit()
                logger.info(f"Database initialized at {self.db_path}")
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def create_roast_session(self, name: str, roaster_id: str = "BHR2") -> str:
        """Create a new roast session and return its ID"""
        try:
            roast_id = str(uuid.uuid4())
            start_time = datetime.now().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO roast_sessions (id, start_time, name, status, roaster_id)
                    VALUES (?, ?, ?, 'active', ?)
                ''', (roast_id, start_time, name, roaster_id))
                conn.commit()
                
            logger.info(f"Created roast session: {roast_id} - {name} (Roaster: {roaster_id})")
            return roast_id
            
        except Exception as e:
            logger.error(f"Failed to create roast session: {e}")
            raise
    
    def end_roast_session(self, roast_id: str) -> bool:
        """End a roast session"""
        try:
            end_time = datetime.now().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE roast_sessions 
                    SET end_time = ?, status = 'completed'
                    WHERE id = ? AND status = 'active'
                ''', (end_time, roast_id))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"Ended roast session: {roast_id}")
                    return True
                else:
                    logger.warning(f"No active roast session found: {roast_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to end roast session: {e}")
            return False
    
    def add_data_point(self, roast_id: str, sensor_name: str, metric_type: str, 
                      value: float, unit: str) -> bool:
        """Add a data point to a roast session"""
        try:
            timestamp = datetime.now().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO data_points (roast_id, timestamp, sensor_name, metric_type, value, unit)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (roast_id, timestamp, sensor_name, metric_type, value, unit))
                conn.commit()
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to add data point: {e}")
            return False
    
    def get_roast_sessions(self, limit: int = 50, roaster_id: str = None) -> List[Dict]:
        """Get list of roast sessions"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if roaster_id:
                    cursor.execute('''
                        SELECT id, start_time, end_time, name, status, roaster_id,
                               (SELECT COUNT(*) FROM data_points WHERE roast_id = roast_sessions.id) as data_count,
                               (SELECT MAX(value) FROM data_points WHERE roast_id = roast_sessions.id AND metric_type = 'temperature') as peak_temp
                        FROM roast_sessions
                        WHERE roaster_id = ?
                        ORDER BY start_time DESC
                        LIMIT ?
                    ''', (roaster_id, limit))
                else:
                    cursor.execute('''
                        SELECT id, start_time, end_time, name, status, roaster_id,
                               (SELECT COUNT(*) FROM data_points WHERE roast_id = roast_sessions.id) as data_count,
                               (SELECT MAX(value) FROM data_points WHERE roast_id = roast_sessions.id AND metric_type = 'temperature') as peak_temp
                        FROM roast_sessions
                        ORDER BY start_time DESC
                        LIMIT ?
                    ''', (limit,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get roast sessions: {e}")
            return []
    
    def get_roast_session(self, roast_id: str) -> Optional[Dict]:
        """Get a specific roast session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM roast_sessions WHERE id = ?
                ''', (roast_id,))
                
                row = cursor.fetchone()
                return dict(row) if row else None
                
        except Exception as e:
            logger.error(f"Failed to get roast session: {e}")
            return None
    
    def get_roast_data(self, roast_id: str) -> List[Dict]:
        """Get all data points for a roast session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT timestamp, sensor_name, metric_type, value, unit
                    FROM data_points
                    WHERE roast_id = ?
                    ORDER BY timestamp
                ''', (roast_id,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get roast data: {e}")
            return []
    
    def get_active_roast_session(self) -> Optional[Dict]:
        """Get the currently active roast session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM roast_sessions 
                    WHERE status = 'active'
                    ORDER BY start_time DESC
                    LIMIT 1
                ''', )
                
                row = cursor.fetchone()
                return dict(row) if row else None
                
        except Exception as e:
            logger.error(f"Failed to get active roast session: {e}")
            return None
    
    def get_data_since(self, roast_id: str, since_timestamp: str) -> List[Dict]:
        """Get data points for a roast session since a specific timestamp"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT timestamp, sensor_name, metric_type, value, unit
                    FROM data_points
                    WHERE roast_id = ? AND timestamp > ?
                    ORDER BY timestamp
                ''', (roast_id, since_timestamp))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get data since {since_timestamp}: {e}")
            return []
    
    def get_latest_data_point(self, roast_id: str) -> Optional[Dict]:
        """Get the most recent data point for a roast session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT timestamp, sensor_name, metric_type, value, unit
                    FROM data_points
                    WHERE roast_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                ''', (roast_id,))
                
                row = cursor.fetchone()
                return dict(row) if row else None
                
        except Exception as e:
            logger.error(f"Failed to get latest data point: {e}")
            return None
    
    def get_roast_activity_status(self, roast_id: str) -> Dict:
        """Check if a roast has recent data activity"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get latest data point timestamp
                cursor.execute('''
                    SELECT timestamp
                    FROM data_points
                    WHERE roast_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                ''', (roast_id,))
                
                row = cursor.fetchone()
                if not row or not row['timestamp']:
                    return {
                        'has_data': False,
                        'last_data_time': None,
                        'minutes_since_last_data': None,
                        'is_recently_active': False
                    }
                
                from datetime import datetime
                last_data_time = datetime.fromisoformat(row['timestamp'])
                now = datetime.now()
                minutes_since = (now - last_data_time).total_seconds() / 60
                
                # Consider "recently active" if data within last 5 minutes
                is_recently_active = minutes_since <= 5
                
                return {
                    'has_data': True,
                    'last_data_time': last_data_time.isoformat(),
                    'minutes_since_last_data': minutes_since,
                    'is_recently_active': is_recently_active
                }
                
        except Exception as e:
            logger.error(f"Failed to get roast activity status: {e}")
            return {
                'has_data': False,
                'last_data_time': None,
                'minutes_since_last_data': None,
                'is_recently_active': False
            }
    
    def update_roast_roaster_id(self, roast_id: str, roaster_id: str) -> bool:
        """Update the roaster_id for an existing roast session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if roast exists and is not active
                cursor.execute('''
                    SELECT status FROM roast_sessions WHERE id = ?
                ''', (roast_id,))
                
                result = cursor.fetchone()
                if not result:
                    logger.warning(f"No roast session found: {roast_id}")
                    return False
                
                if result[0] == 'active':
                    logger.warning(f"Cannot update roaster_id for active roast: {roast_id}")
                    return False
                
                # Update roaster_id
                cursor.execute('''
                    UPDATE roast_sessions 
                    SET roaster_id = ?
                    WHERE id = ?
                ''', (roaster_id, roast_id))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"Updated roaster_id for roast {roast_id} to {roaster_id}")
                    return True
                else:
                    logger.warning(f"No roast session updated: {roast_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to update roaster_id: {e}")
            return False

    def delete_roast_session(self, roast_id: str) -> bool:
        """Delete a roast session and all its data points"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # First delete all data points for this roast
                cursor.execute('''
                    DELETE FROM data_points WHERE roast_id = ?
                ''', (roast_id,))
                
                # Then delete the roast session
                cursor.execute('''
                    DELETE FROM roast_sessions WHERE id = ?
                ''', (roast_id,))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"Deleted roast session and data: {roast_id}")
                    return True
                else:
                    logger.warning(f"No roast session found to delete: {roast_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to delete roast session: {e}")
            return False
    
    def add_first_crack_event(self, roast_id: str, timestamp: str, detection_method: str,
                             confidence_score: float = None, signal_scores: Dict = None,
                             current_temperature: float = None, notes: str = None) -> bool:
        """Add a first crack event to the database"""
        try:
            import json
            signal_scores_json = json.dumps(signal_scores) if signal_scores else None
            
            logger.debug(f"Adding first crack event: roast_id={roast_id}, timestamp={timestamp}, method={detection_method}")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if roast session exists
                cursor.execute('''
                    SELECT id FROM roast_sessions WHERE id = ?
                ''', (roast_id,))
                
                if not cursor.fetchone():
                    logger.error(f"Roast session {roast_id} not found")
                    return False
                
                # Check if first crack already exists for this roast
                cursor.execute('''
                    SELECT id FROM first_crack_events WHERE roast_id = ?
                ''', (roast_id,))
                
                existing = cursor.fetchone()
                if existing:
                    # Delete existing first crack event first
                    cursor.execute('''
                        DELETE FROM first_crack_events WHERE roast_id = ?
                    ''', (roast_id,))
                    logger.info(f"Deleted existing first crack event for roast {roast_id}")
                
                # Insert new first crack event
                cursor.execute('''
                    INSERT INTO first_crack_events 
                    (roast_id, timestamp, detection_method, confidence_score, signal_scores, 
                     current_temperature, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (roast_id, timestamp, detection_method, confidence_score, signal_scores_json,
                      current_temperature, notes))
                
                fc_id = cursor.lastrowid
                logger.debug(f"Inserted first crack event with ID: {fc_id}")
                
                # Update roast session with first crack info
                cursor.execute('''
                    UPDATE roast_sessions 
                    SET first_crack_time = ?, first_crack_detected_by = ?
                    WHERE id = ?
                ''', (timestamp, detection_method, roast_id))
                
                updated_rows = cursor.rowcount
                logger.debug(f"Updated {updated_rows} roast session rows")
                
                conn.commit()
                logger.info(f"Successfully added first crack event for roast {roast_id} at {timestamp}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to add first crack event for roast {roast_id}: {e}", exc_info=True)
            return False
    
    def get_first_crack_event(self, roast_id: str) -> Optional[Dict]:
        """Get the first crack event for a roast session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM first_crack_events WHERE roast_id = ?
                ''', (roast_id,))
                
                row = cursor.fetchone()
                if row:
                    result = dict(row)
                    # Parse signal_scores JSON if present
                    if result.get('signal_scores'):
                        import json
                        try:
                            result['signal_scores'] = json.loads(result['signal_scores'])
                        except json.JSONDecodeError:
                            result['signal_scores'] = None
                    return result
                return None
                
        except Exception as e:
            logger.error(f"Failed to get first crack event: {e}")
            return None
    
    def update_first_crack_event(self, roast_id: str, **kwargs) -> bool:
        """Update an existing first crack event"""
        try:
            if not kwargs:
                return False
                
            # Build update query dynamically
            update_fields = []
            update_values = []
            
            for field, value in kwargs.items():
                if field in ['timestamp', 'detection_method', 'confidence_score', 
                           'current_temperature', 'notes']:
                    update_fields.append(f"{field} = ?")
                    update_values.append(value)
                elif field == 'signal_scores' and isinstance(value, dict):
                    import json
                    update_fields.append("signal_scores = ?")
                    update_values.append(json.dumps(value))
            
            if not update_fields:
                return False
            
            update_values.append(roast_id)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = f'''
                    UPDATE first_crack_events 
                    SET {', '.join(update_fields)}
                    WHERE roast_id = ?
                '''
                
                cursor.execute(query, update_values)
                
                # Also update roast session if timestamp or method changed
                if 'timestamp' in kwargs or 'detection_method' in kwargs:
                    cursor.execute('''
                        UPDATE roast_sessions 
                        SET first_crack_time = COALESCE(?, first_crack_time),
                            first_crack_detected_by = COALESCE(?, first_crack_detected_by)
                        WHERE id = ?
                    ''', (kwargs.get('timestamp'), kwargs.get('detection_method'), roast_id))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"Updated first crack event for roast {roast_id}")
                    return True
                else:
                    logger.warning(f"No first crack event found to update for roast {roast_id}")
                    return False
                
        except Exception as e:
            logger.error(f"Failed to update first crack event: {e}")
            return False
    
    def delete_first_crack_event(self, roast_id: str) -> bool:
        """Delete the first crack event for a roast session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete first crack event
                cursor.execute('''
                    DELETE FROM first_crack_events WHERE roast_id = ?
                ''', (roast_id,))
                
                # Clear first crack info from roast session
                cursor.execute('''
                    UPDATE roast_sessions 
                    SET first_crack_time = NULL, first_crack_detected_by = NULL
                    WHERE id = ?
                ''', (roast_id,))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"Deleted first crack event for roast {roast_id}")
                    return True
                else:
                    logger.warning(f"No first crack event found to delete for roast {roast_id}")
                    return False
                
        except Exception as e:
            logger.error(f"Failed to delete first crack event: {e}")
            return False
    
    def add_first_crack_prediction(self, roast_id: str, timestamp: str, confidence_score: float,
                                  signal_scores: Dict = None, predicted_temperature: float = None,
                                  prediction_algorithm: str = 'multi_signal_v1') -> bool:
        """Add a first crack prediction to the database"""
        try:
            import json
            signal_scores_json = json.dumps(signal_scores) if signal_scores else None
            
            logger.debug(f"Adding FC prediction: roast_id={roast_id}, timestamp={timestamp}, confidence={confidence_score}")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if roast session exists
                cursor.execute('''
                    SELECT id FROM roast_sessions WHERE id = ?
                ''', (roast_id,))
                
                if not cursor.fetchone():
                    logger.error(f"Roast session {roast_id} not found for prediction")
                    return False
                
                # Delete existing prediction for this roast (replace with new one)
                cursor.execute('''
                    DELETE FROM first_crack_predictions WHERE roast_id = ?
                ''', (roast_id,))
                
                # Insert new prediction
                cursor.execute('''
                    INSERT INTO first_crack_predictions 
                    (roast_id, timestamp, confidence_score, signal_scores, 
                     predicted_temperature, prediction_algorithm)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (roast_id, timestamp, confidence_score, signal_scores_json,
                      predicted_temperature, prediction_algorithm))
                
                prediction_id = cursor.lastrowid
                logger.debug(f"Inserted FC prediction with ID: {prediction_id}")
                
                conn.commit()
                logger.info(f"Successfully added FC prediction for roast {roast_id} at {timestamp} (confidence: {confidence_score:.2f})")
                return True
                
        except Exception as e:
            logger.error(f"Failed to add FC prediction for roast {roast_id}: {e}", exc_info=True)
            return False
    
    def get_first_crack_prediction(self, roast_id: str) -> Optional[Dict]:
        """Get the first crack prediction for a roast session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM first_crack_predictions WHERE roast_id = ?
                    ORDER BY created_at DESC LIMIT 1
                ''', (roast_id,))
                
                row = cursor.fetchone()
                if row:
                    result = dict(row)
                    # Parse signal_scores JSON if present
                    if result.get('signal_scores'):
                        import json
                        try:
                            result['signal_scores'] = json.loads(result['signal_scores'])
                        except json.JSONDecodeError:
                            result['signal_scores'] = None
                    return result
                return None
                
        except Exception as e:
            logger.error(f"Failed to get FC prediction: {e}")
            return None
    
    def delete_first_crack_prediction(self, roast_id: str) -> bool:
        """Delete the first crack prediction for a roast session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    DELETE FROM first_crack_predictions WHERE roast_id = ?
                ''', (roast_id,))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"Deleted FC prediction for roast {roast_id}")
                    return True
                else:
                    logger.warning(f"No FC prediction found to delete for roast {roast_id}")
                    return False
                
        except Exception as e:
            logger.error(f"Failed to delete FC prediction: {e}")
            return False
    
    def get_first_crack_summary(self, roast_id: str) -> Dict:
        """Get both manual FC event and prediction for a roast"""
        try:
            manual_fc = self.get_first_crack_event(roast_id)
            predicted_fc = self.get_first_crack_prediction(roast_id)
            
            return {
                'manual': manual_fc,
                'predicted': predicted_fc
            }
            
        except Exception as e:
            logger.error(f"Failed to get FC summary: {e}")
            return {'manual': None, 'predicted': None}