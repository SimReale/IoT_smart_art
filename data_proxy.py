import asyncio
import argparse
import yaml
import paho.mqtt.client as mqtt
from influxdb_client_3 import InfluxDBClient3, Point
from time import time
from datetime import datetime
from pathlib import Path


# Load InfluxDB config
CONFIG_PATH = Path.cwd().joinpath("influx_config.yaml")
INFLUX_CONFIG = {}
try:
  with open(CONFIG_PATH, "r", encoding="utf-8") as _f:
    INFLUX_CONFIG = yaml.safe_load(_f) or {}
except FileNotFoundError:
  print(f"Config file not found: {CONFIG_PATH} — using defaults in-file.")
except Exception as _e:
  print(f"Error loading config file {CONFIG_PATH}: {_e}")

IDB_TOKEN = INFLUX_CONFIG["IDB_TOKEN"]
IDB_ORG = INFLUX_CONFIG["IDB_ORG"]
IDB_HOST = INFLUX_CONFIG["IDB_HOST"]
IDB_BUCKET = INFLUX_CONFIG["IDB_BUCKET"]

TOPIC_CONFIG = "config/"
DATA_PATH = "sensors"
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
COAP_PORT = 5683
HTTP_PORT = 8080 


def on_connect(client, userdata, flags, reason_code, properties):
  
  if reason_code == 0:
    print(f"[{datetime.fromtimestamp(time())}] MQTT Connection established.")
    for topic in userdata.keys():
      client.publish(TOPIC_CONFIG + topic, userdata[topic], retain=True)
    print("Config:") 
    print(f" - protocol: {userdata['protocol']}")
    print(f" - sampling_rate: {userdata['sampling_rate']}")
    print(f" - motion_alert: {userdata['motion_alert']}")


def save_to_influx(client, payload_dict):

  try:
    temp, hum, light = payload_dict["temperature"], payload_dict["humidity"], payload_dict["light"]
    point = Point("sensors") \
      .tag("node_id", "main_hall") \
      .field("temperature", temp) \
      .field("humidity", hum) \
      .field("light", light)
    client.write(point)

  except Exception as e:
    print(f"InfluxDB saving error: {e}")


async def main(config):

  protocol, sampling_rate, motion_alert = config['protocol'], config['sampling_rate'], config['motion_alert']
  
  # Client MQTT
  mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, userdata=config)
  mqtt_client.on_connect = on_connect
  mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)   # 60 is the keepalive seconds parameter (for system resilience)
  mqtt_client.loop_start()

  # Influx client
  influx_client = InfluxDBClient3(
    host=IDB_HOST, 
    token=IDB_TOKEN, 
    org=IDB_ORG,
    database=IDB_BUCKET
    )

  # CoAP/HTTP handler
  if protocol == 'coap':
    pass
  elif protocol == 'http':
    pass

  # Stopping
  try:
    await asyncio.get_running_loop().create_future()
  except KeyboardInterrupt:
    print("Spegnimento...")
    mqtt_client.loop_stop()


if __name__ == "__main__":
  parser = argparse.ArgumentParser(
    description="Node that acts as a proxy for data and enables configuration parameters."
  )
  parser.add_argument(
    "--protocol",
    default='coap',
    choices=['coap', 'http'],
    help="Protocol to use for data communication from sensors."
  )
  parser.add_argument(
    "--sampling_rate",
    type=int,
    default=60,
    help="Sampling rate in seconds for data acquisition from sensors."
  )
  parser.add_argument(
    "--motion_alert",
    type=int,
    default=15,
    help="Number of seconds to trigger a motion alert for visualisation purposes (> 10s)."
  )
  args = parser.parse_args()

  if args.motion_alert <= 10:
    config_data = {
      "protocol": args.protocol,
      "sampling_rate": args.sampling_rate,
      "motion_alert": 15
    }
    print("Error: motion_alert must be greater than 10 seconds. Set to default value of 15 seconds.")
  else:
    config_data = {
      "protocol": args.protocol,
      "sampling_rate": args.sampling_rate,
      "motion_alert": args.motion_alert
    }
  
  asyncio.run(main(config_data))
