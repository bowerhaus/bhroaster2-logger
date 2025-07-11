# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based coffee roasting data logger application that runs on Raspberry Pi. It collects temperature and humidity data from multiple sensors (DHT22, SHT31) during coffee roasting sessions and provides a web interface for monitoring and analyzing roast data.

## Development Commands

### Running the Application
```bash
# Start the main application
python src/app.py

# The web interface will be available at http://localhost:5000
```

### Dependencies
```bash
# Install Python dependencies
pip install -r requirements.txt

# Key dependencies include:
# - Flask for web framework
# - Flask-SocketIO for real-time communication
# - Adafruit CircuitPython libraries for sensors
```

### Configuration
- Edit `config.json` to configure sensors, database path, and web server settings
- Sensor configuration supports DHT22 (GPIO) and SHT31 (I2C) sensors
- Database uses SQLite stored in `data/roasts.db`

## Architecture

### Core Components

**Entry Point**: `src/app.py` - Main application entry point that initializes and runs the web application

**Web Application**: `src/web/app.py` - Flask application with:
- REST API endpoints for roast management (`/api/roasts`)
- WebSocket support for real-time data streaming
- HTML templates for web interface

**Database Layer**: `src/database/models.py` - SQLite database management with:
- `roast_sessions` table for roast metadata
- `data_points` table for sensor readings
- Methods for CRUD operations on roast data

**Sensor Management**: 
- `src/sensors/sensor_manager.py` - Global sensor manager that handles all sensor readings in a dedicated thread
- `src/sensors/managed_*.py` - Sensor implementations for DHT22 and SHT31
- `src/sensors/base.py` - Base sensor interface

**Data Collection**: `src/services/data_collector.py` - Coordinates data collection from sensors to database during active roast sessions

### Key Design Patterns

- **Threaded Sensor Reading**: All sensor operations run in a dedicated thread to avoid GPIO conflicts
- **WebSocket Communication**: Real-time data updates pushed to web clients via SocketIO
- **Configuration-Driven**: Sensor setup defined in JSON config file
- **Session-Based Logging**: Data collection only occurs during active roast sessions

### Data Flow

1. Sensor Manager continuously reads from configured sensors (2-second intervals)
2. Data Collector monitors for active roast sessions
3. During active sessions, sensor data is stored in database and broadcast via WebSocket
4. Web interface displays real-time charts and historical roast data

### File Structure

```
src/
├── app.py              # Main entry point
├── web/app.py          # Flask web application
├── database/models.py  # SQLite database operations
├── sensors/            # Sensor interfaces and manager
├── services/           # Data collection service
└── utils/              # Utility functions

templates/              # HTML templates
static/                 # CSS and JavaScript assets
data/                   # SQLite database storage
config.json             # Application configuration
```

## Development Notes

- The application is designed for Raspberry Pi with GPIO access for sensors
- SQLite database automatically initializes required tables on first run
- Web interface uses Tailwind CSS for styling
- Real-time updates require WebSocket connection
- Sensor readings are cached to handle sensor failures gracefully
- Only one active roast session is allowed at a time