"""MQTT protocol adapter. Only this module knows topic/payload details."""
import json
import logging
import uuid

import paho.mqtt.client as mqtt
from django.conf import settings
from django.utils import timezone

from .models import DeviceState, NFCAuditLog, SystemState

LOG = logging.getLogger(__name__)
PREFIX = "smarthouse"


def topic(zone, device, suffix):
    return f"{PREFIX}/{zone}/{device}/{suffix}"


def _parse(payload):
    text = payload.decode("utf-8").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"state": text}


def save_state(zone, device, payload):
    value = _parse(payload) if isinstance(payload, bytes) else payload
    DeviceState.objects.update_or_create(zone=zone, device=device, defaults={"value": value})


class MQTTBridge:
    """Long-running subscriber used by `python manage.py mqtt_bridge`."""
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"django-bridge-{uuid.uuid4().hex[:8]}")
        if settings.MQTT_USERNAME:
            self.client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
        if settings.MQTT_TLS:
            self.client.tls_set()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            LOG.error("MQTT connection failed: %s", reason_code)
            return
        client.subscribe(f"{PREFIX}/+/+/state")
        client.subscribe(f"{PREFIX}/system/security_mode/state")
        LOG.info("Connected to MQTT broker and subscribed to state topics")

    def on_message(self, client, userdata, message):
        parts = message.topic.split("/")
        try:
            # smarthouse/system/security_mode/state
            if parts[1:3] == ["system", "security_mode"]:
                value = _parse(message.payload)
                state = value.get("state", value) if isinstance(value, dict) else value
                SystemState.objects.update_or_create(pk=1, defaults={"security_mode": str(state).upper() == "ON"})
                return
            # smarthouse/<zone>/<device>/state
            if len(parts) != 4 or parts[0] != PREFIX or parts[3] != "state":
                return
            zone, device = parts[1], parts[2]
            value = _parse(message.payload)
            save_state(zone, device, value)
            # NFC event is published as {tag_id, granted, note}; keep an immutable audit entry.
            if zone == "entrance" and device == "nfc" and isinstance(value, dict) and "tag_id" in value:
                NFCAuditLog.objects.create(
                    tag_id=str(value["tag_id"]), granted=bool(value.get("granted", False)),
                    source="reader", note=str(value.get("note", "")),
                )
        except Exception:
            LOG.exception("Could not process MQTT message on %s", message.topic)

    def run_forever(self):
        self.client.connect(settings.MQTT_HOST, settings.MQTT_PORT, keepalive=60)
        self.client.loop_forever(retry_first_connection=True)


def publish_command(zone, device, command):
    """Publish one retained command so reconnecting ESP32 nodes receive it."""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"django-command-{uuid.uuid4().hex[:8]}")
    if settings.MQTT_USERNAME:
        client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
    if settings.MQTT_TLS:
        client.tls_set()
    client.connect(settings.MQTT_HOST, settings.MQTT_PORT, keepalive=20)
    result = client.publish(topic(zone, device, "set"), command, retain=True)
    result.wait_for_publish(timeout=5)
    client.disconnect()


def publish_security_mode(enabled):
    publish_command("system", "security_mode", "ON" if enabled else "OFF")
