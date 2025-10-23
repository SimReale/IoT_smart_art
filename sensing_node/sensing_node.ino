#include "params.h"
#include "DHT.h"
#include <WiFi.h>
#include <PubSubClient.h>
#include <coap-simple.h>



// Inits
DHT dht(DHTPIN, DHTTYPE);
WiFiClient wifiClient;
PubSubClient client(wifiClient);


// RTOS handles init
TaskHandle_t TaskMotionDetection;

// Config Variables
String protocol = "coap";
int sampling_rate = 300;
int motion_alert = 15;



void setup() {

  if(DEBUG){
    Serial.begin(115200);
  }
  dht.begin();
  pinMode(PIRPIN, INPUT);
  pinMode(LEDPIN, OUTPUT);
  pinMode(LIGHTPIN, INPUT);

  digitalWrite(LEDPIN, HIGH);
  setupWiFi();
  client.setServer(BROKER_ADDRESS, BROKER_PORT);
  client.setCallback(SetupCallback);
  connectMQTT();
  digitalWrite(LEDPIN, LOW);

  xTaskCreatePinnedToCore(motion_detection_task, "Motion_Detection", 2048, NULL, 1, &TaskMotionDetection, 1);
}



void loop() {

  // Keeping MQTT connection alive
  if (!client.connected()) {
    digitalWrite(LEDPIN, HIGH);
    connectMQTT();
    digitalWrite(LEDPIN, LOW);
  }
  client.loop();

  // float h = dht.readHumidity();
  // float t = dht.readTemperature();
  // int lightValue = analogRead(LIGHTPIN);
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



void motion_detection_task(void* parameters){

  for (;;){
    int motion = digitalRead(PIRPIN);
    int count = 0;
    if (DEBUG && motion == HIGH){
      Serial.println("Motion detected!");
    }
    while (motion == HIGH){
      count++;
      if (count/2 >= motion_alert){
        client.publish(TOPIC_MOTION, "1");
        if (DEBUG){
          Serial.println("Motion published!");
        }
      }
      motion = digitalRead(PIRPIN);
      vTaskDelay(pdMS_TO_TICKS(500));
    }
    vTaskDelay(pdMS_TO_TICKS(500));
  }
}



void setupWiFi(){

  WiFi.mode(WIFI_STA);          // Station mode (client)
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

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
