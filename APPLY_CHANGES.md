# Apply the Smart House hardware and MQTT update

Use this guide to put the updated code on the Raspberry Pi and ESP32-S3. The installation uses one ESP32-S3, a Django web service, a separate MQTT bridge service, Redis for dashboard live updates, and the same HiveMQ Cloud broker on both sides. The full setup reference is in [README.md](README.md), and the firmware reference is in [firmware/README.md](firmware/README.md).

The update changes the [ESP32 sketch](firmware/smarthouse/smarthouse.ino), [MQTT bridge](house/mqtt.py), [Django controls](house/views.py), and [dashboard](house/templates/house/dashboard.html). The old firmware file contained Wi-Fi and MQTT credentials. Rotate them before deployment: update the Pi environment and the ignored ESP32 configuration with the new values. Removing credentials from the current sketch does not erase them from Git history.

## 1. Check the hardware before flashing

The sketch now expects exactly these sensors and actuators:

| Connection | ESP32-S3 GPIO | Behavior |
| --- | ---: | --- |
| MQ2 analog output | 1 | Smoke alert; operates even when Security Mode is off |
| Relay CH1 | 4 | Bedroom light |
| Relay CH2 | 5 | Kitchen/living light |
| Relay CH3 | 6 | Entrance/outdoor light |
| Relay CH4 | 7 | Bedroom fan, on/off only |
| DHT11 data | 8 | Bedroom temperature and humidity |
| Shared buzzer | 10 | Smoke or entrance motion alarm |
| Entrance PIR | 12 | Security alarm |
| Door servo signal | 13 | Opens for four seconds |
| MFRC522 SDA/SS, RST, MISO, MOSI, SCK | 14, 15, 16, 17, 18 | NFC reader |

There is no indoor PIR, LDR, or kitchen exhaust fan in this version. Check the relay board's trigger polarity: `LOW` is the default in the example configuration, but some boards need `HIGH`. Verify the MQ2 analog signal cannot exceed 3.3 V at the ESP32 pin, share ground among the components, and use suitable power supplies for the relay board, servo, buzzer, and sensors. Calibrate the MQ2 thresholds in the sketch for the actual sensor and voltage divider.

## 2. Configure and upload the ESP32 firmware

From the repository root, create the ignored firmware configuration if it does not already exist:

```bash
cp -n firmware/config.example.h firmware/smarthouse/config.h
```

Edit `firmware/smarthouse/config.h` with the Wi-Fi name/password, HiveMQ hostname, port `8883`, MQTT username/password, the public root CA for the cluster, and `RELAY_ACTIVE_LEVEL`. Keep `MQTT_TLS` set to `1` for HiveMQ Cloud. `MQTT_TOPIC_PREFIX` must match Django's value. The board needs network access to NTP so TLS certificate validation has a current clock. Do not commit `config.h`.

In Arduino IDE, install the **PubSubClient**, **DHT sensor library**, **MFRC522**, and **ESP32Servo** libraries. Select the correct ESP32-S3 board and port, open `firmware/smarthouse/smarthouse.ino`, compile, and upload it. Check the serial monitor for Wi-Fi and MQTT connection messages. Test each relay channel against its named load before relying on automatic behavior. The fan should switch fully on or off; it does not use PWM.

## 3. Update the Raspberry Pi services

These commands assume the existing checkout and systemd service names from `README.md`. Back up the live SQLite database before updating code; do not delete or recreate it:

```bash
sudo mkdir -p /var/backups/smarthouse
sudo sqlite3 /opt/smarthouse/db.sqlite3 ".backup '/var/backups/smarthouse/db.sqlite3'"
sudo -u smarthouse git -C /opt/smarthouse pull --ff-only
sudo -u smarthouse /opt/smarthouse/.venv/bin/pip install -r /opt/smarthouse/requirements.txt
```

Check `/etc/smarthouse/smarthouse.env`: `MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `MQTT_TLS`, and `MQTT_TOPIC_PREFIX` must point to the same broker and prefix as the ESP32. Use `MQTT_TLS=1` and port `8883` for HiveMQ Cloud. Preserve the existing Django secret and Cloudflare host settings. If you rotated broker credentials, update them here before restarting.

Run Django checks with the service environment, then restart Redis and both application services:

```bash
sudo systemd-run --wait --collect --property=User=smarthouse --property=Group=smarthouse --property=WorkingDirectory=/opt/smarthouse --property=EnvironmentFile=/etc/smarthouse/smarthouse.env /opt/smarthouse/.venv/bin/python manage.py migrate
sudo systemd-run --wait --collect --property=User=smarthouse --property=Group=smarthouse --property=WorkingDirectory=/opt/smarthouse --property=EnvironmentFile=/etc/smarthouse/smarthouse.env /opt/smarthouse/.venv/bin/python manage.py check
sudo systemd-run --wait --collect --property=User=smarthouse --property=Group=smarthouse --property=WorkingDirectory=/opt/smarthouse --property=EnvironmentFile=/etc/smarthouse/smarthouse.env /opt/smarthouse/.venv/bin/python manage.py test house
sudo systemd-run --wait --collect --property=User=smarthouse --property=Group=smarthouse --property=WorkingDirectory=/opt/smarthouse --property=EnvironmentFile=/etc/smarthouse/smarthouse.env /opt/smarthouse/.venv/bin/python manage.py collectstatic --noinput
sudo systemctl enable --now redis-server
sudo systemctl restart smarthouse-web smarthouse-mqtt
sudo systemctl status smarthouse-web smarthouse-mqtt redis-server
```

Redis is required in development as well as production: it passes ESP32 state reports from the MQTT bridge to dashboard WebSockets. The bridge also clears any `OPEN` door command retained by older code. New door `OPEN` commands are not retained, so reconnecting the ESP32 should not reopen the door.

## 4. Verify the complete flow

1. Open the dashboard and confirm it says **Live updates connected**. If it keeps reconnecting, check Redis, the web service, and the `/ws/updates/` route.
2. Toggle CH1, CH2, and CH3 from the dashboard. Confirm the correct physical light changes and its **Reported** value updates from the ESP32. The dashboard waits for a device report; broker acknowledgement alone does not change reported state.
3. Test bedroom fan `ON`, `OFF`, and `AUTO`. In `AUTO`, the fan switches on at 30 °C or above. The fan state report includes its operating mode.
4. Arm Security Mode, trigger only the entrance PIR, and confirm the shared buzzer sounds. Disarm and confirm the PIR alarm clears. Test MQ2 with a safe method and confirm a smoke alarm still sounds with Security Mode off.
5. Scan an NFC card, authorize it in the dashboard, then scan it again. Confirm the servo opens for four seconds and an audit entry appears. Test the dashboard door button once; reconnecting the ESP32 must not replay that opening.
6. Temporarily make the MQTT broker unavailable. A dashboard command should show an error and release its control within about 12 seconds; the rest of the page should remain usable. Restore the broker and confirm commands and live reports work again.

For service diagnostics, inspect `sudo journalctl -u smarthouse-web -f` and `sudo journalctl -u smarthouse-mqtt -f`. If a command is accepted but no device state arrives, check that the bridge is running and that the Pi and ESP32 use the same broker credentials and topic prefix. The old indoor PIR, LDR, and kitchen fan database rows may remain as historical records, but the updated bridge ignores new reports for them and the dashboard no longer displays them.

## Local development alternative

Create a local `.env` from `.env.example` only if one does not already exist. Set `DJANGO_DEBUG=1`, `DJANGO_SECURE_SSL_REDIRECT=0`, and the MQTT settings to the same broker as the ESP32. Start Redis, then run Django and the bridge in separate terminals:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py test house
.venv/bin/python manage.py runserver
```

```bash
.venv/bin/python manage.py mqtt_bridge
```

If using an isolated local MQTT broker instead of HiveMQ Cloud, explicitly set `MQTT_TLS=0` and `MQTT_PORT=1883` in both local configurations. Never use that setting for the production HiveMQ connection.
