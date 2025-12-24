#include "params.h"
#include "wifi_config.h"
#include "DHT.h"
#include <WiFi.h>
#include <PubSubClient.h>
#include <WiFiUdp.h>
#include <coap-simple.h>
#include <HTTPClient.h>



// WiFi/Communication Inits
DHT dht(DHTPIN, DHTTYPE);
WiFiClient wifiClient;
PubSubClient client(wifiClient);
WiFiUDP udp;
Coap coap(udp);
HTTPClient http;

// RTOS handles init
TaskHandle_t TaskMotionDetection;

// Config Variables
String protocol = "coap";   // "coap" or "http"
int sampling_rate = 60;
int motion_alert = 15;
unsigned long last_telemetry_time = 0;



void setup() {

  if(DEBUG){
    Serial.begin(115200);
  }
  dht.begin();
  pinMode(LEDPIN, OUTPUT);

  digitalWrite(LEDPIN, HIGH);
  analogSetAttenuation(ADC_11db);
  setupWiFi();
  client.setServer(SERVER_ADDRESS, MQTT_PORT);
  client.setCallback(SetupCallback);
  connectMQTT();
  coap.start();
  digitalWrite(LEDPIN, LOW);

  xTaskCreatePinnedToCore(motion_detection_task, "Motion_Detection", 4096, NULL, 2, &TaskMotionDetection, 1);
}



void loop() {

  if (!client.connected()) {
    digitalWrite(LEDPIN, HIGH);
    connectMQTT();
    digitalWrite(LEDPIN, LOW);
  }
  client.loop(); 

  unsigned long now = millis();
  
  if (now - last_telemetry_time >= (sampling_rate * 1000)) {
    
    last_telemetry_time = now;

    float hum = dht.readHumidity();
    float temp = dht.readTemperature();
    int light = analogRead(LIGHTPIN);
    /*
    float light_V = float(light) * (3.3 / 4095.0);
    float light_muA = (light_V / 10000.0) * 1000000.0;
    float light_lux = light_muA * 2;
    */
    if (isnan(hum) || isnan(temp)) {
      if (DEBUG) Serial.println("Errore lettura DHT!");
      return;
    }

    char payload[100];
    sprintf(payload, "{\"node_id\":\"smart_art_1\",\"temperature\":%.2f,\"humidity\":%.2f,\"light\":%d}", temp, hum, light);

    if (DEBUG) {
      Serial.println(payload);
    }

    if (protocol == "coap") {
      CoAPSend(payload);
    } else if (protocol == "http") {
      HTTPSend(payload);
    }
  }
  
  vTaskDelay(pdMS_TO_TICKS(10)); 
}



void motion_detection_task(void* parameters){

  for (;;){
    int motion = digitalRead(PIRPIN);
    int count = 0;
    bool pub = false;
    if (DEBUG && motion == HIGH){
      Serial.println("Motion detected!");
    }
    while (motion == HIGH){
      count++;
      if (count/2 >= motion_alert && pub == false){
        client.publish(TOPIC_MOTION, "1");
        pub = true;
        if (DEBUG){
          Serial.println("Motion published!");
        }
      }
      motion = digitalRead(PIRPIN);
      vTaskDelay(pdMS_TO_TICKS(500));
    }
    if (count/2 >= motion_alert && motion == LOW){
      client.publish(TOPIC_MOTION, "0");
      pub = false;
      if (DEBUG){
        Serial.println("Motion reset!");
      }
    }
    vTaskDelay(pdMS_TO_TICKS(500));
  }
}



void CoAPSend(const char* payload){

  IPAddress server_IP;
  server_IP.fromString(SERVER_ADDRESS);

  int msg_id = coap.put(server_IP, COAP_PORT, DATA_PATH, payload);
  if (DEBUG){
    if (msg_id){
      Serial.println("CoAP message sent:");
      Serial.print("- ID: ");
      Serial.println(msg_id);
    } else {
      Serial.println("CoAP communication error.");
    }
  }
}



void HTTPSend(const char* payload){

  String server_URL = "http://" + String(SERVER_ADDRESS) + ":" + String(HTTP_PORT) + "/" + String(DATA_PATH);
  http.begin(server_URL);
  http.addHeader("Content-Type", "application/json");
  
  int http_code = http.POST(payload);
  if (DEBUG){
    if (http_code > 0) {
      Serial.println("HTTP message sent:");
      Serial.print("- Code: ");
      Serial.println(http_code);
      Serial.print("- Message: ");
      Serial.println(http.getString().c_str());
    } else {
      Serial.print("HTTP request error: ");
      Serial.println(http.errorToString(http_code).c_str());
    }
  }
  http.end();
}



void SetupCallback(char* topic, byte* message, unsigned int length) {
  
  String msg;
  for(unsigned int i = 0; i < length; i++) {
    msg += (char)message[i];
  }
  if(DEBUG){
    Serial.print("Config changed on ");
    Serial.print(topic);
    Serial.print(": ");
  }

  if(String(topic) == TOPIC_PROTOCOL) {
    if(msg == "coap" || msg == "http"){
      protocol = msg;
      if(DEBUG){
        Serial.println(msg);
      }
    } else {
      if(DEBUG){
        Serial.println("Error! Accepted values: 'coap' or 'http'. ");
        Serial.print("Current ");
        Serial.print(topic);
        Serial.print(": ");
        Serial.println(protocol);
      }
    }
  }

  else if(String(topic) == TOPIC_SAMPLING_RATE) {
    int val = msg.toInt();
    if(val > 0){
      sampling_rate = val;
      if(DEBUG){
        Serial.println(msg);
      }
    } else {
      if(DEBUG){
        Serial.println("Error! Accepted values: int > 0. ");
        Serial.print("Current ");
        Serial.print(topic);
        Serial.print(": ");
        Serial.println(sampling_rate);
      }
    }
  }

  else if(String(topic) == TOPIC_MOTION_ALERT) {
    int val = msg.toInt();
    if(val >= 10){
      motion_alert = val;
      if(DEBUG){
        Serial.println(msg);
      }
    } else {
      if(DEBUG){
        Serial.println("Error! Accepted values: int >= 10. ");
        Serial.print("Current ");
        Serial.print(topic);
        Serial.print(": ");
        Serial.println(motion_alert);
      }
    }
  }
}



void setupWiFi(){

  WiFi.mode(WIFI_STA);          // Station mode (client)
  WiFi.begin(MY_SSID, MY_PASSWORD);

  int count = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(100);
    count++;
    if(count >= 1000){
      if(DEBUG){
        Serial.println("Rebooting...");
      }
      ESP.restart();
    }
  }

  if(DEBUG){
    Serial.println("Sensing Client Node");
    Serial.println("Ready!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
  }
}



void connectMQTT(){

  if(DEBUG){
    Serial.println("Connecting to MQTT...");
  }

  while (!client.connected()) {
    if (client.connect(BOARD_NAME)) {
      client.subscribe(TOPIC_PROTOCOL, MQTT_SUBSCRIBE_QOS);
      client.subscribe(TOPIC_SAMPLING_RATE, MQTT_SUBSCRIBE_QOS);
      client.subscribe(TOPIC_MOTION_ALERT, MQTT_SUBSCRIBE_QOS);
    } else {
      delay(100);
    }
  }

  if(DEBUG){
    Serial.println("Connection established!");
  }
}
