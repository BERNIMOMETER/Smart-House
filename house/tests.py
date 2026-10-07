"""Regression tests for dashboard commands and MQTT state persistence."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import DeviceState, NFCAuditLog, NFCRegisteredCard, SystemState
from .mqtt import MQTTBridge, MQTTCommandError, publish_command, topic


class MQTTBridgeTests(TestCase):
    @patch("house.mqtt.broadcast_state")
    def send(self, topic, payload, _broadcast):
        MQTTBridge().on_message(None, None, SimpleNamespace(topic=topic, payload=payload.encode()))

    def test_sensor_json_state_is_persisted(self):
        self.send("smarthouse/bedroom/dht11/state", '{"temp":30.0,"humidity":65.0}')
        state = DeviceState.objects.get(zone="bedroom", device="dht11")
        self.assertEqual(state.value, {"temp": 30.0, "humidity": 65.0})

    def test_fan_report_controls_manual_mode(self):
        self.send("smarthouse/bedroom/fan/state", '{"state":"ON","mode":"MANUAL"}')
        self.assertTrue(DeviceState.objects.get(zone="bedroom", device="fan").manual_override)
        self.send("smarthouse/bedroom/fan/state", '{"state":"OFF","mode":"AUTO"}')
        self.assertFalse(DeviceState.objects.get(zone="bedroom", device="fan").manual_override)

    def test_development_and_bridge_share_redis_channel_layer(self):
        from django.conf import settings as django_settings
        self.assertEqual(django_settings.CHANNEL_LAYERS["default"]["BACKEND"], "channels_redis.core.RedisChannelLayer")

    def test_redis_channel_layer_timeout_exceeds_blocking_websocket_reads(self):
        from django.conf import settings as django_settings
        from channels_redis.utils import create_pool
        from smarthouse.settings import _without_redis_socket_timeout
        host = django_settings.CHANNEL_LAYERS["default"]["CONFIG"]["hosts"][0]
        self.assertEqual(host["socket_connect_timeout"], 2)
        self.assertEqual(host["socket_timeout"], 30)
        pool = create_pool({
            "address": _without_redis_socket_timeout("redis://localhost:6379/0?socket_timeout=2"),
            "socket_connect_timeout": 2,
            "socket_timeout": 30,
        })
        self.assertEqual(pool.connection_kwargs["socket_timeout"], 30)

    def test_redis_url_read_timeout_is_removed_without_losing_other_options(self):
        from smarthouse.settings import _without_redis_socket_timeout
        redis_url = "redis://localhost:6379/0?socket_timeout=2&health_check_interval=15"
        self.assertEqual(
            _without_redis_socket_timeout(redis_url),
            "redis://localhost:6379/0?health_check_interval=15",
        )

    def test_removed_sensor_topic_is_ignored(self):
        self.send("smarthouse/kitchen_living/pir/state", "ON")
        self.send("smarthouse/entrance/ldr/state", '{"raw":1200}')
        self.send("smarthouse/kitchen_living/fan/state", "ON")
        self.assertEqual(DeviceState.objects.count(), 0)

    def test_nfc_event_creates_an_audit_log_and_current_state(self):
        self.send("smarthouse/entrance/nfc/state", '{"tag_id":"abc123","granted":true}')
        self.assertEqual(NFCAuditLog.objects.count(), 1)
        record = NFCAuditLog.objects.get()
        self.assertEqual(record.tag_id, "abc123")
        self.assertTrue(record.granted)
        self.assertEqual(record.source, "reader")
        self.assertEqual(DeviceState.objects.get(zone="entrance", device="nfc").value["tag_id"], "abc123")

    def test_global_security_state_is_persisted(self):
        self.send("smarthouse/system/security_mode/state", "ON")
        self.assertTrue(SystemState.objects.get(pk=1).security_mode)

    @override_settings(MQTT_TOPIC_PREFIX="school/smarthouse")
    def test_configured_multi_level_topic_prefix_is_persisted(self):
        self.send("school/smarthouse/bedroom/dht11/state", '{"temp":29.5}')
        state = DeviceState.objects.get(zone="bedroom", device="dht11")
        self.assertEqual(state.value, {"temp": 29.5})
        self.assertEqual(topic("bedroom", "fan", "set"), "school/smarthouse/bedroom/fan/set")

    @patch("house.mqtt.mqtt.Client")
    @override_settings(
        MQTT_TLS=True,
        MQTT_TLS_CA_CERTS="/etc/ssl/custom-ca.pem",
        MQTT_CLIENT_ID="test-django",
    )
    def test_bridge_uses_verified_tls_and_bounded_reconnects(self, client_class):
        client = client_class.return_value
        MQTTBridge()
        self.assertEqual(client_class.call_args.kwargs["client_id"], "test-django-bridge")
        client.tls_set.assert_called_once_with(ca_certs="/etc/ssl/custom-ca.pem")
        client.reconnect_delay_set.assert_called_once_with(min_delay=1, max_delay=60)

    @patch("house.mqtt.mqtt.Client")
    @override_settings(MQTT_HOST="localhost", MQTT_PORT=1883)
    def test_bridge_uses_async_connection_and_forever_retry_loop(self, client_class):
        client = client_class.return_value
        bridge = MQTTBridge()
        bridge.run_forever()
        client.connect_async.assert_called_once_with("localhost", 1883, keepalive=60)
        client.loop_forever.assert_called_once_with(retry_first_connection=True)

    @patch("house.mqtt.mqtt.Client")
    def test_bridge_clears_stale_retained_door_open(self, client_class):
        bridge = MQTTBridge()
        bridge.on_connect(bridge.client, None, None, 0, None)
        client_class.return_value.publish.assert_called_once_with(
            "smarthouse/entrance/door/set", "", qos=1, retain=True,
        )

    @patch("house.mqtt.mqtt.Client")
    @override_settings(MQTT_HOST="localhost", MQTT_PORT=1883)
    def test_command_publish_runs_network_loop_until_delivery(self, client_class):
        client = client_class.return_value
        result = client.publish.return_value
        result.rc = 0
        result.is_published.return_value = True
        client.loop_start.side_effect = lambda: client.on_connect(client, None, None, 0, None)

        publish_command("bedroom", "fan", "ON")

        client.connect_async.assert_called_once_with("localhost", 1883, keepalive=20)
        client.loop_start.assert_called_once_with()
        client.publish.assert_called_once_with("smarthouse/bedroom/fan/set", "ON", qos=1, retain=True)
        result.wait_for_publish.assert_called_once_with(timeout=5)
        client.disconnect.assert_called_once_with()
        client.loop_stop.assert_called_once_with()

    @patch("house.mqtt.mqtt.Client")
    def test_door_open_command_is_not_retained(self, client_class):
        client = client_class.return_value
        client.loop_start.side_effect = lambda: client.on_connect(client, None, None, 0, None)
        client.publish.return_value.rc = 0
        client.publish.return_value.is_published.return_value = True
        publish_command("entrance", "door", "OPEN")
        client.publish.assert_called_once_with("smarthouse/entrance/door/set", "OPEN", qos=1, retain=False)

    @patch("house.mqtt.mqtt.Client")
    def test_command_publish_wraps_connection_errors(self, client_class):
        client_class.return_value.connect_async.side_effect = OSError("broker password must stay private")

        with self.assertLogs("house.mqtt", level="WARNING") as logs:
            with self.assertRaises(MQTTCommandError):
                publish_command("bedroom", "fan", "ON")

        self.assertIn("OSError", logs.output[0])
        self.assertNotIn("broker password", logs.output[0])

    @patch("house.mqtt.mqtt.Client")
    def test_broker_rejection_returns_without_publishing(self, client_class):
        client = client_class.return_value
        client.loop_start.side_effect = lambda: client.on_connect(client, None, None, 5, None)
        with self.assertRaises(MQTTCommandError):
            publish_command("bedroom", "fan", "ON")
        client.publish.assert_not_called()


@override_settings(SECURE_SSL_REDIRECT=False)
class DashboardControlTests(TestCase):
    @patch("house.views.publish_nfc_authorization")
    def test_authorize_card_publishes_and_registers_card(self, publish):
        response = self.client.post(reverse("set_nfc_authorization"), {"tag_id": "627084B4", "enabled": "1"})
        self.assertRedirects(response, reverse("dashboard"))
        publish.assert_called_once_with("627084b4", True)
        self.assertTrue(NFCRegisteredCard.objects.filter(tag_id="627084b4").exists())

    @patch("house.views.publish_nfc_authorization")
    def test_revoke_card_publishes_and_removes_card(self, publish):
        NFCRegisteredCard.objects.create(tag_id="627084b4")
        response = self.client.post(reverse("set_nfc_authorization"), {"tag_id": "627084b4", "enabled": "0"})
        self.assertRedirects(response, reverse("dashboard"))
        publish.assert_called_once_with("627084b4", False)
        self.assertFalse(NFCRegisteredCard.objects.filter(tag_id="627084b4").exists())

    @patch("house.views.publish_command")
    def test_manual_on_does_not_fake_device_state_or_mode(self, publish):
        response = self.client.post(reverse("control_device"), {"zone": "bedroom", "device": "fan", "command": "ON"})
        self.assertRedirects(response, reverse("dashboard"))
        publish.assert_called_once_with("bedroom", "fan", "ON")
        self.assertFalse(DeviceState.objects.filter(zone="bedroom", device="fan").exists())

    @patch("house.views.publish_command")
    def test_auto_releases_manual_override(self, publish):
        DeviceState.objects.create(zone="bedroom", device="fan", manual_override=True)
        response = self.client.post(reverse("control_device"), {"zone": "bedroom", "device": "fan", "command": "AUTO"})
        self.assertRedirects(response, reverse("dashboard"))
        publish.assert_called_once_with("bedroom", "fan", "AUTO")
        self.assertTrue(DeviceState.objects.get(zone="bedroom", device="fan").manual_override)

    @patch("house.views.publish_command")
    def test_removed_auto_light_mode_is_rejected(self, publish):
        response = self.client.post(reverse("control_device"), {"zone": "entrance", "device": "outdoor_led", "command": "AUTO"})
        self.assertEqual(response.status_code, 400)
        publish.assert_not_called()

    @patch("house.views.publish_command")
    def test_door_opens_through_the_only_supported_command(self, publish):
        response = self.client.post(reverse("control_device"), {"zone": "entrance", "device": "door", "command": "OPEN"})
        self.assertRedirects(response, reverse("dashboard"))
        publish.assert_called_once_with("entrance", "door", "OPEN")

    @patch("house.views.publish_command")
    def test_unsafe_buzzer_command_is_rejected(self, publish):
        response = self.client.post(reverse("control_device"), {"zone": "kitchen_living", "device": "buzzer", "command": "OFF"})
        self.assertEqual(response.status_code, 400)
        publish.assert_not_called()

    @patch("house.views.publish_security_mode")
    def test_security_control_publishes_global_mode(self, publish):
        response = self.client.post(reverse("set_security_mode"), {"enabled": "1"})
        self.assertRedirects(response, reverse("dashboard"))
        publish.assert_called_once_with(True)
        self.assertFalse(SystemState.objects.get(pk=1).security_mode)

    @patch("house.views.publish_command", side_effect=MQTTCommandError("broker unavailable"))
    def test_publish_failure_does_not_expose_broker_details(self, publish):
        response = self.client.post(
            reverse("control_device"),
            {"zone": "bedroom", "device": "fan", "command": "ON"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain, [(reverse("dashboard"), 302)])
        self.assertContains(response, "Command was not sent. Check the MQTT connection and try again.")
        self.assertNotContains(response, "broker unavailable")

    @patch("house.views.publish_command", side_effect=MQTTCommandError("broker unavailable"))
    def test_ajax_publish_failure_returns_bounded_error_response(self, publish):
        response = self.client.post(
            reverse("control_device"),
            {"zone": "bedroom", "device": "fan", "command": "ON"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 502)
        self.assertTrue(response.json()["error"])
        self.assertFalse(DeviceState.objects.filter(zone="bedroom", device="fan").exists())

    def test_dashboard_renders_without_any_device_reports(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Smart House")
        self.assertContains(response, "No report")
        self.assertContains(response, 'aria-label="Room controls"')
        self.assertContains(response, 'id="theme-toggle"')
        self.assertContains(response, 'action="/security/"')
        self.assertContains(response, 'name="enabled" value="1"')
        self.assertContains(response, 'action="/control/"')
        self.assertContains(response, 'name="zone" value="kitchen_living"')
        self.assertContains(response, 'name="device" value="living_led"')
        self.assertContains(response, 'name="zone" value="bedroom"')
        self.assertContains(response, 'name="device" value="fan"')
        self.assertContains(response, 'name="device" value="led"')
        self.assertContains(response, 'name="zone" value="entrance"')
        self.assertContains(response, 'name="device" value="outdoor_led"')
        self.assertContains(response, 'name="device" value="door"')
        self.assertContains(response, 'name="command" value="AUTO"')
        self.assertContains(response, 'name="command" value="OPEN"')
        self.assertNotContains(response, "Living motion")
        self.assertNotContains(response, "Ambient light")
        self.assertNotContains(response, "Exhaust fan")
        self.assertContains(response, 'action="/nfc/add/"')
        self.assertContains(response, 'name="tag_id"')
        self.assertContains(response, 'name="note"')
        self.assertContains(response, 'name="granted"')
