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

// WiFi parameters
#define WIFI_SSID "Vodafone-C00630078"
#define WIFI_PASSWORD "CT7r3HbmACF4McXz"

// MQTT parameters
#define BROKER_ADDRESS "192.168.1.7"     //CAMBIAAA
#define BROKER_PORT 1883                 //CAMBIAAA
#define MQTT_SUBSCRIBE_QOS 1
#define TOPIC_MOTION "sensors/motion"
#define TOPIC_PROTOCOL "config/protocol"
#define TOPIC_SAMPLING_RATE "config/sampling_rate"
#define TOPIC_MOTION_ALERT "config/motion_alert"

#endif