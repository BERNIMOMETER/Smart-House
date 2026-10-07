#include <WiFi.h>

#define WIFI_SSID "T.I.P.ian Student"
#define WIFI_PASSWORD ""
#define MQTT_HOST "a183c6cd0d574f5ca102dee94fb9c29c.s1.eu.hivemq.cloud"
#define MQTT_PORT 8883
#define MQTT_USER "wadudumzaku"
#define MQTT_PASSWORD "wadudumzaku"
#define MQTT_CLIENT_ID "smarthouse-esp32-s3"
#define MQTT_TOPIC_PREFIX "smarthouse"  
#define RELAY_ACTIVE_LEVEL LOW

#define MQTT_TLS 1

#if MQTT_TLS
#define NTP_SERVER "pool.ntp.org"
#define NTP_SERVER_BACKUP_1 "time.nist.gov"
#define NTP_SERVER_BACKUP_2 "time.google.com"
static const char MQTT_ROOT_CA[] = R"EOF(
-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw
TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh
cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4
WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu
ZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY
MTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54rVygc
h77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+
0TM8ukj13Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6U
A5/TR5d8mUgjU+g4rk8Kb4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+sW
T8KOEUt+zwvo/7V3LvSye0rgTBIlDHCNAymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qyH
B5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ4Q7e2RCOFvu396j3x+UC
B5iPNgiV5+I3lg02dZ77DnKxHZu8A/lJBdiB3QW0KtZB6awBdpUKD9jf1b0SHzUv
KBds0pjBqAlkd25HN7rOrFleaJ1/ctaJxQZBKT5ZPt0m9STJEadao0xAH0ahmbWn
OlFuhjuefXKnEgV4We0+UXgVCwOPjdAvBbI+e0ocS3MFEvzG6uBQE3xDk3SzynTn
jh8BCNAw1FtxNrQHusEwMFxIt4I7mKZ9YIqioymCzLq9gwQbooMDQaHWBfEbwrbw
qHyGO0aoSCqI3Haadr8faqU9GY/rOPNk3sgrDQoo//fb4hVC1CLQJ13hef4Y53CI
rU7m2Ys6xt0nUW7/vGT1M0NPAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNV
HRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY9umbbjANBgkq
hkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V9lZL
ubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk6ZGQ
3BebYhtF8GaV0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcOj/KK
NFtY2PwByVS5uCbMiogziUwthDyC3+6WVwW6LLv3xLfHTjuCvjHIInNzktHCgKQ5
ORAzI4JMPJ+GslWYHb4phowim57iaztXOoJwTdwJx4nLCgdNbOhdjsnvzqvHu7Ur
TkXWStAmzOVyyghqpZXjFaH3pO3JLF+l+/+sKAIuvtd7u+Nxe5AW0wdeRlN8NwdC
jNPElpzVmbUq4JUagEiuTDkHzsxHpFKVK7q4+63SM1N95R1NbdWhscdCb+ZAJzVc
oyi3B43njTOQ5yOf+1CceWxG1bQVs5ZufpsMljq4Ui0/1lvh+wjChP4kqKOJ2qxq
4RgqsahDYVvTH9w7jXbyLeiNdd8XM2w9U/t7y0Ff/9yi0GE44Za4rF2LN9d11TPA
mRGunUHBcnWEvgJBQl9nJEiU0Zsnvgc/ubhPgXRR4Xq37Z0j4r7g1SgEEzwxA57d
emyPxgcYxn/eR44/KJ4EBs+lVDR3veyJm+kXQ99b21/+jh5Xos1AnX5iItreGCc=
-----END CERTIFICATE-----

)EOF";
#endif

#if MQTT_TLS
#include <WiFiClientSecure.h>
#include <time.h>
#endif
#include <PubSubClient.h>
#include <DHT.h>
#include <SPI.h>
#include <MFRC522.h>
#include <ESP32Servo.h>

// ESP32-S3 pin map for the single-controller installation.
// All pins below (1,4-18) are outside the strapping (0/3/45/46), native-USB
// (19/20), and octal-flash/PSRAM (26-37) ranges, so they're safe on standard
// ESP32-S3-DevKitC-1 / WROOM-1 boards.
constexpr int RELAY_CH1_BEDROOM_LED_PIN = 4;
constexpr int RELAY_CH2_LIVING_LED_PIN = 5;
constexpr int RELAY_CH3_OUTDOOR_LED_PIN = 6;
constexpr int RELAY_CH4_FAN_PIN = 7;

constexpr int DHT_PIN = 8;
constexpr int MQ2_PIN = 1;   // ADC1_CH0 -- see voltage-divider note below
constexpr int BUZZER_PIN = 10;
constexpr int ENTRANCE_PIR_PIN = 12;
constexpr int SERVO_PIN = 13;

constexpr int RFID_SS_PIN = 14;
constexpr int RFID_RST_PIN = 15;
constexpr int RFID_MISO_PIN = 16;
constexpr int RFID_MOSI_PIN = 17;
constexpr int RFID_SCK_PIN = 18;

constexpr int DHT_TYPE = DHT11;
constexpr float FAN_THRESHOLD_C = 30.0;
#define SERVO_ENABLED 0

// --- MQ2 thresholds with hysteresis ---
// NOTE: if you add a voltage divider on the MQ2 AO line (needed if your
// module's analog output can exceed ~3.3V), these raw ADC values will shift
// and MUST be recalibrated against your actual divider ratio.
constexpr int SMOKE_THRESHOLD_ON = 1800;   // raw reading that trips the alarm
constexpr int SMOKE_THRESHOLD_OFF = 1650;  // must drop below this to clear it

constexpr int DOOR_OPEN_ANGLE = 90;
constexpr int DOOR_CLOSED_ANGLE = 0;
constexpr unsigned long DOOR_OPEN_MS = 4000;
constexpr unsigned long SENSOR_INTERVAL_MS = 5000;
constexpr unsigned long REPORT_INTERVAL_MS = 10000;
constexpr unsigned long MQTT_RETRY_INTERVAL_MS = 3000;
constexpr unsigned long WIFI_RETRY_INTERVAL_MS = 5000;
constexpr unsigned long NTP_RETRY_INTERVAL_MS = 30000;
constexpr unsigned long NFC_DEBOUNCE_MS = 3000;
constexpr byte MAX_AUTHORISED_UIDS = 32;

#if MQTT_TLS
WiFiClientSecure mqttTransport;
#else
WiFiClient mqttTransport;
#endif
PubSubClient mqtt(mqttTransport);
DHT dht(DHT_PIN, DHT_TYPE);
MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN);
Servo door;

bool securityMode = false;
bool smokeAlarm = false;
bool entranceMotionAlarm = false;
bool bedroomFan = false;
bool bedroomFanManual = false;
bool bedroomLed = false;
bool livingLed = false;
bool outdoorLed = false;
bool buzzer = false;
unsigned long doorClosesAt = 0;
unsigned long lastSensorRead = 0;
unsigned long lastReport = 0;
unsigned long lastMqttAttempt = 0;
unsigned long lastWifiAttempt = 0;
#if MQTT_TLS
unsigned long lastNtpAttempt = 0;
bool tlsClockReady = false;
#endif
String lastNfcUid = "";
unsigned long lastNfcMillis = 0;
String authorisedUids[MAX_AUTHORISED_UIDS];
byte authorisedUidCount = 0;

void publishState(const char *zone, const char *device, const char *value, bool retained = true) {
  char topic[160];
  snprintf(topic, sizeof(topic), "%s/%s/%s/state", MQTT_TOPIC_PREFIX, zone, device);
  mqtt.publish(topic, value, retained);
}

String commandTopic(const char *zone, const char *device) {
  return String(MQTT_TOPIC_PREFIX) + "/" + zone + "/" + device + "/set";
}

#if MQTT_TLS
bool synchroniseClockForTls() {
  configTime(0, 0, NTP_SERVER, NTP_SERVER_BACKUP_1, NTP_SERVER_BACKUP_2);
  struct tm timeInfo;
  for (int attempt = 0; attempt < 10; ++attempt) {
    if (getLocalTime(&timeInfo, 1000)) {
      Serial.println("NTP clock synchronized for TLS");
      return true;
    }
  }
  Serial.println("NTP clock not ready; TLS MQTT is paused until time synchronizes");
  return false;
}

void maintainTlsClock() {
  if (tlsClockReady) return;
  unsigned long now = millis();
  if (now - lastNtpAttempt < NTP_RETRY_INTERVAL_MS) return;
  lastNtpAttempt = now;
  tlsClockReady = synchroniseClockForTls();
}
#endif

void publishBool(const char *zone, const char *device, bool value) {
  publishState(zone, device, value ? "ON" : "OFF");
}

void updateBuzzer() {
  bool shouldBuzz = smokeAlarm || entranceMotionAlarm;
  if (buzzer == shouldBuzz) return;
  buzzer = shouldBuzz;
  digitalWrite(BUZZER_PIN, buzzer ? HIGH : LOW);
  publishBool("kitchen_living", "buzzer", buzzer);
}

void writeRelay(int pin, bool on) {
  digitalWrite(pin, on ? RELAY_ACTIVE_LEVEL : !RELAY_ACTIVE_LEVEL);
}

void publishBedroomFanState() {
  char payload[64];
  snprintf(payload, sizeof(payload), "{\"state\":\"%s\",\"mode\":\"%s\"}",
           bedroomFan ? "ON" : "OFF", bedroomFanManual ? "MANUAL" : "AUTO");
  publishState("bedroom", "fan", payload);
}

void setBedroomFan(bool on) {
  bedroomFan = on;
  writeRelay(RELAY_CH4_FAN_PIN, on);
  publishBedroomFanState();
}

void setBedroomLed(bool on) {
  bedroomLed = on;
  writeRelay(RELAY_CH1_BEDROOM_LED_PIN, on);
  publishBool("bedroom", "led", on);
}

void setLivingLed(bool on) {
  livingLed = on;
  writeRelay(RELAY_CH2_LIVING_LED_PIN, on);
  publishBool("kitchen_living", "living_led", on);
}

void setOutdoorLed(bool on) {
  outdoorLed = on;
  writeRelay(RELAY_CH3_OUTDOOR_LED_PIN, on);
  publishBool("entrance", "outdoor_led", on);
}

void openDoor() {
#if SERVO_ENABLED
  door.write(DOOR_OPEN_ANGLE);
#endif
  doorClosesAt = millis() + DOOR_OPEN_MS;
  publishState("entrance", "door", "OPEN");
}

void handleSecurityMode(const String &value) {
  securityMode = value == "ON";
  if (!securityMode) {
    entranceMotionAlarm = false;
    publishBool("entrance", "pir", false);
    publishBool("entrance", "alarm", false);
    updateBuzzer();
  }
  publishState("system", "security_mode", securityMode ? "ON" : "OFF");
}

void onMessage(char *topic, byte *payload, unsigned int length) {
  Serial.printf("MQTT received: %s -> ", topic);
  String value;
  for (unsigned int index = 0; index < length; ++index) {
    value += (char)payload[index];
  }
  Serial.println(value);
  String topicName(topic);
  String authorizationPrefix = String(MQTT_TOPIC_PREFIX) + "/entrance/nfc/authorized/";
  if (topicName.startsWith(authorizationPrefix) && topicName.endsWith("/set")) {
    String uid = topicName.substring(authorizationPrefix.length(), topicName.length() - 4);
    bool authorised = value == "ON";
    setAuthorisedUid(uid, authorised);
    Serial.printf("NFC card %s: %s\n", uid.c_str(), value == "ON" ? "AUTHORIZED" : "REVOKED");
    char state[180];
    snprintf(state, sizeof(state), "{\"tag_id\":\"%s\",\"state\":\"%s\"}", uid.c_str(), authorised ? "ON" : "OFF");
    publishState("entrance", "nfc_authorized", state);
    return;
  }

  if (topicName == commandTopic("system", "security_mode")) {
    if (value == "ON" || value == "OFF") handleSecurityMode(value);
  } else if (topicName == commandTopic("bedroom", "fan")) {
    if (value == "AUTO") {
      bedroomFanManual = false;
      publishBedroomFanState();
    }
    else if (value == "ON" || value == "OFF") {
      bedroomFanManual = true;
      setBedroomFan(value == "ON");
    }
  } else if (topicName == commandTopic("bedroom", "led")) {
    if (value == "ON" || value == "OFF") setBedroomLed(value == "ON");
  } else if (topicName == commandTopic("kitchen_living", "living_led")) {
    if (value == "ON" || value == "OFF") setLivingLed(value == "ON");
  } else if (topicName == commandTopic("entrance", "outdoor_led")) {
    if (value == "ON" || value == "OFF") setOutdoorLed(value == "ON");
  } else if (topicName == commandTopic("entrance", "door") && value == "OPEN") {
    openDoor();
  }
}

// Rate-limit MQTT reconnects. PubSubClient's connect itself is synchronous,
// so loop() defers attempts while the door is open.
void maintainMqtt() {
  if (mqtt.connected()) return;
#if MQTT_TLS
  if (!tlsClockReady) {
    Serial.println("Waiting for a valid NTP clock before MQTT TLS connection");
    return;
  }
#endif
  unsigned long now = millis();
  if (now - lastMqttAttempt < MQTT_RETRY_INTERVAL_MS) return;
  lastMqttAttempt = now;

  Serial.printf("MQTT connecting to %s:%d, free heap: %u\n", MQTT_HOST, MQTT_PORT, ESP.getFreeHeap());
#if MQTT_TLS
  Serial.println("MQTT TLS enabled; validating certificate against broker root CA.");
#endif
  if (mqtt.connect(MQTT_CLIENT_ID, MQTT_USER, MQTT_PASSWORD)) {
    Serial.println("MQTT connected");
    // Delete any OPEN command retained by older backend versions before subscribing.
    String doorCommand = commandTopic("entrance", "door");
    mqtt.publish(doorCommand.c_str(), "", true);
    const char *topics[] = {
      "system/security_mode",
      "bedroom/fan",
      "bedroom/led",
      "kitchen_living/living_led",
      "entrance/outdoor_led",
      "entrance/door",
    };
    for (const char *topicSuffix : topics) {
      String topic = String(MQTT_TOPIC_PREFIX) + "/" + topicSuffix + "/set";
      bool subscribed = mqtt.subscribe(topic.c_str());
      Serial.printf("MQTT subscribe %s: %s\n", topic.c_str(), subscribed ? "OK" : "FAILED");
    }
    String authorizationTopic = String(MQTT_TOPIC_PREFIX) + "/entrance/nfc/authorized/+/set";
    bool authorizationSubscribed = mqtt.subscribe(authorizationTopic.c_str());
    Serial.printf("MQTT subscribe %s: %s\n", authorizationTopic.c_str(), authorizationSubscribed ? "OK" : "FAILED");
    // Retained commands are the authority after reconnect. Report after they
    // have had time to arrive, rather than briefly overwriting state with boot defaults.
    lastReport = millis();
  } else {
    Serial.printf("MQTT connect failed, state=%d\n", mqtt.state());
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
  for (byte index = 0; index < authorisedUidCount; ++index) {
    if (uid.equalsIgnoreCase(authorisedUids[index])) return true;
  }
  return false;
}

void setAuthorisedUid(const String &uid, bool authorised) {
  for (byte index = 0; index < authorisedUidCount; ++index) {
    if (!authorisedUids[index].equalsIgnoreCase(uid)) continue;
    if (authorised) return;
    authorisedUids[index] = authorisedUids[authorisedUidCount - 1];
    authorisedUids[--authorisedUidCount] = "";
    return;
  }
  if (!authorised || authorisedUidCount >= MAX_AUTHORISED_UIDS) return;
  authorisedUids[authorisedUidCount++] = uid;
}

void checkNfc() {
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;
  String uid;
  for (byte index = 0; index < rfid.uid.size; ++index) {
    if (rfid.uid.uidByte[index] < 16) uid += "0";
    uid += String(rfid.uid.uidByte[index], HEX);
  }
  Serial.printf("RFID scanned UID: %s\n", uid.c_str());

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
  Serial.printf("RFID access: %s\n", granted ? "AUTHORIZED" : "DENIED");
  if (granted) {
    openDoor();
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
    if (!bedroomFanManual && bedroomFan != (temperature >= FAN_THRESHOLD_C)) {
      setBedroomFan(temperature >= FAN_THRESHOLD_C);
    }
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
    publishBool("kitchen_living", "mq2", smokeAlarm);
    updateBuzzer();
  }

  Serial.println("--- Sensor readings ---");
  if (!isnan(temperature) && !isnan(humidity)) {
    Serial.printf("DHT11: %.1f C, %.1f %% RH\n", temperature, humidity);
  } else {
    Serial.println("DHT11: unavailable");
  }
  Serial.printf("MQ2: raw=%d, alarm=%s\n", smokeRaw, smokeAlarm ? "ON" : "OFF");
  Serial.printf(
    "PIR: entrance=%s, security=%s\n",
    digitalRead(ENTRANCE_PIR_PIN) == HIGH ? "HIGH" : "LOW",
    securityMode ? "ON" : "OFF"
  );

  if (millis() - lastReport >= REPORT_INTERVAL_MS) {
    lastReport = millis();
    char smokePayload[64];
    snprintf(smokePayload, sizeof(smokePayload), "{\"raw\":%d,\"state\":\"%s\"}", smokeRaw, smokeAlarm ? "ON" : "OFF");
    publishState("kitchen_living", "mq2", smokePayload);
    publishState("system", "security_mode", securityMode ? "ON" : "OFF");
    publishBedroomFanState();
    publishBool("bedroom", "led", bedroomLed);
    publishBool("kitchen_living", "living_led", livingLed);
    publishBool("entrance", "outdoor_led", outdoorLed);
    publishBool("kitchen_living", "buzzer", buzzer);
    publishBool("entrance", "pir", entranceMotionAlarm);
    publishBool("entrance", "alarm", entranceMotionAlarm);
  }
}

void readMotion() {
  if (!securityMode || entranceMotionAlarm) return;
  if (digitalRead(ENTRANCE_PIR_PIN) == HIGH) {
    entranceMotionAlarm = true;
    publishBool("entrance", "pir", true);
    publishBool("entrance", "alarm", true);
    updateBuzzer();
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("Sketch setup started");
#if MQTT_TLS
  Serial.println("Configuring TLS certificate...");
  mqttTransport.setCACert(MQTT_ROOT_CA);
  Serial.println("TLS certificate configured");
  mqttTransport.setHandshakeTimeout(5);
#endif
  Serial.println("Configuring pins...");
  // Preload the inactive level before switching each relay GPIO to OUTPUT.
  const int relayPins[] = {RELAY_CH1_BEDROOM_LED_PIN, RELAY_CH2_LIVING_LED_PIN,
                           RELAY_CH3_OUTDOOR_LED_PIN, RELAY_CH4_FAN_PIN};
  for (int pin : relayPins) {
    digitalWrite(pin, !RELAY_ACTIVE_LEVEL);
    pinMode(pin, OUTPUT);
  }
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(ENTRANCE_PIR_PIN, INPUT_PULLDOWN);
  pinMode(MQ2_PIN, INPUT);
  digitalWrite(BUZZER_PIN, LOW);
  Serial.println("Starting sensors and actuators...");
  dht.begin();
  Serial.println("DHT initialized");
#if SERVO_ENABLED
  door.setPeriodHertz(50);
  Serial.println("Servo frequency configured");
  door.attach(SERVO_PIN);
  Serial.println("Servo attached");
  door.write(DOOR_CLOSED_ANGLE);
  Serial.println("Servo position set");
#else
  Serial.println("Servo disabled until hardware is connected");
#endif
  SPI.begin(RFID_SCK_PIN, RFID_MISO_PIN, RFID_MOSI_PIN, RFID_SS_PIN);
  Serial.println("SPI initialized");
  rfid.PCD_Init();
  Serial.println("RFID initialized");
  Serial.println("Peripherals initialized");
  Serial.println("Connecting to WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long wifiStartedAt = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - wifiStartedAt < 30000) {
    Serial.printf("WiFi status: %d\n", WiFi.status());
    delay(1000);
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi connection timed out; retrying in loop");
  } else {
    Serial.print("WiFi connected, IP: ");
    Serial.println(WiFi.localIP());
  }
#if MQTT_TLS
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("Starting TLS clock sync before MQTT connect...");
    lastNtpAttempt = millis();
    tlsClockReady = synchroniseClockForTls();
    Serial.println("TLS clock sync attempt finished");
  }
#endif
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setSocketTimeout(3);
  mqtt.setCallback(onMessage);
}

void loop() {
  maintainWifi();
  if (WiFi.status() == WL_CONNECTED) {
#if MQTT_TLS
    if (!doorClosesAt) maintainTlsClock();
#endif
    if (!doorClosesAt) maintainMqtt();
    if (mqtt.connected()) {
      mqtt.loop();
    }
  }

  // millis()-safe comparison: a plain "millis() >= doorClosesAt" breaks for
  // the one wraparound window every ~49 days of uptime.
  if (doorClosesAt && (long)(millis() - doorClosesAt) >= 0) {
#if SERVO_ENABLED
    door.write(DOOR_CLOSED_ANGLE);
#endif
    doorClosesAt = 0;
    publishState("entrance", "door", "CLOSED");
  }
  readMotion();
  checkNfc();
  if (millis() - lastSensorRead >= SENSOR_INTERVAL_MS) {
    lastSensorRead = millis();
    readSensors();
  }
  yield();
}
