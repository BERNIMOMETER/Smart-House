"""MQTT protocol adapter. Only this module knows topic/payload details."""
import json
import logging
import uuid

import paho.mqtt.client as mqtt
from django.conf import settings

from .models import DeviceState, NFCAuditLog, SystemState

LOG = logging.getLogger(__name__)


class MQTTCommandError(RuntimeError):
    """A command could not be delivered to the configured MQTT broker."""


def _relative_topic(message_topic):
    prefix_parts = settings.MQTT_TOPIC_PREFIX.split("/")
    parts = message_topic.split("/")
    if parts[:len(prefix_parts)] != prefix_parts:
        return None
    return parts[len(prefix_parts):]


def _configure_client(client):
    if settings.MQTT_USERNAME:
        client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
    if settings.MQTT_TLS:
        # tls_set verifies the broker certificate and hostname by default.
        # Do not use tls_insecure_set(True): HiveMQ Cloud must stay verified.
        client.tls_set(ca_certs=settings.MQTT_TLS_CA_CERTS)
    client.reconnect_delay_set(min_delay=1, max_delay=60)
    return client


def _client_id(role, unique=False):
    suffix = f"-{uuid.uuid4().hex[:8]}" if unique else ""
    return f"{settings.MQTT_CLIENT_ID}-{role}{suffix}"


def topic(zone, device, suffix):
    return f"{settings.MQTT_TOPIC_PREFIX}/{zone}/{device}/{suffix}"


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
        self.client = _configure_client(mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=_client_id("bridge"),
        ))
        self.client.on_connect = self.on_connect
        self.client.on_connect_fail = self.on_connect_fail
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            LOG.error("MQTT connection failed: %s", reason_code)
            return
        client.subscribe(f"{settings.MQTT_TOPIC_PREFIX}/+/+/state")
        LOG.info("Connected to MQTT broker and subscribed to state topics")

    def on_connect_fail(self, client, userdata):
        LOG.warning("MQTT connection attempt failed; retrying with backoff")

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        if reason_code != 0:
            LOG.warning("MQTT connection lost: %s; reconnecting", reason_code)

    def on_message(self, client, userdata, message):
        parts = _relative_topic(message.topic)
        try:
            if parts == ["system", "security_mode", "state"]:
                value = _parse(message.payload)
                state = value.get("state", value) if isinstance(value, dict) else value
                SystemState.objects.update_or_create(pk=1, defaults={"security_mode": str(state).upper() == "ON"})
                return
            # <prefix>/<zone>/<device>/state
            if not parts or len(parts) != 3 or parts[2] != "state":
                return
            zone, device = parts[0], parts[1]
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
        # connect_async lets loop_forever retry if HiveMQ or the network is
        # unavailable while the systemd service starts.
        self.client.connect_async(settings.MQTT_HOST, settings.MQTT_PORT, keepalive=60)
        self.client.loop_forever(retry_first_connection=True)


def publish_command(zone, device, command):
    """Publish one retained command so reconnecting ESP32 nodes receive it."""
    client = _configure_client(mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=_client_id("command", unique=True),
    ))
    connected = False
    loop_started = False
    try:
        client.connect(settings.MQTT_HOST, settings.MQTT_PORT, keepalive=20)
        connected = True
        client.loop_start()
        loop_started = True
        result = client.publish(topic(zone, device, "set"), command, retain=True)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise MQTTCommandError("MQTT client did not accept the command for publishing.")
        result.wait_for_publish(timeout=5)
        if not result.is_published():
            raise MQTTCommandError("Timed out waiting for MQTT command delivery.")
    except MQTTCommandError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        # Exception text can originate in third-party transport code. Log its
        # type for diagnostics without risking credentials in journal output.
        LOG.warning("MQTT command publish failed (%s)", type(error).__name__)
        raise MQTTCommandError("Could not publish the MQTT command.") from error
    finally:
        if loop_started:
            client.loop_stop()
        if connected:
            client.disconnect()


def publish_security_mode(enabled):
    publish_command("system", "security_mode", "ON" if enabled else "OFF")


def publish_nfc_authorization(tag_id, enabled):
    """Retain one authorization decision for the ESP32 to receive on reconnect."""
    publish_command("entrance", f"nfc/authorized/{tag_id}", "ON" if enabled else "OFF")
