import asyncio
import json
import threading
import time
from influxdb import InfluxDBClient
import paho.mqtt.client as mqtt

# -----------------------------
# INITIAL CONFIGURATION
# -----------------------------
config = {
    "protocol": "http",   # or "coap"
    "sampling_rate": 5,   # seconds between samples
    "motion_alert": 10    # seconds for motion trigger threshold
}

INFLUX_CONFIG = {
    "host": "localhost",
    "port": 8086,
    "username": "admin",
    "password": "password",
    "database": "iot_data"
}

# -----------------------------
# INFLUXDB CONNECTION
# -----------------------------
influx_client = InfluxDBClient(
    host=INFLUX_CONFIG["host"],
    port=INFLUX_CONFIG["port"],
    username=INFLUX_CONFIG["username"],
    password=INFLUX_CONFIG["password"],
    database=INFLUX_CONFIG["database"]
)

# -----------------------------
# DATA HANDLING FUNCTIONS
# -----------------------------

def send_to_influx(data):
    """Send a measurement to InfluxDB."""
    json_body = [
        {
            "measurement": "environment",
            "fields": {
                "temperature": float(data.get("temperature", 0.0)),
                "humidity": float(data.get("humidity", 0.0)),
                "light": float(data.get("light", 0.0))
            }
        }
    ]
    influx_client.write_points(json_body)
    print(f"[INFLUX] Data sent: {json_body}")

async def coap_listener():
    """CoAP server listening for sensor data."""
    from aiocoap import Context, Message, resource

    class SensorDataResource(resource.Resource):
        async def render_post(self, request):
            try:
                payload = json.loads(request.payload.decode())
                send_to_influx(payload)
                return Message(code=2.04, payload=b"OK")
            except Exception as e:
                print(f"[COAP] Error: {e}")
                return Message(code=5.00, payload=str(e).encode())

    root = resource.Site()
    root.add_resource(["data"], SensorDataResource())

    context = await Context.create_server_context(root)
    print("[COAP] Listening on port 5683 for POST /data")
    await asyncio.get_running_loop().create_future()  # Keeps server running

def http_listener():
    """HTTP server listening for sensor data."""
    from flask import Flask, request
    app = Flask(__name__)

    @app.route("/data", methods=["POST"])
    def receive_data():
        try:
            payload = request.json
            send_to_influx(payload)
            return "OK", 200
        except Exception as e:
            print(f"[HTTP] Error: {e}")
            return str(e), 400

    print("[HTTP] Listening on port 8080 for POST /data")
    app.run(host="0.0.0.0", port=8080)

# -----------------------------
# MQTT CALLBACKS
# -----------------------------

def on_connect(client, userdata, flags, rc):
    print("[MQTT] Connected with result code:", rc)
    client.subscribe("config/#")

def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode().strip()
    print(f"[MQTT] Message on {topic}: {payload}")

    if topic == "config/protocol" and payload in ["coap", "http"]:
        config["protocol"] = payload
        print(f"[CONFIG] Protocol set to: {payload}")

    elif topic == "config/sampling_rate":
        try:
            config["sampling_rate"] = int(payload)
            print(f"[CONFIG] Sampling rate set to: {config['sampling_rate']} seconds")
        except ValueError:
            print("[ERROR] Invalid sampling rate value")

    elif topic == "config/motion_alert":
        try:
            config["motion_alert"] = int(payload)
            print(f"[CONFIG] Motion alert set to: {config['motion_alert']} seconds")
        except ValueError:
            print("[ERROR] Invalid motion alert value")

# -----------------------------
# MQTT CLIENT SETUP
# -----------------------------

def start_mqtt():
    """Start MQTT client in background."""
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("localhost", 1883, 60)
    client.loop_forever()

# -----------------------------
# SERVER STARTUP
# -----------------------------

def start_server():
    """Start the selected communication protocol server."""
    if config["protocol"] == "http":
        http_listener()
    elif config["protocol"] == "coap":
        asyncio.run(coap_listener())

# -----------------------------
# MAIN ENTRY POINT
# -----------------------------

if __name__ == "__main__":
    mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
    mqtt_thread.start()

    print("[MAIN] Waiting for MQTT configuration...")
    time.sleep(2)

    start_server()
