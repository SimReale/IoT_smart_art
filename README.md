# Smart Wall Art - Interactive Art That Changes Based on Environmental Input

The **_Smart Wall Art_** project merges art and technology to create dynamic, interactive experiences that adapt to the user's environment. This IoT project enables artwork to actively respond to daily rhythms through environmental sensing, data processing, and visual generation. The system emphasizes creativity and emotional connection, exploring how IoT technology can enhance our relationship with visual experiences.

## Features

- **Environmental Sensing**: Real-time monitoring of temperature, humidity, and light levels using ESP32-based sensing nodes
- **Motion Detection**: PIR sensor integration to activate the artwork when presence is detected
- **Generative Art Display**: Dynamic eye-shaped visualization that changes based on sensor readings
  - Color varies with temperature (green to red gradient)
  - Size responds to humidity levels
  - Animation speed adapts to light conditions
- **Time Series Forecasting**: Prophet-based machine learning models for predicting sensor values up to 24 hours ahead
- **Multi-Protocol Support**: Flexible data communication using CoAP or HTTP protocols
- **Real-time Dashboard**: Grafana integration for visualizing sensor data and forecasts
- **MQTT Configuration**: Remote configuration of sensing nodes via MQTT topics

## Architecture

The project consists of three main components:

1. **Sensing Node** (ESP32): Collects environmental data (temperature, humidity, light) and detects motion via PIR sensor
2. **Data Proxy** (Python): Receives sensor data via CoAP/HTTP, stores it in InfluxDB, and generates forecasts using Prophet models
3. **Display Node** (Python + Pygame): Subscribes to MQTT motion events and renders generative art based on real-time sensor data

<div align="center">
  <img src="media/architecture_graph.png" alt="Architecture Diagram" width="600"/>
</div>

> [!NOTE]
> Each blue block in the image is intended to be run on a different machine.

### Dashboard

#### Grafana Dashboard
Load the `dashboard_grafana.json` file into Grafana Cloud for real-time monitoring. The dashboard includes:
- Real-time sensor readings (temperature, humidity, light)
- Historical data visualization
- Prophet forecast predictions (24-hour horizon)

### Art Visualization
The display node generates a blinking eye visualization where:
- **Temperature** affects color (green = cold, red = warm)
- **Humidity** controls the eye size and animation frame rate
- **Light** influences animation speed

## Hardware Requirements

### Sensing Node
- **ESP32** development board
- **DHT22** temperature and humidity sensor
- **PIR sensor** (HC-SR501) for motion detection
- **TEMT6000** for ambient light sensing

## Software Requirements

### Python Dependencies
- Python 3.7+
- See `requirements.txt` for complete list:
  - `aiocoap` - CoAP protocol support
  - `aiohttp` - HTTP server framework
  - `paho-mqtt` - MQTT client
  - `influxdb3-python` - InfluxDB client
  - `pandas` - Data processing
  - `prophet` - Time series forecasting
  - `pygame` - Graphics rendering
  - `scikit-learn` - Machine learning metrics
  - `PyYAML` - Configuration file parsing
  - `schedule` - Task scheduling

### Arduino/ESP32 Setup
- Arduino IDE or PlatformIO
- ESP32 board support packages
- Required libraries:
  - `WiFi` (built-in)
  - `PubSubClient` (MQTT)
  - `DHT` (DHT sensor library)
  - `coap-simple`
  - `HTTPClient`

### Infrastructure
- **MQTT Broker** (e.g., Mosquitto) running on your network
- **InfluxDB 3.0** instance (cloud or self-hosted)
- **Grafana** (optional, for dashboard visualization)

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/SimReale/IoT_smart_art.git
cd IoT_smart_art
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure InfluxDB
Add `influx_config.yaml` with your InfluxDB credentials:
```yaml
IDB_TOKEN: "your-token-here"
IDB_ORG: "your-org"
IDB_HOST: "https://your-influx-host.com"
IDB_BUCKET: "your-bucket-name"
```

### 4. Configure WiFi and Server Address
Add `sensing_node/wifi_config.h` with your WiFi credentials:
```cpp
#ifndef _WIFI_CONFIG_H_
#define _WIFI_CONFIG_H_

#define MY_SSID "your-ssid"
#define MY_PASSWORD "your-password"

#endif
```

Edit `sensing_node/params.h` to set your MQTT broker and data proxy server address:
```cpp
#define SERVER_ADDRESS "your-proxy-ip"
```

Update `display_node.py` with your MQTT broker address:
```python
BROKER_ADDRESS = "your-mqtt-broker-ip"
```

### 5. Flash ESP32 Firmware
1. Open `sensing_node/sensing_node.ino` in Arduino IDE
2. Select your ESP32 board and port
3. Upload the firmware to your ESP32

## Usage

### Starting the Data Proxy
The data proxy receives sensor data and stores it in InfluxDB. It also generates forecasts using Prophet models.

```bash
# Using CoAP protocol (default)
python data_proxy.py --protocol coap --sampling_rate 60 --motion_alert 15

# Using HTTP protocol
python data_proxy.py --protocol http --sampling_rate 60 --motion_alert 15
```

The data proxy automatically publishes these configuration values when it starts.

**Parameters:**
- `--protocol`: Communication protocol (`coap` or `http`)
- `--sampling_rate`: Expected sensor sampling interval in seconds
- `--motion_alert`: Motion detection threshold in seconds (minimum 10)

### Starting the Display Node
The display node renders generative art based on sensor data when motion is detected.

```bash
python display_node.py
```

The application will:
- Connect to MQTT broker and subscribe to motion events
- Fetch latest sensor data from InfluxDB when motion is detected
- Render an animated eye visualization that responds to environmental conditions

### Training Forecasting Models
The analytics module trains Prophet models for time series forecasting.

```bash
# Run as a scheduled service for retraining the models (trains every 6 hours)
python data_analytics_module.py
```

The module:
- Retrieves historical data from InfluxDB (default: 7 days lookback)
- Trains Prophet models for temperature, humidity, and light
- Validates models using cross-validation
- Saves models to `forecasting_models/` directory

Models are automatically loaded by `data_proxy.py` for generating forecasts when new sensor data arrives.

## Project Structure

```
IoT_smart_art/
├── sensing_node/           # ESP32 firmware
│   ├── sensing_node.ino    # Main Arduino sketch
│   ├── params.h            # Hardware pin definitions and MQTT topics
│   └── wifi_config.h       # WiFi credentials (not in repo)
├── data_proxy.py           # Data proxy server (CoAP/HTTP → InfluxDB)
├── display_node.py         # Generative art display application
├── data_analytics_module.py # Prophet model training and forecasting
├── forcasting_model.ipynb  # Jupyter notebook for model exploration
├── influx_config.yaml      # InfluxDB configuration (not in repo)
├── requirements.txt        # Python dependencies
├── forecasting_models/     # Saved Prophet models
│   ├── model_temperature.json
│   ├── model_humidity.json
│   └── model_light.json
└── data/                   # Default datasets for model training
    └── default_dataset.csv
```
