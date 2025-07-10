# Coffee Roaster Data Logger

A Python-based data logging application for coffee roasting that captures temperature and humidity data from multiple sensors.

## Features

- Real-time data collection from DHT22 and SHT31 sensors
- Web interface for viewing roast sessions and data
- SQLite database for data storage
- Configurable sensor setup
- Live chart updates during roasting

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure sensors in `config.json`

3. Run the application:
```bash
python src/app.py
```

4. Access the web interface at `http://localhost:8080`

## Hardware Requirements

- Raspberry Pi Compute Module
- DHT22 temperature/humidity sensor
- Adafruit SHT31 sensor
- GPIO and I2C connections as configured

## Project Structure

```
src/
├── sensors/     # Sensor interface modules
├── database/    # Database models and operations
├── web/         # Flask web application
└── utils/       # Utility functions
static/          # CSS and JavaScript files
templates/       # HTML templates
tests/           # Test files
```