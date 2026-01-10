import asyncio
import argparse
import logging
import socket
import yaml
import json
import numpy as np
import pandas as pd
import paho.mqtt.client as mqtt
import aiocoap.resource as resource
import aiocoap
from aiohttp import web
from influxdb_client_3 import InfluxDBClient3, Point
from prophet.serialize import model_from_json
from datetime import datetime, timezone
from pathlib import Path


# Load InfluxDB config
WORKING_DIR = Path.cwd()
CONFIG_PATH = WORKING_DIR.joinpath("influx_config.yaml")
with open(CONFIG_PATH, "r", encoding="utf-8") as _f:
  INFLUX_CONFIG = yaml.safe_load(_f) or {}

PROXY_NODE_ADDRESS = socket.gethostbyname(socket.gethostname())
PROXY_CLIENT_ID = "DataProxy"
TOPIC_CONFIG = "config/"
DATA_PATH = "sensors"
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
COAP_PORT = 5683
HTTP_PORT = 8080
# Default ports of each protocol used for communication, but made them explicit for allowing tests on different ports

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def on_connect(client, userdata, flags, rc, properties):
  
  if rc == 0:
    logging.info("MQTT connection established.")
    for topic in userdata.keys():
      client.publish(f"{TOPIC_CONFIG}{topic}", userdata[topic], retain=True)
    print(f"   - Config: {userdata}")
    print(f"   - IP: {PROXY_NODE_ADDRESS}")
  else:
    logging.error("ConnectionError: MQTT connection failed.")


def save_to_influx(payload_dict):

  INFLUX_CLIENT = InfluxDBClient3(
    host=INFLUX_CONFIG.get("IDB_HOST", ""), 
    token=INFLUX_CONFIG.get("IDB_TOKEN", ""), 
    org=INFLUX_CONFIG.get("IDB_ORG", ""),
    database=INFLUX_CONFIG.get("IDB_BUCKET", "")
  )

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
    
    data_forecast = {'node_id': node_id}
    lower_bound = 0
    for field_name in ['temperature', 'humidity', 'light']:
      if field_name == 'temperature':
          upper_bound = 80
      elif field_name =='humidity':
          upper_bound = 100
      elif field_name == 'light':
          upper_bound = 660
      upper_bound_log = np.log1p(upper_bound)

      with open(WORKING_DIR.joinpath('forecasting_models', f'model_{field_name}.json'), 'r') as fin:
        prophet_model = model_from_json(json.load(fin))
      
      future_data = pd.date_range(
        start=pd.Timestamp.now(tz=None).ceil('5min'), 
        periods=288, 
        freq='5min'
      )
      future_data = pd.DataFrame({'ds': future_data})
      future_data['floor'] = lower_bound
      future_data['cap'] = upper_bound_log
      forecast = prophet_model.predict(future_data)
      forecast['ds'] = forecast['ds'].dt.tz_localize('UTC')

      data_forecast['time'] = forecast['ds']
      data_forecast[field_name] = np.expm1(forecast['yhat']).clip(lower=lower_bound, upper=upper_bound)
    
    df_forecast = pd.DataFrame(data_forecast)
    INFLUX_CLIENT.write(
      record=df_forecast,
      data_frame_measurement_name="sensors_forecast",
      data_frame_timestamp_column='time',
      data_frame_tag_columns=['node_id']
    )

  except Exception as e:
    logging.error(f"InfluxDB saving error: {e}")


class CoAPResource(resource.Resource):

  async def render_put(self, request):
    try:
      payload = request.payload.decode('utf-8')
      data = json.loads(payload)
      logging.info(f"Data received: {data}.")
      save_to_influx(data)
      return aiocoap.Message(code=aiocoap.CHANGED, payload=b"OK CoAP")
    except json.JSONDecodeError:
      logging.error("Decoding Error in the JSON message format.")
      return aiocoap.Message(code=aiocoap.BAD_REQUEST, payload=b"Invalid JSON")
    except Exception as e:
      logging.error(f"Internal Server Error: {e}.")
      return aiocoap.Message(code=aiocoap.INTERNAL_SERVER_ERROR)


async def http_handler(request):

  try:
    data = await request.json()
    logging.info(f"Data received: {data}.")
    save_to_influx(data)
    return web.Response(text="OK HTTP")
  except json.JSONDecodeError:
    logging.error("Decoding Error in the JSON message format.")
    return web.Response(status=400, text="Invalid JSON")
  except Exception as e:
    logging.error(f"Internal Server Error: {e}.")
    return web.Response(status=500, text="Server Error")


async def main(config):

  protocol = config['protocol']
  
  # Client MQTT
  mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, PROXY_CLIENT_ID, userdata=config)
  mqtt_client.on_connect = on_connect
  mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
  mqtt_client.loop_start()

  # CoAP/HTTP handler
  if protocol == 'coap':
    try:
      root = resource.Site()
      root.add_resource([DATA_PATH], CoAPResource())
      await aiocoap.Context.create_server_context(root, bind=(PROXY_NODE_ADDRESS, COAP_PORT))    # listening on coap://<IP>:5683/sensors
    except KeyboardInterrupt as ke:
      logging.error(f"{ke}: CoAP interrupted!")

  elif protocol == 'http':
    try:
      app = web.Application()
      app.router.add_put(f"/{DATA_PATH}", http_handler)
      runner = web.AppRunner(app)
      await runner.setup()
      site = web.TCPSite(runner, PROXY_NODE_ADDRESS, HTTP_PORT)    # listening on http://<IP>:8080/sensors
      await site.start()
    except KeyboardInterrupt as ke:
      logging.error(f"{ke}: HTTP interrupted!")

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

  if args.motion_alert < 10:
    config_data = {
      "protocol": args.protocol,
      "sampling_rate": args.sampling_rate,
      "motion_alert": 15
    }
    logging.error("ConfigError: motion_alert must be greater than 10 seconds. Set to default value of 15 seconds.")
  else:
    config_data = {
      "protocol": args.protocol,
      "sampling_rate": args.sampling_rate,
      "motion_alert": args.motion_alert
    }
  
  try:
    asyncio.run(main(config_data))
  except KeyboardInterrupt as ke:
    logging.error(f"{ke}")
