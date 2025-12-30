#ifndef _PARAMS_H_
#define _PARAMS_H_

#define DEBUG 1

// Sensing node parameters
#define BOARD_UID 1909
#define BOARD_NAME "sensing_node"
#define DHTPIN 4
#define DHTTYPE DHT22
#define PIRPIN 14
#define LEDPIN 2
#define LIGHTPIN 34

// MQTT parameters
#define SERVER_ADDRESS "192.168.68.103"
#define MQTT_PORT 1883
#define COAP_PORT 5683
#define HTTP_PORT 8080
#define DATA_PATH "sensors"
#define MQTT_SUBSCRIBE_QOS 1
#define TOPIC_MOTION "sensors/motion"
#define TOPIC_PROTOCOL "config/protocol"
#define TOPIC_SAMPLING_RATE "config/sampling_rate"
#define TOPIC_MOTION_ALERT "config/motion_alert"

#endif