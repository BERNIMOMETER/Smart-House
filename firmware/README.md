# Single ESP32-S3 firmware

`smarthouse/smarthouse.ino` combines the bedroom, kitchen/living, and entrance sketches for one ESP32-S3. It keeps the existing MQTT topic contract used by Django, but all sensors, actuators, NFC, and alarm logic now run in one `setup()`/`loop()` pair.

## Arduino setup

1. Open `smarthouse/smarthouse.ino` and fill in the Wi-Fi, HiveMQ Cloud MQTT settings, and `MQTT_ROOT_CA` near the top of the sketch. Keep `MQTT_TLS` set to `1`, use the cluster hostname and port `8883`, and paste the public PEM root CA that validates the cluster into `MQTT_ROOT_CA`. The ESP32 synchronizes its clock through `NTP_SERVER` before validating the certificate, so the Wi-Fi network must allow outbound NTP. Never use `setInsecure()`.
2. Install these libraries through the Arduino Library Manager:
   - PubSubClient
   - DHT sensor library
   - MFRC522
   - ESP32Servo
3. Open `smarthouse/smarthouse.ino` in Arduino IDE.
4. Select the correct ESP32-S3 board and port.
5. Upload the sketch. The ESP32 receives the registered NFC card list from the retained MQTT topic published by the website.
6. Register cards from the dashboard using the UID reported by the NFC reader.

Do not upload the three old sketches for this installation. They are retained as references for the original room-specific wiring.

## Default pin map

| Device | GPIO |
| --- | ---: |
| Bedroom DHT11 data | 4 |
| Bedroom fan | 5 |
| Bedroom LED | 6 |
| MQ2 analog output | 1 |
| Kitchen/living exhaust fan | 7 |
| Living-room PIR | 8 |
| Living-room LED | 9 |
| Shared buzzer | 10 |
| Entrance LDR analog output | 2 |
| Outdoor LED | 11 |
| Entrance PIR | 12 |
| Door servo signal | 13 |
| MFRC522 SDA/SS | 14 |
| MFRC522 RST | 15 |
| MFRC522 MISO | 16 |
| MFRC522 MOSI | 17 |
| MFRC522 SCK | 18 |

The pin constants are at the top of the sketch. Change them to match the physical wiring before uploading. Power the MQ2, servo, and buzzer from suitable supplies; share ground with the ESP32-S3 and do not feed a 5 V signal into an ESP32 input.

## Runtime behavior

- The bedroom fan follows DHT11 temperature at 30 C or above until the website sends `ON` or `OFF`; `AUTO` releases that override.
- MQ2 smoke turns on the exhaust fan and shared buzzer. Smoke remains an active alarm independently of Security Mode.
- Both PIR sensors latch their security alarms while Security Mode is on. Turning Security Mode off clears both motion alarms and the buzzer they caused.
- The LDR controls the outdoor light in AUTO mode. Website `ON`/`OFF` commands override it; `AUTO` releases the override.
- The door opens for four seconds from a valid NFC tag or the remote `OPEN` command.
- NFC reads publish an event and are recorded by the Django MQTT bridge.

## MQTT topics

Commands are received on the existing `.../set` topics:

```text
smarthouse/system/security_mode/set       ON | OFF
smarthouse/bedroom/fan/set                ON | OFF | AUTO
smarthouse/bedroom/led/set                ON | OFF | AUTO
smarthouse/kitchen_living/living_led/set  ON | OFF
smarthouse/entrance/outdoor_led/set       ON | OFF | AUTO
smarthouse/entrance/door/set               OPEN
```

States are published under the matching `.../state` topics. Sensor readings use JSON, for example `{"temp":30.0,"humidity":65.0}`. The sketch uses the `MQTT_CLIENT_ID` defined near the top of the sketch, so only one copy of this combined sketch should be connected with that client ID. `MQTT_TOPIC_PREFIX` defaults to `smarthouse` and must match Django's `MQTT_TOPIC_PREFIX`.
