import logging
import pygame
import math
import yaml
import paho.mqtt.client as mqtt
from influxdb_client_3 import InfluxDBClient3
from pathlib import Path


# Load InfluxDB config
WORKING_DIR = Path.cwd()
CONFIG_PATH = WORKING_DIR.joinpath("influx_config.yaml")
with open(CONFIG_PATH, "r", encoding="utf-8") as _f:
  INFLUX_CONFIG = yaml.safe_load(_f) or {}

BROKER_ADDRESS = "192.168.68.102"
BROKER_PORT = 1883
TOPIC_MOTION = "sensors/motion"
CLIENT_ID = "DisplayNode"

WIDTH, HEIGHT = 800, 600
BG_COLOR = (0, 0, 0)

art_state = {
    "active": False,
    "temperature": 20.0,
    "humidity": 50.0,
    "light": 330
}

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s')


def fetch_sensor_data():
    try:
        INFLUX_CLIENT = InfluxDBClient3(
            host=INFLUX_CONFIG.get("IDB_HOST", ""), 
            token=INFLUX_CONFIG.get("IDB_TOKEN", ""), 
            org=INFLUX_CONFIG.get("IDB_ORG", ""),
            database=INFLUX_CONFIG.get("IDB_BUCKET", "")
        )
        query = 'SELECT "temperature", "humidity", "light" FROM "sensors" WHERE "node_id" = \'smart_art_1\' ORDER BY time DESC LIMIT 1'
        df_values = INFLUX_CLIENT.query(query, language='sql').to_pandas()

        return {
            'temperature': df_values['temperature'].values[0],
            'humidity': df_values['humidity'].values[0],
            'light': df_values['light'].values[0]
        }
    except Exception as e:
        logging.error(f" Query Error: {e}")
        return {'temperature': 20.0, 'humidity': 50.0, 'light': 330}    # default values
    

def map_val(value, in_min, in_max, out_min, out_max):
    val = max(in_min, min(value, in_max))
    return (val - in_min) * (out_max - out_min) // (in_max - in_min) + out_min


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        client.subscribe(TOPIC_MOTION, qos=1)
        logging.info(f"Subscribed: {TOPIC_MOTION}")
    else:
        logging.error(f"MQTT Connection Error: {rc}")


def on_message(client, userdata, msg):

    payload_str = msg.payload.decode('utf-8')
    motion_val = int(payload_str)

    if motion_val > 0:
        env_data = fetch_sensor_data()
        art_state.update({
            "temperature": env_data["temperature"],
            "humidity": env_data["humidity"],
            "light": env_data["light"],
            "active": True
        })
    else:
        art_state["active"] = False


def draw_generative_art(screen, ticks):

    center = (WIDTH // 2, HEIGHT // 2)
    scale_freq = 0.025

    t = art_state["temperature"]
    r = int(map_val(t, 15, 25, 0, 255))
    g = int(map_val(t, 15, 25, 255, 0))
    color = (r, g, 0)

    l = art_state["humidity"]
    radius_base = map_val(l, 0, 100, 25, 150)

    h = art_state["light"]
    speed_factor = map_val(h, 0, 100, 0.5, 5.0)

    # --- EYE SHAPE --- #
    num_lines = 72
    for i in range(num_lines):
        angle = math.radians((360 / num_lines) * i + (ticks * speed_factor))
        end_x = center[0] + math.cos(angle) * radius_base * 6
        end_y = center[1] + math.sin(angle) * radius_base * 6
        thickness = int(2 + math.sin(ticks * scale_freq) * 2)
        pygame.draw.line(screen, (100, 100, 255), center, (end_x, end_y), thickness)

    # Contour
    eye_width = radius_base * 4
    eye_height = radius_base * 2 * math.sin(ticks * scale_freq)
    rect_x = center[0] - (eye_width // 2)
    rect_y = center[1] - (eye_height // 2)
    eye_rect = pygame.Rect(rect_x, rect_y, int(eye_width), int(eye_height))
    pygame.draw.ellipse(screen, (255, 255, 255), eye_rect)

    # Iris
    iris_width = radius_base * 2
    iris_height = radius_base * 2 * math.sin(ticks * scale_freq)
    rect_x = center[0] - (iris_width // 2)
    rect_y = center[1] - (iris_height // 2)
    iris_rect = pygame.Rect(rect_x, rect_y, int(iris_width), int(iris_height))
    pygame.draw.ellipse(screen, color, iris_rect)

    iris_width = radius_base * 2
    iris_height = radius_base * 2 * math.sin(ticks * scale_freq)
    rect_x = center[0] - (iris_width // 2)
    rect_y = center[1] - (iris_height // 2)
    iris_rect = pygame.Rect(rect_x, rect_y, int(iris_width), int(iris_height))
    pygame.draw.ellipse(screen, (100, 100, 255), iris_rect, 5)
    pygame.draw.ellipse(screen, BG_COLOR, iris_rect, 3)

    # Pupil
    pupil_perc = 0.7
    pupil_width = radius_base * pupil_perc
    pupil_height = radius_base * pupil_perc * math.sin(ticks * scale_freq)
    rect_x = center[0] - (pupil_width // 2)
    rect_y = center[1] - (pupil_height // 2)
    pupil_rect = pygame.Rect(rect_x, rect_y, int(pupil_width), int(pupil_height))
    pygame.draw.ellipse(screen, (10, 10, 10), pupil_rect)


if __name__ == "__main__":
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, CLIENT_ID)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER_ADDRESS, BROKER_PORT, 60)
    client.loop_start()

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    running = True
    ticks = 0 
    
    try:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            screen.fill(BG_COLOR)

            if art_state["active"]:
                draw_generative_art(screen, ticks)
                ticks += 1
                if ticks == 28400:  # to avoid overflow and guarantee sinusoidal continuity through the reset loop
                    ticks = 0
            else:
                ticks = 0

            pygame.display.flip()
            clock.tick(int(art_state["humidity"]))

    except KeyboardInterrupt:
        client.loop_stop()
        client.disconnect()
        pygame.quit()