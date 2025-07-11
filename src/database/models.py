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
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
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
                
                # Create indexes for performance
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_data_points_roast_id 
                    ON data_points (roast_id)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_data_points_timestamp 
                    ON data_points (timestamp)
                ''')
                
                conn.commit()
                logger.info(f"Database initialized at {self.db_path}")
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def create_roast_session(self, name: str) -> str:
        """Create a new roast session and return its ID"""
        try:
            roast_id = str(uuid.uuid4())
            start_time = datetime.now().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO roast_sessions (id, start_time, name, status)
                    VALUES (?, ?, ?, 'active')
                ''', (roast_id, start_time, name))
                conn.commit()
                
            logger.info(f"Created roast session: {roast_id} - {name}")
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
    
    def get_roast_sessions(self, limit: int = 50) -> List[Dict]:
        """Get list of roast sessions"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id, start_time, end_time, name, status,
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