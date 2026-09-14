#include <WiFi.h>
#include <PubSubClient.h>
#include "../config.h"

// Adjust these pins to match the installed hardware.
constexpr int MQ2_PIN = 34, PIR_PIN = 27, FAN_PIN = 26, LIVING_LED_PIN = 25, BUZZER_PIN = 33;
constexpr int SMOKE_THRESHOLD = 1800;
const char *BASE = "smarthouse/kitchen_living/";

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
bool securityMode = false, smokeAlarm = false, livingMotionAlarm = false, entranceMotionAlarm = false;
bool livingLed = false, fan = false;
unsigned long lastReport = 0;

void publishState(const char *device, const char *state, bool retain = true) {
  char topic[96]; snprintf(topic, sizeof(topic), "%s%s/state", BASE, device);
  mqtt.publish(topic, state, retain);
}
void publishBool(const char *device, bool value) { publishState(device, value ? "ON" : "OFF"); }
void setBuzzer() { digitalWrite(BUZZER_PIN, (smokeAlarm || livingMotionAlarm || entranceMotionAlarm) ? HIGH : LOW); publishBool("buzzer", smokeAlarm || livingMotionAlarm || entranceMotionAlarm); }

void onMessage(char *topic, byte *payload, unsigned int length) {
  String value; for (unsigned int i = 0; i < length; ++i) value += (char)payload[i];
  String t(topic);
  if (t == "smarthouse/system/security_mode/set") {
    securityMode = value == "ON";
    if (!securityMode) { livingMotionAlarm = false; entranceMotionAlarm = false; setBuzzer(); }
    publishState("security_mode", securityMode ? "ON" : "OFF");
  } else if (t == "smarthouse/kitchen_living/living_led/set") {
    livingLed = value == "ON"; digitalWrite(LIVING_LED_PIN, livingLed); publishBool("living_led", livingLed);
  } else if (t == "smarthouse/entrance/alarm/state") {
    entranceMotionAlarm = value == "ON" && securityMode; setBuzzer();
  }
}
void connectMqtt() {
  while (!mqtt.connected()) {
    if (mqtt.connect("kitchen-living", MQTT_USER, MQTT_PASSWORD)) {
      mqtt.subscribe("smarthouse/system/security_mode/set"); mqtt.subscribe("smarthouse/kitchen_living/living_led/set");
      mqtt.subscribe("smarthouse/entrance/alarm/state");
      publishBool("living_led", livingLed); publishBool("fan", fan); setBuzzer();
    } else delay(3000);
  }
}
void setup() {
  pinMode(PIR_PIN, INPUT); pinMode(FAN_PIN, OUTPUT); pinMode(LIVING_LED_PIN, OUTPUT); pinMode(BUZZER_PIN, OUTPUT);
  Serial.begin(115200); WiFi.begin(WIFI_SSID, WIFI_PASSWORD); while (WiFi.status() != WL_CONNECTED) delay(500);
  mqtt.setServer(MQTT_HOST, MQTT_PORT); mqtt.setCallback(onMessage);
}
void loop() {
  if (!mqtt.connected()) connectMqtt(); mqtt.loop();
  int smokeRaw = analogRead(MQ2_PIN);
  bool detected = smokeRaw >= SMOKE_THRESHOLD;
  if (detected != smokeAlarm) { smokeAlarm = detected; digitalWrite(FAN_PIN, smokeAlarm); fan = smokeAlarm; publishBool("mq2", smokeAlarm); publishBool("fan", fan); setBuzzer(); }
  // Security alarms latch until Security Mode is turned off. Smoke remains independent.
  if (securityMode && digitalRead(PIR_PIN) == HIGH && !livingMotionAlarm) { livingMotionAlarm = true; publishBool("pir", true); setBuzzer(); }
  if (millis() - lastReport > 10000) { lastReport = millis(); char payload[48]; snprintf(payload, sizeof(payload), "{\"raw\":%d,\"state\":\"%s\"}", smokeRaw, smokeAlarm ? "ON" : "OFF"); publishState("mq2", payload); publishBool("fan", fan); }
}
