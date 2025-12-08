import asyncio
import argparse
import yaml
import json
import paho.mqtt.client as mqtt
import aiocoap.resource as resource
import aiocoap
from aiohttp import web
from influxdb_client_3 import InfluxDBClient3, Point
from time import time
from datetime import datetime, timezone
from pathlib import Path


# Load InfluxDB config
CONFIG_PATH = Path.cwd().joinpath("influx_config.yaml")
with open(CONFIG_PATH, "r", encoding="utf-8") as _f:
  INFLUX_CONFIG = yaml.safe_load(_f) or {}

try:
  INFLUX_CLIENT = InfluxDBClient3(
    host=INFLUX_CONFIG.get("IDB_HOST", ""), 
    token=INFLUX_CONFIG.get("IDB_TOKEN", ""), 
    org=INFLUX_CONFIG.get("IDB_ORG", ""),
    database=INFLUX_CONFIG.get("IDB_BUCKET", "")
  )
except Exception as e:
  print(f"[{datetime.fromtimestamp(time())}] {e}: InfluxDB Init Error!")

TOPIC_CONFIG = "config/"
DATA_PATH = "sensors"
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
COAP_PORT = 5683
HTTP_PORT = 8080
# Default ports of each protocol used for communication, but made them explicit for allowing tests on different ports


def on_connect(client, userdata, flags, rc, properties):
  
  if rc == 0:
    print(f"[{datetime.fromtimestamp(time())}] MQTT connection established.")
    for topic in userdata.keys():
      client.publish(f"{TOPIC_CONFIG}{topic}", userdata[topic], retain=True)
    print(f"   Config: {userdata}")
  else:
    print(f"[{datetime.fromtimestamp(time())}] ConnectionError: MQTT connection failed.")


def save_to_influx(payload_dict):

  try:
    node_id = str(payload_dict.get("node_id", ""))
    temp = float(payload_dict.get("temperature", 0))
    hum = float(payload_dict.get("humidity", 0))
    light = float(payload_dict.get("light", 0))
    timestamp = datetime.now(timezone.utc)    # Since natively InfluxDB works with UTC timestamps
    point = Point("sensors") \
      .tag("node_id", node_id) \
      .field("temperature", temp) \
      .field("humidity", hum) \
      .field("light", light) \
      .time(timestamp)
    INFLUX_CLIENT.write(point)
    # This call is blocking, so if the Influx server is slow it could block any other process (MQTT, CoAP/HTTP).
    # Since this is a small prototype, it is possible to use it like above, otherwise it should be inserted into a thread executor.

  except Exception as e:
    print(f"[{datetime.fromtimestamp(time())}] InfluxDB saving error: {e}")


class CoAPResource(resource.Resource):

  async def render_put(self, request):
    try:
      payload = request.payload.decode('utf-8')
      data = json.loads(payload)
      print(f"[{datetime.fromtimestamp(time())}] Data received: {data}.")
      save_to_influx(data)
      return aiocoap.Message(code=aiocoap.CHANGED, payload=b"OK CoAP")
    except json.JSONDecodeError:
      print(f"[{datetime.fromtimestamp(time())}] Decoding Error in the JSON message format.")
      return aiocoap.Message(code=aiocoap.BAD_REQUEST, payload=b"Invalid JSON")
    except Exception as e:
      print(f"[{datetime.fromtimestamp(time())}] Internal Server Error: {e}.")
      return aiocoap.Message(code=aiocoap.INTERNAL_SERVER_ERROR)


async def http_handler(request):

  try:
    data = await request.json()
    print(f"[{datetime.fromtimestamp(time())}] Data received: {data}.")
    save_to_influx(data)
    return web.Response(text="OK HTTP")
  except json.JSONDecodeError:
    print(f"[{datetime.fromtimestamp(time())}] Decoding Error in the JSON message format.")
    return web.Response(status=400, text="Invalid JSON")
  except Exception as e:
    print(f"[{datetime.fromtimestamp(time())}] Internal Server Error: {e}.")
    return web.Response(status=500, text="Server Error")


async def main(config):

  protocol = config['protocol']
  
  # Client MQTT
  mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, userdata=config)
  mqtt_client.on_connect = on_connect
  mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)   # 60 is the keepalive seconds parameter (for system resilience)
  mqtt_client.loop_start()

  # CoAP/HTTP handler
  if protocol == 'coap':
    try:
      root = resource.Site()
      root.add_resource([DATA_PATH], CoAPResource())
      await aiocoap.Context.create_server_context(root, bind=('192.168.1.7', COAP_PORT))    # listening on coap://192.168.1.7:5683/sensors
    except KeyboardInterrupt as ke:
      print(f"[{datetime.fromtimestamp(time())}] {ke}: CoAP interrupted!")

  elif protocol == 'http':
    try:
      app = web.Application()
      app.router.add_post(f"/{DATA_PATH}", http_handler)
      runner = web.AppRunner(app)
      await runner.setup()
      site = web.TCPSite(runner, '0.0.0.0', HTTP_PORT)    # listening on http://<IP>:8080/sensors
      await site.start()
    except KeyboardInterrupt as ke:
      print(f"[{datetime.fromtimestamp(time())}] {ke}: HTTP interrupted!")

  # Stopping
  try:
    await asyncio.get_running_loop().create_future()
  except asyncio.CancelledError:
    pass
  except KeyboardInterrupt:
    mqtt_client.loop_stop()
    mqtt_client.disconnect()


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
    print(f"[{datetime.fromtimestamp(time())}] ConfigError: motion_alert must be greater than 10 seconds. Set to default value of 15 seconds.")
  else:
    config_data = {
      "protocol": args.protocol,
      "sampling_rate": args.sampling_rate,
      "motion_alert": args.motion_alert
    }
  
  try:
    asyncio.run(main(config_data))
  except KeyboardInterrupt as ke:
    print(f"[{datetime.fromtimestamp(time())}] {ke}")
