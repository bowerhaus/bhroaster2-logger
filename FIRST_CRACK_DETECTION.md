# First Crack Detection System

## Overview
Implemented a comprehensive first crack detection system for coffee roasting that combines automatic multi-signal analysis with manual marking capabilities.

## Features Implemented

### 🔥 Multi-Signal Automatic Detection
- **Temperature Rate of Change (RoR)**: Detects temperature stalls/drops during first crack (30% weight)
- **VOC Spike Detection**: Monitors volatile organic compound releases (40% weight) 
- **CO2 Pattern Analysis**: Tracks CO2 release from coffee cells (20% weight)
- **Humidity Response**: Detects water vapor spikes (10% weight)
- **Weighted Scoring**: Combined confidence score with 75% threshold for automatic detection

### 🗄️ Database Schema
- **New table**: `first_crack_events` - stores FC detection data with timestamps, confidence scores, signal analysis
- **Enhanced table**: `roast_sessions` - added `first_crack_time` and `first_crack_detected_by` columns
- **Full CRUD operations**: Create, read, update, delete first crack events

### 🌐 API Endpoints
- `GET /api/roasts/{id}/first-crack` - Get first crack event for a roast
- `POST /api/roasts/{id}/first-crack` - Manual first crack marking (replaces existing)
- `DELETE /api/roasts/{id}/first-crack` - Remove first crack event
- **Real-time detection**: Integrated into existing live data endpoint
- **SocketIO events**: Instant notifications for FC detection

### 📊 Chart Visualization
- **Red dashed vertical line** marking first crack timing on roast profile chart
- **FC label** showing "FC (Manual)" or "FC (85%)" with confidence score
- **Custom Chart.js plugin**: Draws FC marker without external dependencies
- **Proper positioning**: Label appears inside chart area for visibility
- **Toggle controls**: All sensor plots can be toggled on/off including FC marker

### ⚙️ Configuration
```json
"first_crack": {
  "CONFIDENCE_THRESHOLD": 0.75,
  "MIN_TEMP_FOR_FC": 180,
  "VOC_SPIKE_THRESHOLD": 1.3,
  "CO2_SPIKE_THRESHOLD": 1.2,
  "HUMIDITY_SPIKE_THRESHOLD": 1.15,
  "TEMP_ROR_THRESHOLD": -2.0,
  "TEMP_WEIGHT": 0.30,
  "VOC_WEIGHT": 0.40,
  "CO2_WEIGHT": 0.20,
  "HUMIDITY_WEIGHT": 0.10,
  "ANALYSIS_WINDOW_SIZE": 120,
  "MIN_TEMP_FOR_FC": 180
}
```

## User Interface

### Manual Marking
- **"Mark FC" button** appears during active roasts
- **No confirmations** - single click to mark FC at current time
- **Multiple markings allowed** - can re-mark FC as many times as needed
- **Button label stays constant** - always shows "Mark FC" (doesn't change to "Re-mark")

### Visual Feedback
- **Chart marker**: Red dashed line with FC label
- **Real-time notifications**: Popup alerts when FC is detected automatically
- **Legend**: Shows "First Crack (FC)" in chart legend

## Files Modified

### Backend
- `src/services/first_crack_detector.py` - Core detection algorithm
- `src/database/models.py` - Database schema and CRUD operations
- `src/web/app.py` - API endpoints and real-time detection integration

### Frontend
- `templates/roast_detail.html` - Chart visualization and manual marking UI
- `templates/base.html` - Chart.js plugin dependencies (later removed)
- `config.json` - First crack detection configuration parameters

### Database Migration
- Added missing columns to existing `roast_sessions` table:
  ```sql
  ALTER TABLE roast_sessions ADD COLUMN first_crack_time TEXT;
  ALTER TABLE roast_sessions ADD COLUMN first_crack_detected_by TEXT;
  ```

## Detection Algorithm

### Analysis Window
- **2-minute sliding window** for real-time analysis
- **Temperature minimum**: 180°C before FC detection starts
- **Signal correlation**: Matches temperature/humidity readings within 1 second

### Confidence Scoring
```python
total_confidence = (
    temp_score * 0.30 +      # RoR analysis
    voc_score * 0.40 +       # VOC spike detection  
    co2_score * 0.20 +       # CO2 pattern analysis
    humidity_score * 0.10    # Humidity response
)
# Triggers FC detection when total_confidence >= 0.75
```

### Signal Thresholds
- **Temperature RoR**: -2.0°C/min drop indicates FC stall
- **VOC spike**: 30% increase over 30-60 second baseline
- **CO2 increase**: 20% increase over baseline
- **Humidity spike**: 15% increase indicating water vapor release

## Implementation Notes

### Technical Decisions
1. **Custom Chart.js plugin** instead of annotation plugin (dependency issues)
2. **Replace vs. append** FC events (allows re-marking without conflicts)
3. **Real-time detection** only during active roasts to avoid false positives
4. **Silent operation** - no confirmation dialogs for smooth roasting workflow

### Issues Resolved
1. **Chart.js annotation plugin loading** - Replaced with custom drawing
2. **Database schema migration** - Added missing columns to existing tables
3. **Roast ID validation** - Proper error handling for non-existent roasts
4. **Label positioning** - FC marker label now visible inside chart area

## Usage

### Automatic Detection
- System automatically analyzes sensor data during active roasts
- FC detected when confidence score exceeds 75%
- Real-time notifications appear when FC is found
- Chart immediately shows FC marker line

### Manual Marking
- Click "Mark FC" button during active roast
- FC marker appears at current time
- Can be re-marked multiple times
- Previous FC marks are automatically replaced

### Review Mode
- Historical roasts show FC markers if detected/marked
- Chart displays FC timing relative to roast start
- Confidence scores shown in FC label

## Future Enhancements
- **Second crack detection** using similar multi-signal approach
- **FC prediction** based on RoR trends
- **Sound detection** integration for crack audio analysis
- **Machine learning** to improve detection accuracy over time
- **Export FC data** for roast profiling and analysis