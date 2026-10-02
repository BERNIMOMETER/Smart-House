# Single ESP32-S3 firmware

`smarthouse/smarthouse.ino` combines the bedroom, kitchen/living, and entrance sketches for one ESP32-S3. It keeps the existing MQTT topic contract used by Django, but all sensors, actuators, NFC, and alarm logic now run in one `setup()`/`loop()` pair.

## Arduino setup

1. Copy `config.example.h` to the ignored `smarthouse/config.h` in the `firmware` directory. Fill in Wi-Fi, HiveMQ Cloud MQTT settings, and `MQTT_ROOT_CA` there. Keep `MQTT_TLS` set to `1`, use the cluster hostname and port `8883`, and paste the public PEM root CA that validates the cluster into `MQTT_ROOT_CA`. The ESP32 synchronizes its clock through `NTP_SERVER` before validating the certificate, so the Wi-Fi network must allow outbound NTP. Never use `setInsecure()`.
2. Install these libraries through the Arduino Library Manager:
   - PubSubClient
   - DHT sensor library
   - MFRC522
   - ESP32Servo
3. Open `smarthouse/smarthouse.ino` in Arduino IDE.
4. Select the correct ESP32-S3 board and port.
5. Upload the sketch. NFC authorization is managed from the website: scan a card, open the dashboard, and select **Authorize card** for its UID. The decision is sent to the ESP32 over a retained MQTT command and survives reconnects.
6. Use **Revoke** in the dashboard to remove a card from the controller.

Upload only the combined sketch for this installation.

## Default pin map

| Device | GPIO |
| --- | ---: |
| Bedroom DHT11 data | 4 |
| Relay CH4: bedroom fan (on/off only) | 5 |
| Relay CH1: bedroom LED | 6 |
| MQ2 analog output | 1 |
| Relay CH2: kitchen/living LED | 9 |
| Shared buzzer | 10 |
| Relay CH3: outdoor LED | 11 |
| Entrance PIR | 12 |
| Door servo signal | 13 |
| MFRC522 SDA/SS | 14 |
| MFRC522 RST | 15 |
| MFRC522 MISO | 16 |
| MFRC522 MOSI | 17 |
| MFRC522 SCK | 18 |

The relay pin constants are at the top of the sketch. Most relay boards are active LOW; `RELAY_ACTIVE_LEVEL` in `smarthouse/config.h` selects the installed board's polarity. Change pins to match physical wiring before uploading. Power the MQ2, servo, and buzzer from suitable supplies; share ground with the ESP32-S3 and do not feed a 5 V signal into an ESP32 input.

## Runtime behavior

- The bedroom fan follows DHT11 temperature at 30 C or above until the website sends `ON` or `OFF`; `AUTO` releases that override.
- MQ2 smoke turns on the shared buzzer. Smoke remains an active alarm independently of Security Mode.
- The entrance PIR latches its security alarm while Security Mode is on. Turning Security Mode off clears the motion alarm and the buzzer it caused.
- The outdoor light is controlled by website `ON`/`OFF` commands only.
- The door opens for four seconds from a valid NFC tag or the remote `OPEN` command.
- NFC reads publish an event and are recorded by the Django MQTT bridge.

## MQTT topics

Commands are received on the existing `.../set` topics:

```text
smarthouse/system/security_mode/set       ON | OFF
smarthouse/bedroom/fan/set                ON | OFF | AUTO
smarthouse/bedroom/led/set                ON | OFF
smarthouse/kitchen_living/living_led/set  ON | OFF
smarthouse/entrance/outdoor_led/set       ON | OFF
smarthouse/entrance/door/set              OPEN (not retained)
```

States are published under the matching `.../state` topics. Sensor readings use JSON, for example `{"temp":30.0,"humidity":65.0}`. Fan reports include both its relay state and operating mode, for example `{"state":"ON","mode":"AUTO"}`. The sketch uses the `MQTT_CLIENT_ID` defined in `smarthouse/config.h`, so only one copy of this combined sketch should be connected with that client ID. `MQTT_TOPIC_PREFIX` defaults to `smarthouse` and must match Django's `MQTT_TOPIC_PREFIX`.
