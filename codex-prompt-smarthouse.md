# Prompt for Codex — Smart House IoT/MQTT System

## Context
Build a smart house monitoring & control system for a school project. Three physical zones, each with an ESP32 node running C++ (Arduino framework) that talks to a Django backend over MQTT. Django is the single source of truth and the web dashboard; SQLite is the database; Tailwind CSS for styling; hosted on PythonAnywhere.

## Zones and Hardware

**Zone: kitchen_living** (Kitchen + Living Room, one shared space)
- Sensors: MQ2 (smoke, analog, polled continuously)
- Actuators: Fan (kitchen, exhaust — auto ON when smoke detected), LED (living room), Buzzer (the ONE buzzer for the whole house), PIR (motion, living room)

**Zone: bedroom**
- Sensors: DHT11 (temperature + humidity)
- Actuators: Fan (auto ON above a temperature threshold), LED

**Zone: entrance**
- Sensors: LDR (ambient light), PIR (motion/alarm), NFC reader (door access)
- Actuators: Servo motor (door lock/unlock), LED

## Global Rules (do not deviate from these)
1. There is exactly **one buzzer**, physically wired to the kitchen_living node (living room). It can be triggered by TWO independent events, and must track them as independent flags (so one clearing doesn't silence the other):
   - MQ2 smoke detected → buzzer ON, **regardless of security mode state**.
   - PIR (living room OR entrance — clarify which PIRs count) detects motion **while security mode is ON** → buzzer ON.
2. Security Mode is a single global boolean, controlled from the Django website, published over MQTT to all nodes (or checked server-side before acting on PIR events — pick one architecture and justify it).
3. NFC reader logic lives on the entrance node: valid tag → open servo, log the event; Django stores the audit log (readable and writable via the web UI — allow manual log entry/edit for admin).
4. All actuator state is controllable AND readable from the Django dashboard (see per-feature Remote column below) — every actuator's current state must be persisted in Django so the dashboard reflects real device state, not just "last command sent."

## Feature Behavior Spec

| Feature | Trigger | Action | Remote (Django) |
|---|---|---|---|
| Home security (door) | NFC tag read | Open servo (auto-close after N sec — define N) | Remote "open door" command; NFC audit log (read/write) |
| Security alarm | PIR motion, while Security Mode ON | Buzzer ON | Read-only status |
| Fire alert | MQ2 smoke | Buzzer ON | Read-only status |
| Bedroom temp regulation | DHT11 | Fan auto ON/OFF | Read DHT11 values; read/write Fan boolean (manual override) |
| Outdoor light | LDR OR manual website command | Set outdoor LED | Read LDR + light state; read/write |
| Living room light | Manual website command only | Set LED | Read/write |
| Bedroom light | Manual website command only | Set LED | Read/write |

Resolve before coding: when a manual override (e.g. Fan/light forced ON via website) conflicts with automatic sensor logic, which wins? Pick a rule (e.g. manual override holds until explicitly released back to "auto") and apply it consistently across Fan and both Light Control features.

## MQTT Topic Convention
Use this structure (adjust prefix if you already have one):
```
smarthouse/<zone>/<device>/state      # device -> Django, retained, e.g. sensor reading or actuator status
smarthouse/<zone>/<device>/set        # Django -> device, command
smarthouse/system/security_mode/state
smarthouse/system/security_mode/set
```
Example: `smarthouse/bedroom/fan/set` (payload `"ON"`/`"OFF"`), `smarthouse/bedroom/dht11/state` (payload JSON `{"temp":28.5,"humidity":60}`).

## What I need from you (Codex)
1. **ESP32 C++ firmware**, one file per zone (kitchen_living, bedroom, entrance), using `WiFi.h` + `PubSubClient` (or `AsyncMqttClient`) — subscribe to `.../set` topics, publish `.../state` on sensor change or on a fixed interval, implement the auto-actuation rules above with the manual-override rule respected.
2. **Django app**: models for each zone/device's current state + the NFC audit log; an MQTT client running in Django (e.g. `paho-mqtt` in a background thread/management command) that syncs incoming `/state` messages into the DB and publishes `/set` messages when the dashboard issues commands.
3. **Dashboard templates** (Tailwind) showing live status per zone and control toggles per the Remote column above.
4. **requirements.txt** and a short README on running the MQTT bridge alongside `runserver`, plus PythonAnywhere deployment notes (PythonAnywhere doesn't allow long-running background sockets on free tier — flag this and suggest a workaround, e.g. a scheduled task or an always-on task if available).

Ask me before assuming values for: fire-alert auto-off condition, servo auto-close delay, temperature threshold for bedroom fan, and which PIR(s) count toward the security alarm.
