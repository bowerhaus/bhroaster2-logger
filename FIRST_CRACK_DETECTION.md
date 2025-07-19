# First Crack Detection & Prediction System

## Overview
Implemented a unified first crack system for coffee roasting that combines:
1. **Manual marking** - User-controlled FC marking during roasts
2. **Live prediction** - Real-time FC prediction during active roasts with 30-second lookahead
3. **Historical prediction** - Post-analysis prediction on existing roast data

## Features Implemented

### 🔥 Unified Multi-Signal Algorithm
- **Temperature Rate of Change (RoR)**: Detects temperature stalls/drops during first crack (25% weight)
- **VOC Spike Detection**: Monitors volatile organic compound releases (45% weight) 
- **CO2 Pattern Analysis**: Tracks CO2 release from coffee cells (20% weight)
- **Humidity Response**: Detects water vapor spikes (10% weight)
- **Weighted Scoring**: Combined confidence score with 50% threshold for detection
- **Exhaust Gas Optimized**: Calibrated for exhaust temperature measurements (30°C minimum)

### 🗄️ Database Schema
- **Table**: `first_crack_events` - stores manual FC markings with timestamps, confidence scores
- **Table**: `first_crack_predictions` - stores predicted FC data with algorithm analysis
- **Enhanced table**: `roast_sessions` - added `first_crack_time` and `first_crack_detected_by` columns
- **Full CRUD operations**: Create, read, update, delete both events and predictions

### 🌐 API Endpoints
#### Manual First Crack
- `GET /api/roasts/{id}/first-crack` - Get manual first crack event for a roast
- `POST /api/roasts/{id}/first-crack` - Manual first crack marking (replaces existing)
- `DELETE /api/roasts/{id}/first-crack` - Remove manual first crack event

#### Predicted First Crack
- `GET /api/roasts/{id}/first-crack-prediction` - Get predicted first crack for a roast
- `POST /api/roasts/{id}/first-crack-prediction` - Generate first crack prediction
- `DELETE /api/roasts/{id}/first-crack-prediction` - Remove first crack prediction

#### Combined Data
- `GET /api/roasts/{id}/first-crack-summary` - Get both manual and predicted FC data
- **Live data endpoint**: Includes both manual and predicted FC in polling responses
- **SocketIO events**: Real-time notifications for manual detection and live predictions

### 📊 Chart Visualization
- **Red dashed line**: Manual FC marking - "FC (Manual)"
- **Orange dash-dot line**: Predicted FC - "FC (Predicted X%)" with confidence score
- **Live predictions**: Show as orange markers that update in real-time during roasting
- **Custom Chart.js plugin**: Draws both markers simultaneously without external dependencies
- **Proper positioning**: Labels appear inside chart area for visibility
- **Toggle controls**: All sensor plots can be toggled on/off including FC markers

### ⚙️ Configuration
```json
"first_crack": {
  "TEMP_ROR_THRESHOLD": -1.0,
  "VOC_SPIKE_THRESHOLD": 1.2,
  "CO2_SPIKE_THRESHOLD": 1.15,
  "HUMIDITY_SPIKE_THRESHOLD": 1.1,
  "TEMP_WEIGHT": 0.25,
  "VOC_WEIGHT": 0.45,
  "CO2_WEIGHT": 0.20,
  "HUMIDITY_WEIGHT": 0.10,
  "ANALYSIS_WINDOW_SIZE": 120,
  "CONFIDENCE_THRESHOLD": 0.50,
  "MIN_TEMP_FOR_FC": 30,
  "LOOKAHEAD_SECONDS": 30
}
```

## User Interface

### Manual Marking
- **"Mark FC" button** appears during active roasts
- **No confirmations** - single click to mark FC at current time
- **Multiple markings allowed** - can re-mark FC as many times as needed
- **Button label stays constant** - always shows "Mark FC" (doesn't change to "Re-mark")

### Live Predictions
- **Automatic generation** during active roasts as data accumulates
- **30-second lookahead** - can detect FC that occurred up to 30 seconds ago
- **Progressive refinement** - updates prediction as roast progresses if confidence improves
- **Orange notifications** - subtle notifications when predictions update during roasting

### Visual Feedback
- **Manual FC**: Red dashed line with "FC (Manual)" label
- **Predicted FC**: Orange dash-dot line with "FC (Predicted X%)" label
- **Live notifications**: 
  - Red notifications for manual FC detection
  - Orange notifications for live prediction updates
- **Dual markers**: Can show both manual and predicted FC simultaneously

## Files Modified

### Backend
- `src/services/first_crack_predictor.py` - Unified prediction algorithm for both live and historical analysis
- `src/services/first_crack_detector.py` - Legacy real-time detector (deprecated)
- `src/database/models.py` - Database schema with separate tables for events and predictions
- `src/web/app.py` - API endpoints and unified live prediction integration

### Frontend
- `templates/roast_detail.html` - Chart visualization supporting dual FC markers and live updates
- `config.json` - Unified first crack configuration optimized for exhaust gas measurements

### Database Schema
- `first_crack_events` table for manual markings
- `first_crack_predictions` table for algorithmic predictions
- Existing `roast_sessions` table enhanced with FC columns

## Unified Algorithm

### Analysis Approach
- **Same algorithm** for both live and historical analysis
- **2-minute analysis window** for pattern detection
- **Exhaust gas calibration**: 30°C minimum temperature (vs 180°C for bean temp)
- **Signal correlation**: Matches sensor readings within time windows

### Confidence Scoring
```python
total_confidence = (
    temp_score * 0.25 +      # RoR analysis (reduced weight)
    voc_score * 0.45 +       # VOC spike detection (primary indicator)
    co2_score * 0.20 +       # CO2 pattern analysis
    humidity_score * 0.10    # Humidity response
)
# Triggers FC detection when total_confidence >= 0.50
```

### Signal Thresholds (Exhaust Gas Optimized)
- **Temperature RoR**: -1.0°C/min slowdown indicates FC pattern
- **VOC spike**: 20% increase over baseline (primary FC indicator)
- **CO2 increase**: 15% increase over baseline
- **Humidity spike**: 10% increase indicating water vapor release

## Implementation Features

### Technical Decisions
1. **Unified algorithm** - Same predictor used for live and historical analysis
2. **Separate data storage** - Manual events and predictions stored independently
3. **Live lookahead** - 30-second backward analysis for real-time detection
4. **Progressive refinement** - Predictions update as confidence improves during roasting
5. **Exhaust gas optimization** - Thresholds calibrated for exhaust temperature measurements

### Live vs Historical Consistency
- **Identical algorithms** - Live predictions exactly match post-roast historical analysis
- **Same configuration** - No separate settings for live vs historical
- **Confidence-based updates** - Only updates predictions with higher confidence scores
- **Persistent storage** - Live predictions saved as historical predictions

### Issues Resolved
1. **Algorithm consistency** - Eliminated differences between live and historical analysis
2. **Exhaust gas calibration** - Adjusted thresholds for exhaust temperature measurements
3. **Dual marker support** - Chart displays both manual and predicted FC simultaneously
4. **Real-time updates** - Live predictions update smoothly without page reloads

## Usage

### Live Prediction (During Roasting)
- System continuously analyzes all accumulated roast data
- Generates predictions when confidence threshold (50%) is exceeded
- Updates predictions if higher confidence candidates are found
- Shows orange FC marker with confidence percentage
- Provides 30-second lookahead for FC detection

### Manual Marking (During Roasting)
- Click "Mark FC" button during active roast
- Red FC marker appears at current time
- Can be re-marked multiple times
- Manual markings take precedence over predictions for user control

### Historical Analysis (Post-Roast)
- Automatically generates predictions for completed roasts
- Uses identical algorithm as live prediction
- Shows orange FC marker if prediction exists
- Can display both manual and predicted FC markers simultaneously

### Review Mode
- Historical roasts show both manual and predicted FC markers
- Chart displays FC timing relative to roast start
- Confidence scores shown in FC labels
- Different colors distinguish manual (red) vs predicted (orange) FC

## Configuration Notes

### Exhaust Gas Measurements
- **MIN_TEMP_FOR_FC: 30** - Minimum exhaust temperature (vs 180°C for bean temp)
- **Adjusted thresholds** - More sensitive spike detection for diluted exhaust signals
- **VOC emphasis** - Higher weight (45%) since aromatics are primary exhaust indicator
- **Temperature de-emphasis** - Lower weight (25%) since exhaust shows smaller temperature changes

### Algorithm Tuning
- **CONFIDENCE_THRESHOLD: 0.50** - Balanced sensitivity for both live and historical
- **LOOKAHEAD_SECONDS: 30** - Allows detection of FC up to 30 seconds after occurrence
- **Unified settings** - Same configuration used for all FC detection scenarios

## Future Enhancements
- **Second crack detection** using similar multi-signal approach
- **Roast profiling integration** for predictive FC timing based on heating curves
- **Sound detection** integration for crack audio analysis
- **Machine learning** to improve detection accuracy over time with roast data
- **Export FC data** for external roast profiling and analysis tools