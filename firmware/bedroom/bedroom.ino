#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include "../config.h"

constexpr int DHT_PIN = 4, DHT_TYPE = DHT11, FAN_PIN = 26, LED_PIN = 25;
constexpr float FAN_THRESHOLD_C = 30.0;
const char *BASE = "smarthouse/bedroom/";
WiFiClient wifiClient; PubSubClient mqtt(wifiClient); DHT dht(DHT_PIN, DHT_TYPE);
bool fan = false, led = false, fanManual = false, ledManual = false;
unsigned long lastRead = 0;

void publishState(const char *device, const char *state) { char t[72]; snprintf(t, sizeof(t), "%s%s/state", BASE, device); mqtt.publish(t, state, true); }
void publishBool(const char *device, bool value) { publishState(device, value ? "ON" : "OFF"); }
void setFan(bool on) { fan = on; digitalWrite(FAN_PIN, on); publishBool("fan", on); }
void setLed(bool on) { led = on; digitalWrite(LED_PIN, on); publishBool("led", on); }
void onMessage(char *topic, byte *payload, unsigned int length) {
  String v; for (unsigned int i=0; i<length; i++) v += (char)payload[i]; String t(topic);
  if (t == "smarthouse/bedroom/fan/set") { if (v == "AUTO") fanManual = false; else { fanManual = true; setFan(v == "ON"); } }
  if (t == "smarthouse/bedroom/led/set") { if (v == "AUTO") ledManual = false; else { ledManual = true; setLed(v == "ON"); } }
}
void connectMqtt() { while (!mqtt.connected()) { if (mqtt.connect("bedroom", MQTT_USER, MQTT_PASSWORD)) { mqtt.subscribe("smarthouse/bedroom/fan/set"); mqtt.subscribe("smarthouse/bedroom/led/set"); publishBool("fan", fan); publishBool("led", led); } else delay(3000); } }
void setup() { pinMode(FAN_PIN, OUTPUT); pinMode(LED_PIN, OUTPUT); dht.begin(); WiFi.begin(WIFI_SSID, WIFI_PASSWORD); while(WiFi.status()!=WL_CONNECTED) delay(500); mqtt.setServer(MQTT_HOST, MQTT_PORT); mqtt.setCallback(onMessage); }
void loop() { if(!mqtt.connected()) connectMqtt(); mqtt.loop(); if(millis()-lastRead >= 5000) { lastRead=millis(); float temp=dht.readTemperature(), humidity=dht.readHumidity(); if(!isnan(temp) && !isnan(humidity)) { if(!fanManual) setFan(temp >= FAN_THRESHOLD_C); char p[80]; snprintf(p,sizeof(p),"{\"temp\":%.1f,\"humidity\":%.1f}",temp,humidity); publishState("dht11",p); } } }
