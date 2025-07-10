# Coffee Roaster Data Logger - Product Requirements Document

## 1. Product Overview

### 1.1 Purpose
A Python-based data logging application for coffee roasting that captures temperature, humidity, and future sensor data (CO2, VOC) to analyze roast profiles and predict first crack timing.

### 1.2 Target Platform
- Raspberry Pi Compute Module (16GB disk)
- Python backend with web interface
- Tailwind CSS for styling
- Local network access with remote capability

### 1.3 Key Users
- Coffee roasters analyzing roast profiles
- Operators monitoring active roasts
- Future: automated roast control systems

## 2. Core Requirements

### 2.1 Data Collection
- **Sampling Rate**: 1 data point per second
- **Session Duration**: Typical 10-minute roasts (600 data points)
- **Data Retention**: Indefinite storage
- **Sensor Support**: Configurable via config.json
  - DHT22 (temperature/humidity)
  - Adafruit SHT31 (precision temperature/humidity)
  - Adafruit SGP30 (CO2/VOC - future)
- **Multi-sensor Logging**: Log from multiple temp/humidity sensors simultaneously
- **Data Integrity**: Log all readings as-is (no validation/filtering)

### 2.2 Sensor Configuration
```json
{
  "sensors": [
    {
      "type": "DHT22",
      "name": "DHT22",
      "gpio_pin": 4,
      "metrics": ["temperature", "humidity"]
    },
    {
      "type": "SHT31",
      "name": "SHT32",
      "i2c_address": "0x44",
      "metrics": ["temperature", "humidity"]
    }
  ]
}
```

### 2.3 Web Interface Requirements
- **Access**: Remote access over local network (no authentication required)
- **Primary Screen**: List of completed roasts with timestamps
- **Roast Detail**: Chart visualization of selected roast data
- **Session Control**: Manual start/stop roast logging
- **Real-time Updates**: Live chart updates during active roast (preferred over polling)
- **Responsive Design**: Tailwind CSS implementation

## 3. Technical Specifications

### 3.1 Architecture
- **Backend**: Python Flask/FastAPI web server
- **Frontend**: HTML/JavaScript with Tailwind CSS
- **Database**: SQLite for roast data storage
- **Real-time**: WebSockets for live updates
- **Sensor Interface**: GPIO/I2C libraries for sensor communication

### 3.2 Data Model
```python
# Roast Session
{
  "id": "uuid",
  "start_time": "datetime",
  "end_time": "datetime",
  "name": "string",
  "status": "active|completed|stopped"
}

# Data Point
{
  "roast_id": "uuid",
  "timestamp": "datetime",
  "sensor_name": "string",
  "metric_type": "temperature|humidity|co2|voc",
  "value": "float",
  "unit": "string"
}
```

### 3.3 API Endpoints
- `GET /roasts` - List all roast sessions
- `POST /roasts` - Start new roast session
- `PUT /roasts/{id}/stop` - Stop active roast
- `GET /roasts/{id}` - Get roast details and data
- `GET /roasts/{id}/data` - Get roast data points
- `WebSocket /roasts/{id}/live` - Live data stream

## 4. Feature Specifications

### 4.1 MVP Features (Phase 1)
- [x] Temperature and humidity data collection
- [x] Manual roast session start/stop
- [x] Basic roast list interface
- [x] Simple line chart visualization
- [x] SQLite data storage
- [x] Configurable sensor setup
- [x] Real-time data updates

### 4.2 Future Enhancements (Phase 2+)
- [ ] CO2/VOC sensor integration
- [ ] First crack prediction algorithm (180-215°C range)
- [ ] Interactive charts (zoom, pan, hover tooltips)
- [ ] Data export functionality (CSV/JSON)
- [ ] Roast comparison overlays
- [ ] Temperature rate-of-change calculations
- [ ] Roast profile templates
- [ ] Mobile-responsive improvements

## 5. User Interface Requirements

### 5.1 Main Dashboard
- Clean list of roasts with:
  - Timestamp
  - Duration
  - Peak temperature
  - Status indicator
- "Start New Roast" button
- Search/filter capabilities (future)

### 5.2 Roast Detail View
- Multi-line chart showing:
  - Temperature readings (multiple sensors)
  - Humidity readings
  - Time-based X-axis
- Session metadata (start/end times, duration)
- Back to dashboard navigation

### 5.3 Active Roast View
- Live updating chart
- Current readings display
- Stop roast button
- Timer display

## 6. Technical Constraints

### 6.1 Hardware Limitations
- 16GB disk space (monitor usage)
- GPIO/I2C pin availability
- Power consumption considerations
- Network connectivity requirements

### 6.2 Performance Requirements
- 1-second data collection reliability
- Web interface response < 2 seconds
- Real-time updates with < 3-second latency
- Handle 100+ roast sessions without performance degradation

## 7. Success Criteria

### 7.1 MVP Success Metrics
- [ ] Successfully log 10-minute roast sessions
- [ ] Reliable 1-second data sampling
- [ ] Web interface accessible from network devices
- [ ] Data persistence across system reboots
- [ ] Multiple sensor support working

### 7.2 Future Success Metrics
- [ ] First crack prediction accuracy > 80%
- [ ] Support for additional sensor types
- [ ] Data export functionality
- [ ] Mobile device compatibility

## 8. Implementation Strategy

### 8.1 Development Phases
1. **Phase 1 (MVP)**: Core logging and basic web interface
2. **Phase 2**: Enhanced visualization and CO2/VOC sensors
3. **Phase 3**: Predictive analytics and advanced features
4. **Phase 4**: Mobile optimization and data export

### 8.2 Testing Strategy
- Unit tests for sensor interfaces
- Integration tests for data collection
- Web interface functionality testing
- Long-duration reliability testing
- Multiple sensor configuration testing

## 9. Risk Mitigation

### 9.1 Technical Risks
- **Sensor failure**: Multiple sensor redundancy
- **Data loss**: Regular SQLite backups
- **Network issues**: Local storage ensures data safety
- **GPIO conflicts**: Configurable pin assignments

### 9.2 User Experience Risks
- **Complex interface**: Progressive disclosure approach
- **Slow performance**: Optimize for Pi hardware constraints
- **Data overload**: Focus on essential metrics first

---

*This PRD serves as the foundation for incremental development, starting with the MVP and building toward advanced roast analysis capabilities.*