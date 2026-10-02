# Smart House IoT/MQTT System

This project runs a Django dashboard and one ESP32-S3 controller for the kitchen/living area, bedroom, and entrance. Django stores device-reported state in SQLite; HiveMQ Cloud transports MQTT commands and sensor reports. The production deployment is a Raspberry Pi behind a Cloudflare Tunnel.

## Behaviour locked into this project

- One house-wide buzzer sounds for MQ2 smoke or the entrance PIR alarm. Disarming Security Mode clears only the PIR alarm; it cannot silence a smoke alarm.
- The bedroom fan runs automatically at 30 C or above unless the dashboard sends `ON` or `OFF`; `AUTO` releases the override. The outdoor light is controlled manually from the dashboard.
- Relay channels are CH1 bedroom light (GPIO 6), CH2 kitchen/living light (GPIO 9), CH3 outdoor light (GPIO 11), and CH4 bedroom fan (GPIO 5). Set `RELAY_ACTIVE_LEVEL` in the ignored `firmware/smarthouse/config.h` for the installed board. The fan uses relay on/off only.
- The only PIR is at the entrance. There is no LDR or kitchen exhaust fan. The door `OPEN` command is an event and is never retained; other control settings are retained for reconnects.
- A valid NFC tag or dashboard door command opens the servo for four seconds. NFC reads are retained as audit records.
- The MQTT topic contract is unchanged. Do not rename topics when configuring HiveMQ Cloud.

## MQTT topic contract

```text
smarthouse/<zone>/<device>/state    # ESP32 -> Django, retained state
smarthouse/<zone>/<device>/set      # Django -> ESP32, retained command
smarthouse/system/security_mode/set
smarthouse/system/security_mode/state
```

Payloads are `ON`, `OFF`, `AUTO`, or `OPEN` for commands. Sensor payloads are JSON, such as `{"temp":30.0,"humidity":65.0}`. The `MQTT_TOPIC_PREFIX` setting defaults to `smarthouse`; it must be identical in Django and `firmware/smarthouse/config.h`.

## Local development MQTT

The ESP32 sketch in this repository uses HiveMQ Cloud over TLS on port `8883`.
Do not leave Django's development fallback (`localhost:1883`) enabled when the
ESP32 is connected to HiveMQ, because the dashboard can publish successfully to
the wrong broker and no device state will return. Copy `.env.example` to `.env`,
set the same HiveMQ host, username, password, port, TLS setting, and topic
prefix used by the firmware, then start both processes:

```bat
copy .env.example .env
python manage.py runserver
python manage.py mqtt_bridge
```

Set `DJANGO_DEBUG=1` and `DJANGO_SECURE_SSL_REDIRECT=0` in the local `.env`, and start Redis locally for WebSocket updates. Set the MQTT values to the same broker used by the ESP32.

The bridge must remain running for device-reported state to update the
dashboard. A command response means the MQTT broker accepted publication; the
live state changes only after the ESP32 receives the command and publishes its
state report.

## Production architecture

```text
Phone or laptop -- HTTPS --> Cloudflare Access + Tunnel --> Gunicorn on Raspberry Pi
                                                           |             |
                                                           |             +-- Django / SQLite
                                                           +-- MQTT/TLS -- HiveMQ Cloud -- MQTT/TLS -- ESP32-S3
```

Gunicorn listens only on `127.0.0.1:8000`. `cloudflared` makes the outbound connection to Cloudflare, so do not expose Django directly or configure router port forwarding. The MQTT subscriber is a distinct service from Gunicorn, preventing its persistent connection from blocking web requests.

## Raspberry Pi prerequisites

Use Raspberry Pi OS Bookworm or newer with Python 3.10+, stable power, persistent storage, and a reliable network connection. A Raspberry Pi 4/5 with at least 2 GB RAM is a comfortable baseline for this small deployment. Give the Pi a DHCP reservation or other stable local network identity for maintenance.

Install base packages:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip ca-certificates sqlite3 redis-server
```

Create a dedicated service account and place a checkout at `/opt/smarthouse`. The account must own the checkout because it writes `db.sqlite3` and `staticfiles`.

```bash
sudo useradd --system --create-home --home-dir /opt/smarthouse --shell /usr/sbin/nologin smarthouse
sudo -u smarthouse git clone <YOUR_REPOSITORY_URL> /opt/smarthouse
sudo -u smarthouse python3 -m venv /opt/smarthouse/.venv
sudo -u smarthouse /opt/smarthouse/.venv/bin/pip install --upgrade pip
sudo -u smarthouse /opt/smarthouse/.venv/bin/pip install -r /opt/smarthouse/requirements.txt
```

If the project is copied instead of cloned, ensure `/opt/smarthouse` is owned by `smarthouse:smarthouse` before continuing.

## Production environment

Create a root-owned environment directory and copy the tracked example. The final file contains secrets and must never be committed.

```bash
sudo install -d -m 0750 -o root -g smarthouse /etc/smarthouse
sudo install -m 0640 -o root -g smarthouse /opt/smarthouse/.env.example /etc/smarthouse/smarthouse.env
sudo nano /etc/smarthouse/smarthouse.env
```

Set these values in `/etc/smarthouse/smarthouse.env`:

| Variable | Production value |
| --- | --- |
| `DJANGO_SECRET_KEY` | A long, unique random value. |
| `DJANGO_DEBUG` | `0`. |
| `DJANGO_ALLOWED_HOSTS` | The Cloudflare hostname, for example `home.example.com`. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | The HTTPS origin, for example `https://home.example.com`. |
| `MQTT_HOST` | HiveMQ Cloud cluster hostname. |
| `MQTT_PORT` | `8883`. |
| `MQTT_USERNAME`, `MQTT_PASSWORD` | HiveMQ Cloud Access Management credentials. |
| `MQTT_TLS` | `1`; do not disable in production. |
| `MQTT_TLS_CA_CERTS` | Blank for the Raspberry Pi system CA store, or a PEM bundle path if HiveMQ requires one. |
| `MQTT_CLIENT_ID` | A unique base, such as `smarthouse-django`. |
| `MQTT_TOPIC_PREFIX` | `smarthouse`, matching the ESP32. |
| `REDIS_URL` | `redis://127.0.0.1:6379/0`, for dashboard WebSockets. |

The file is parsed by systemd. Quote values containing spaces or shell-sensitive characters. Generate a suitable Django secret with:

```bash
/opt/smarthouse/.venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Run database migrations and collect static files using the same environment-file parser as the services. This avoids exposing or mis-parsing special characters in passwords:

```bash
sudo systemd-run --wait --collect --property=User=smarthouse --property=Group=smarthouse --property=WorkingDirectory=/opt/smarthouse --property=EnvironmentFile=/etc/smarthouse/smarthouse.env /opt/smarthouse/.venv/bin/python manage.py migrate
sudo systemd-run --wait --collect --property=User=smarthouse --property=Group=smarthouse --property=WorkingDirectory=/opt/smarthouse --property=EnvironmentFile=/etc/smarthouse/smarthouse.env /opt/smarthouse/.venv/bin/python manage.py collectstatic --noinput
```

SQLite is appropriate for this project's low dashboard and sensor write volume. Do not delete or recreate `db.sqlite3`. Back it up with SQLite's online backup command, not a raw file copy while services are writing:

```bash
sudo mkdir -p /var/backups/smarthouse
sudo sqlite3 /opt/smarthouse/db.sqlite3 ".backup '/var/backups/smarthouse/db.sqlite3'"
```

## Gunicorn and MQTT services

The repository includes version-controlled templates in `deploy/systemd/`. Install and enable both services:

```bash
sudo install -m 0644 /opt/smarthouse/deploy/systemd/smarthouse-web.service /etc/systemd/system/
sudo install -m 0644 /opt/smarthouse/deploy/systemd/smarthouse-mqtt.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now smarthouse-web smarthouse-mqtt
sudo systemctl status smarthouse-web smarthouse-mqtt
```

Both services restart after crashes and boot. Inspect logs without exposing configuration values:

```bash
sudo journalctl -u smarthouse-web -f
sudo journalctl -u smarthouse-mqtt -f
```

After a code update, reinstall dependencies if needed, run migrations/`collectstatic`, then restart both services:

```bash
sudo systemctl restart smarthouse-web smarthouse-mqtt
```

The dashboard uses a WebSocket at `/ws/updates/`. Redis carries MQTT state events
from the bridge process to ASGI web workers in both development and production, so keep `redis-server` enabled:

```bash
sudo systemctl enable --now redis-server
sudo systemctl restart smarthouse-web smarthouse-mqtt
```

## HiveMQ Cloud and ESP32-S3

Create HiveMQ Cloud credentials through Access Management. Configure its cluster hostname, port `8883`, username, and password in both the Pi environment file and the ignored `firmware/smarthouse/config.h`.

For the ESP32, copy `firmware/config.example.h` to `firmware/smarthouse/config.h`, paste the public root CA that validates the HiveMQ cluster into `MQTT_ROOT_CA`, and keep `MQTT_TLS` set to `1`. The sketch synchronizes its certificate-validation clock through the configured NTP server, so allow outbound NTP on the ESP32 network. The sketch deliberately does not use insecure TLS. Flash `firmware/smarthouse/smarthouse.ino` after installing PubSubClient, DHT sensor library, MFRC522, and ESP32Servo; see [firmware/README.md](firmware/README.md) for the pin map.

## Cloudflare Tunnel and access control

1. Add the intended domain to Cloudflare and create a remotely managed Tunnel in Cloudflare Zero Trust.
2. Add a public hostname such as `home.example.com` whose service is `http://127.0.0.1:8000`.
3. Install `cloudflared` for the Pi architecture using Cloudflare's current package instructions, then install the tunnel service with the token shown in the dashboard:

   ```bash
   read -rsp 'Tunnel token: ' TUNNEL_TOKEN; echo
   sudo cloudflared service install "$TUNNEL_TOKEN"
   unset TUNNEL_TOKEN
   sudo systemctl status cloudflared
   ```

4. Create a Cloudflare Access application for the hostname and an allow policy limited to the approved identities before sharing the URL.
5. Keep Django bound to loopback and leave router port forwarding disabled.

The tunnel token is a secret: do not add it to this repository, screenshots, shell history, or a public issue. Cloudflare Access is required because the dashboard currently has controls available to any user who reaches it; it supplies the public authentication boundary without changing the frontend.

## Verification and troubleshooting

On the Pi, run these checks after installation:

```bash
sudo systemd-run --wait --collect --property=User=smarthouse --property=Group=smarthouse --property=WorkingDirectory=/opt/smarthouse --property=EnvironmentFile=/etc/smarthouse/smarthouse.env /opt/smarthouse/.venv/bin/python manage.py check
sudo systemd-run --wait --collect --property=User=smarthouse --property=Group=smarthouse --property=WorkingDirectory=/opt/smarthouse --property=EnvironmentFile=/etc/smarthouse/smarthouse.env /opt/smarthouse/.venv/bin/python manage.py test house
sudo systemctl is-enabled smarthouse-web smarthouse-mqtt cloudflared
```

- Visit the Cloudflare hostname from an allowed identity; verify HTTPS, dashboard rendering, a command publish, ESP32 actuator response, and the subsequent device-reported dashboard state after refresh.
- Verify an unauthorized identity is rejected by Cloudflare Access.
- Trigger a safe sensor/NFC test and confirm `smarthouse-mqtt` logs the connection and SQLite/dashboard receives the state.
- Temporarily disconnect the Pi or broker network, restore it, and confirm `smarthouse-mqtt` reconnects automatically.
- Reboot the Pi and verify all three services return with `systemctl status`.
- If HiveMQ TLS fails, confirm hostname, port `8883`, credentials, system CA availability, and the ESP32 CA certificate. Never resolve it by disabling certificate validation.

## Local development

For a local non-production broker, use `DJANGO_DEBUG=1`, `MQTT_TLS=0`, and port `1883` explicitly. Run the bridge and Django development server separately:

```bash
python3 manage.py mqtt_bridge
python3 manage.py runserver
```

Start Redis locally before these two processes. Dashboard commands wait at most five seconds for a broker connection and five seconds for its acknowledgement. If a command fails, the dashboard shows an error and keeps the reported device state until the ESP32 publishes a new report.

Do not use `runserver` in production.
