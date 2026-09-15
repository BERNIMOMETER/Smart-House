#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <SPI.h>
#include <MFRC522.h>
#include <ESP32Servo.h>
#include "../config.h"

// ESP32-S3 pin map for the single-controller installation.
// All pins below (1,2,4-18) are outside the strapping (0/3/45/46), native-USB
// (19/20), and octal-flash/PSRAM (26-37) ranges, so they're safe on standard
// ESP32-S3-DevKitC-1 / WROOM-1 boards.
constexpr int DHT_PIN = 4;
constexpr int BEDROOM_FAN_PIN = 5;
constexpr int BEDROOM_LED_PIN = 6;
constexpr int MQ2_PIN = 1;   // ADC1_CH0 -- see voltage-divider note below
constexpr int KITCHEN_FAN_PIN = 7;
constexpr int LIVING_PIR_PIN = 8;
constexpr int LIVING_LED_PIN = 9;
constexpr int BUZZER_PIN = 10;
constexpr int LDR_PIN = 2;   // ADC1_CH1 -- see voltage-divider note below
constexpr int OUTDOOR_LED_PIN = 11;
constexpr int ENTRANCE_PIR_PIN = 12;
constexpr int SERVO_PIN = 13;
constexpr int RFID_SS_PIN = 14;
constexpr int RFID_RST_PIN = 15;
constexpr int RFID_MISO_PIN = 16;
constexpr int RFID_MOSI_PIN = 17;
constexpr int RFID_SCK_PIN = 18;

constexpr int DHT_TYPE = DHT11;
constexpr float FAN_THRESHOLD_C = 30.0;

// --- MQ2 / LDR thresholds with hysteresis ---
// NOTE: if you add a voltage divider on the MQ2 AO line (needed if your
// module's analog output can exceed ~3.3V), these raw ADC values will shift
// and MUST be recalibrated against your actual divider ratio.
constexpr int SMOKE_THRESHOLD_ON = 1800;   // raw reading that trips the alarm
constexpr int SMOKE_THRESHOLD_OFF = 1650;  // must drop below this to clear it
constexpr int LDR_DARK_ON = 1450;          // darker than this turns the light on
constexpr int LDR_DARK_OFF = 1600;         // brighter than this turns it back off

constexpr int DOOR_OPEN_ANGLE = 90;
constexpr int DOOR_CLOSED_ANGLE = 0;
constexpr unsigned long DOOR_OPEN_MS = 4000;
constexpr unsigned long SENSOR_INTERVAL_MS = 5000;
constexpr unsigned long REPORT_INTERVAL_MS = 10000;
constexpr unsigned long MQTT_RETRY_INTERVAL_MS = 3000;
constexpr unsigned long WIFI_RETRY_INTERVAL_MS = 5000;
constexpr unsigned long NFC_DEBOUNCE_MS = 3000;

// Set to 1 if you want a tripped motion alarm to clear itself the moment the
// PIR goes back to LOW, instead of staying latched until security mode is
// toggled off/on. Defaults to the original latching behavior.
#define ALARM_AUTO_CLEAR 0

// Replace this value with the lowercase hexadecimal UID of the authorised tag.
const char *AUTHORISED_UID = "REPLACE_WITH_AUTHORISED_UID";

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
DHT dht(DHT_PIN, DHT_TYPE);
MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN);
Servo door;

bool securityMode = false;
bool smokeAlarm = false;
bool livingMotionAlarm = false;
bool entranceMotionAlarm = false;
bool bedroomFan = false;
bool bedroomFanManual = false;
bool bedroomLed = false;
bool bedroomLedManual = false;
bool livingLed = false;
bool outdoorLed = false;
bool outdoorLedManual = false;
bool buzzer = false;
unsigned long doorClosesAt = 0;
unsigned long lastSensorRead = 0;
unsigned long lastReport = 0;
unsigned long lastMqttAttempt = 0;
unsigned long lastWifiAttempt = 0;
String lastNfcUid = "";
unsigned long lastNfcMillis = 0;

void publishState(const char *zone, const char *device, const char *value, bool retained = true) {
  char topic[96];
  snprintf(topic, sizeof(topic), "smarthouse/%s/%s/state", zone, device);
  mqtt.publish(topic, value, retained);
}

void publishBool(const char *zone, const char *device, bool value) {
  publishState(zone, device, value ? "ON" : "OFF");
}

void setBuzzer() {
  bool shouldBuzz = smokeAlarm || livingMotionAlarm || entranceMotionAlarm;
  if (shouldBuzz == buzzer) return;
  buzzer = shouldBuzz;
  digitalWrite(BUZZER_PIN, buzzer ? HIGH : LOW);
  publishBool("kitchen_living", "buzzer", buzzer);
}

void setBedroomFan(bool on) {
  bedroomFan = on;
  digitalWrite(BEDROOM_FAN_PIN, on ? HIGH : LOW);
  publishBool("bedroom", "fan", on);
}

void setBedroomLed(bool on) {
  bedroomLed = on;
  digitalWrite(BEDROOM_LED_PIN, on ? HIGH : LOW);
  publishBool("bedroom", "led", on);
}

void setLivingLed(bool on) {
  livingLed = on;
  digitalWrite(LIVING_LED_PIN, on ? HIGH : LOW);
  publishBool("kitchen_living", "living_led", on);
}

void setOutdoorLed(bool on) {
  outdoorLed = on;
  digitalWrite(OUTDOOR_LED_PIN, on ? HIGH : LOW);
  publishBool("entrance", "outdoor_led", on);
}

void openDoor() {
  door.write(DOOR_OPEN_ANGLE);
  doorClosesAt = millis() + DOOR_OPEN_MS;
  publishState("entrance", "door", "OPEN");
}

void handleSecurityMode(const String &value) {
  securityMode = value == "ON";
  if (!securityMode) {
    livingMotionAlarm = false;
    entranceMotionAlarm = false;
    publishBool("kitchen_living", "pir", false);
    publishBool("entrance", "pir", false);
    publishBool("entrance", "alarm", false);
    setBuzzer();
  }
  publishState("system", "security_mode", securityMode ? "ON" : "OFF");
}

void onMessage(char *topic, byte *payload, unsigned int length) {
  String value;
  for (unsigned int index = 0; index < length; ++index) value += (char)payload[index];
  String topicName(topic);

  if (topicName == "smarthouse/system/security_mode/set") {
    handleSecurityMode(value);
  } else if (topicName == "smarthouse/bedroom/fan/set") {
    if (value == "AUTO") bedroomFanManual = false;
    else { bedroomFanManual = true; setBedroomFan(value == "ON"); }
  } else if (topicName == "smarthouse/bedroom/led/set") {
    if (value == "AUTO") bedroomLedManual = false;
    else { bedroomLedManual = true; setBedroomLed(value == "ON"); }
  } else if (topicName == "smarthouse/kitchen_living/living_led/set") {
    setLivingLed(value == "ON");
  } else if (topicName == "smarthouse/entrance/outdoor_led/set") {
    if (value == "AUTO") outdoorLedManual = false;
    else { outdoorLedManual = true; setOutdoorLed(value == "ON"); }
  } else if (topicName == "smarthouse/entrance/door/set" && value == "OPEN") {
    openDoor();
  }
}

// Non-blocking MQTT (re)connect. Returning early instead of looping with
// delay() keeps readMotion()/checkNfc()/door-close timing alive during an
// outage instead of freezing the whole controller.
void maintainMqtt() {
  if (mqtt.connected()) return;
  unsigned long now = millis();
  if (now - lastMqttAttempt < MQTT_RETRY_INTERVAL_MS) return;
  lastMqttAttempt = now;

  if (mqtt.connect("smarthouse-esp32-s3", MQTT_USER, MQTT_PASSWORD)) {
    mqtt.subscribe("smarthouse/system/security_mode/set");
    mqtt.subscribe("smarthouse/bedroom/fan/set");
    mqtt.subscribe("smarthouse/bedroom/led/set");
    mqtt.subscribe("smarthouse/kitchen_living/living_led/set");
    mqtt.subscribe("smarthouse/entrance/outdoor_led/set");
    mqtt.subscribe("smarthouse/entrance/door/set");
    publishState("system", "security_mode", securityMode ? "ON" : "OFF");
    publishBool("bedroom", "fan", bedroomFan);
    publishBool("bedroom", "led", bedroomLed);
    publishBool("kitchen_living", "living_led", livingLed);
    publishBool("kitchen_living", "fan", smokeAlarm);
    publishBool("entrance", "outdoor_led", outdoorLed);
    publishBool("kitchen_living", "buzzer", buzzer);
  }
}

// Wi-Fi drops don't fix themselves -- without this, a lost connection left
// maintainMqtt() retrying forever against a radio that was never reconnected.
void maintainWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  unsigned long now = millis();
  if (now - lastWifiAttempt < WIFI_RETRY_INTERVAL_MS) return;
  lastWifiAttempt = now;
  WiFi.reconnect();
}

bool allowedTag(const String &uid) {
  return uid.equalsIgnoreCase(AUTHORISED_UID);
}

void checkNfc() {
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;
  String uid;
  for (byte index = 0; index < rfid.uid.size; ++index) {
    if (rfid.uid.uidByte[index] < 16) uid += "0";
    uid += String(rfid.uid.uidByte[index], HEX);
  }

  // Debounce: MIFARE tags can be re-read several times in one tap if they
  // linger near the reader, which used to fire openDoor()/publish repeatedly.
  unsigned long now = millis();
  if (uid == lastNfcUid && (now - lastNfcMillis) < NFC_DEBOUNCE_MS) {
    rfid.PICC_HaltA();
    return;
  }
  lastNfcUid = uid;
  lastNfcMillis = now;

  bool granted = allowedTag(uid);
  if (granted) {
    openDoor();
    // A valid entry should silence an entrance alarm that was tripped by the
    // same person walking up to the door -- previously the buzzer kept going
    // after a fully legitimate entry until security mode was toggled off.
    if (entranceMotionAlarm) {
      entranceMotionAlarm = false;
      publishBool("entrance", "pir", false);
      publishBool("entrance", "alarm", false);
      setBuzzer();
    }
  }
  char payload[140];
  snprintf(payload, sizeof(payload), "{\"tag_id\":\"%s\",\"granted\":%s}", uid.c_str(), granted ? "true" : "false");
  publishState("entrance", "nfc", payload, false);
  rfid.PICC_HaltA();
}

void readSensors() {
  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();
  if (!isnan(temperature) && !isnan(humidity)) {
    if (!bedroomFanManual) setBedroomFan(temperature >= FAN_THRESHOLD_C);
    char payload[80];
    snprintf(payload, sizeof(payload), "{\"temp\":%.1f,\"humidity\":%.1f}", temperature, humidity);
    publishState("bedroom", "dht11", payload);
  }

  // Hysteresis prevents rapid on/off chatter when the raw reading sits right
  // at the boundary -- turning on needs to cross the upper bound, turning
  // off needs to drop below the lower one.
  int smokeRaw = analogRead(MQ2_PIN);
  bool smokeDetected = smokeAlarm ? (smokeRaw >= SMOKE_THRESHOLD_OFF) : (smokeRaw >= SMOKE_THRESHOLD_ON);
  if (smokeDetected != smokeAlarm) {
    smokeAlarm = smokeDetected;
    digitalWrite(KITCHEN_FAN_PIN, smokeAlarm ? HIGH : LOW);
    publishBool("kitchen_living", "mq2", smokeAlarm);
    publishBool("kitchen_living", "fan", smokeAlarm);
    setBuzzer();
  }

  int lightRaw = analogRead(LDR_PIN);
  bool wantOutdoorLed = outdoorLed ? (lightRaw < LDR_DARK_OFF) : (lightRaw < LDR_DARK_ON);
  if (!outdoorLedManual && wantOutdoorLed != outdoorLed) {
    setOutdoorLed(wantOutdoorLed);
  }

  if (millis() - lastReport >= REPORT_INTERVAL_MS) {
    lastReport = millis();
    char smokePayload[64];
    snprintf(smokePayload, sizeof(smokePayload), "{\"raw\":%d,\"state\":\"%s\"}", smokeRaw, smokeAlarm ? "ON" : "OFF");
    publishState("kitchen_living", "mq2", smokePayload);
    char lightPayload[32];
    snprintf(lightPayload, sizeof(lightPayload), "{\"raw\":%d}", lightRaw);
    publishState("entrance", "ldr", lightPayload);
  }
}

void readMotion() {
  if (!securityMode) return;

  bool livingHigh = digitalRead(LIVING_PIR_PIN) == HIGH;
  if (livingHigh && !livingMotionAlarm) {
    livingMotionAlarm = true;
    publishBool("kitchen_living", "pir", true);
    setBuzzer();
  }
#if ALARM_AUTO_CLEAR
  else if (!livingHigh && livingMotionAlarm) {
    livingMotionAlarm = false;
    publishBool("kitchen_living", "pir", false);
    setBuzzer();
  }
#endif

  bool entranceHigh = digitalRead(ENTRANCE_PIR_PIN) == HIGH;
  if (entranceHigh && !entranceMotionAlarm) {
    entranceMotionAlarm = true;
    publishBool("entrance", "pir", true);
    publishBool("entrance", "alarm", true);
    setBuzzer();
  }
#if ALARM_AUTO_CLEAR
  else if (!entranceHigh && entranceMotionAlarm) {
    entranceMotionAlarm = false;
    publishBool("entrance", "pir", false);
    publishBool("entrance", "alarm", false);
    setBuzzer();
  }
#endif
}

void setup() {
  Serial.begin(115200);
  pinMode(BEDROOM_FAN_PIN, OUTPUT);
  pinMode(BEDROOM_LED_PIN, OUTPUT);
  pinMode(KITCHEN_FAN_PIN, OUTPUT);
  pinMode(LIVING_PIR_PIN, INPUT);
  pinMode(LIVING_LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(OUTDOOR_LED_PIN, OUTPUT);
  pinMode(ENTRANCE_PIR_PIN, INPUT);
  pinMode(MQ2_PIN, INPUT);
  pinMode(LDR_PIN, INPUT);
  digitalWrite(BUZZER_PIN, LOW);
  dht.begin();
  door.setPeriodHertz(50);
  door.attach(SERVO_PIN);
  door.write(DOOR_CLOSED_ANGLE);
  SPI.begin(RFID_SCK_PIN, RFID_MISO_PIN, RFID_MOSI_PIN, RFID_SS_PIN);
  rfid.PCD_Init();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) delay(500);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMessage);
}

void loop() {
  maintainWifi();
  if (WiFi.status() == WL_CONNECTED) {
    maintainMqtt();
    mqtt.loop();
  }

  // millis()-safe comparison: a plain "millis() >= doorClosesAt" breaks for
  // the one wraparound window every ~49 days of uptime.
  if (doorClosesAt && (long)(millis() - doorClosesAt) >= 0) {
    door.write(DOOR_CLOSED_ANGLE);
    doorClosesAt = 0;
    publishState("entrance", "door", "CLOSED");
  }
  readMotion();
  checkNfc();
  if (millis() - lastSensorRead >= SENSOR_INTERVAL_MS) {
    lastSensorRead = millis();
    readSensors();
  }
}
