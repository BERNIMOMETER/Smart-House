# Smart House IoT/MQTT System

A Django dashboard plus three ESP32 nodes for a kitchen/living area, bedroom, and entrance. Django persists device-reported state in SQLite; MQTT transports commands and sensor reports.

## Behaviour locked into this project

- There is one buzzer, connected to `kitchen_living`. Its output is the OR of two independent, latched security alarms (living and entrance) and the live MQ2 smoke alarm. Disarming Security Mode clears only the security alarms; it cannot silence smoke.
- Both PIRs participate in Security Mode. Each node receives the retained global security-mode command. The entrance reports its alarm to the kitchen/living node, which owns the physical buzzer.
- MQ2 smoke clears the fire buzzer and exhaust fan as soon as its reading falls below the configured threshold.
- The bedroom fan automatically operates at **30°C or above** unless its website override is ON/OFF. Selecting AUTO releases the override.
- The outdoor light uses the same ON/OFF/AUTO override rule. Living and bedroom lights are manually controlled.
- A door command and a valid NFC tag open the servo for **4 seconds**, then close it. NFC events are saved as audit records.

## Start locally

1. Create a virtual environment and install packages:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Create the database and optional Django admin account:

   ```powershell
   py manage.py migrate
   py manage.py createsuperuser
   ```

3. Set MQTT configuration (the defaults are an unauthenticated broker on `localhost:1883`):

   ```powershell
   $env:MQTT_HOST = "192.168.1.10"
   $env:MQTT_PORT = "1883"
   # Set MQTT_USERNAME, MQTT_PASSWORD, and MQTT_TLS=1 when required.
   ```

4. Run these in separate terminals:

   ```powershell
   py manage.py mqtt_bridge
   py manage.py runserver
   ```

Open `http://127.0.0.1:8000/`. The bridge subscribes to all `.../state` messages and is the process that keeps SQLite synchronized with actual ESP32 reports. Dashboard controls only publish retained `.../set` commands; the status is updated from the ESP32 state report, rather than pretending a sent command succeeded.

Run automated backend regression tests with:

```powershell
py manage.py test house
```

## MQTT topics

```
smarthouse/<zone>/<device>/state    # ESP32 -> Django, retained state
smarthouse/<zone>/<device>/set      # Django -> ESP32, retained command
smarthouse/system/security_mode/set
smarthouse/system/security_mode/state
```

Payloads are `ON`, `OFF`, `AUTO`, or `OPEN` for actuator commands. Sensor payloads use JSON where they contain readings, such as `{"temp":30.0,"humidity":65.0}`.

## ESP32 setup

Copy [firmware/config.example.h](firmware/config.example.h) to `firmware/config.h` and set Wi-Fi and broker values; `config.h` is ignored by Git. Open and flash one sketch per node:

- `firmware/kitchen_living/kitchen_living.ino`
- `firmware/bedroom/bedroom.ino`
- `firmware/entrance/entrance.ino`

Adjust pin constants and thresholds at the top of each sketch for the real wiring. Install these Arduino libraries: **PubSubClient**, **DHT sensor library**, **MFRC522**, and **ESP32Servo**. Replace `REPLACE_WITH_AUTHORISED_UID` in the entrance sketch with an authorised NFC UID before using its reader.

## PythonAnywhere

Set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`, and the MQTT environment variables in the web app configuration. Run `collectstatic` after deployment. A free PythonAnywhere account cannot host a continuous MQTT socket worker; use a broker reachable by the ESP32 nodes and run `mqtt_bridge` on a local/Raspberry Pi/other always-on service, or use a paid always-on task. A scheduled task alone will only provide delayed polling-like updates, not live MQTT subscriptions.
