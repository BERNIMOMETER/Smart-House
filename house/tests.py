"""Regression tests for dashboard commands and MQTT state persistence."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import DeviceState, NFCRegisteredCard, NFCAuditLog, SystemState
from .mqtt import MQTTBridge, MQTTCommandError, publish_authorized_nfc_tags, publish_command, topic


class MQTTBridgeTests(TestCase):
    def send(self, topic, payload):
        MQTTBridge().on_message(None, None, SimpleNamespace(topic=topic, payload=payload.encode()))

    def test_sensor_json_state_is_persisted(self):
        self.send("smarthouse/bedroom/dht11/state", '{"temp":30.0,"humidity":65.0}')
        state = DeviceState.objects.get(zone="bedroom", device="dht11")
        self.assertEqual(state.value, {"temp": 30.0, "humidity": 65.0})

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
    def test_bridge_uses_async_connection_and_forever_retry_loop(self, client_class):
        client = client_class.return_value
        bridge = MQTTBridge()
        bridge.run_forever()
        client.connect_async.assert_called_once_with("localhost", 1883, keepalive=60)
        client.loop_forever.assert_called_once_with(retry_first_connection=True)

    @patch("house.mqtt.mqtt.Client")
    def test_command_publish_runs_network_loop_until_delivery(self, client_class):
        client = client_class.return_value
        result = client.publish.return_value
        result.rc = 0
        result.is_published.return_value = True

        publish_command("bedroom", "fan", "ON")

        client.connect.assert_called_once_with("localhost", 1883, keepalive=20)
        client.loop_start.assert_called_once_with()
        client.publish.assert_called_once_with("smarthouse/bedroom/fan/set", "ON", retain=True)
        result.wait_for_publish.assert_called_once_with(timeout=5)
        client.loop_stop.assert_called_once_with()
        client.disconnect.assert_called_once_with()

    @patch("house.mqtt.mqtt.Client")
    def test_command_publish_wraps_connection_errors(self, client_class):
        client_class.return_value.connect.side_effect = OSError("broker password must stay private")

        with self.assertLogs("house.mqtt", level="WARNING") as logs:
            with self.assertRaises(MQTTCommandError):
                publish_command("bedroom", "fan", "ON")

        self.assertIn("OSError", logs.output[0])
        self.assertNotIn("broker password", logs.output[0])

    @patch("house.mqtt.publish_command")
    def test_authorized_cards_are_published_as_a_list(self, publish):
        NFCRegisteredCard.objects.create(tag_id="f2ffacb4")
        NFCRegisteredCard.objects.create(tag_id="627084b4")

        publish_authorized_nfc_tags()

        publish.assert_called_once_with("entrance", "nfc_authorized", "627084b4,f2ffacb4")


class DashboardControlTests(TestCase):
    @patch("house.views.publish_command")
    def test_manual_on_sets_override_but_does_not_fake_device_state(self, publish):
        response = self.client.post(reverse("control_device"), {"zone": "bedroom", "device": "fan", "command": "ON"})
        self.assertRedirects(response, reverse("dashboard"))
        publish.assert_called_once_with("bedroom", "fan", "ON")
        fan = DeviceState.objects.get(zone="bedroom", device="fan")
        self.assertTrue(fan.manual_override)
        self.assertEqual(fan.value, {})

    @patch("house.views.publish_command")
    def test_auto_releases_manual_override(self, publish):
        DeviceState.objects.create(zone="entrance", device="outdoor_led", manual_override=True)
        response = self.client.post(reverse("control_device"), {"zone": "entrance", "device": "outdoor_led", "command": "AUTO"})
        self.assertRedirects(response, reverse("dashboard"))
        publish.assert_called_once_with("entrance", "outdoor_led", "AUTO")
        self.assertFalse(DeviceState.objects.get(zone="entrance", device="outdoor_led").manual_override)

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
        self.assertTrue(SystemState.objects.get(pk=1).security_mode)

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
        self.assertContains(response, 'action="/nfc/register/"')
        self.assertContains(response, 'name="tag_id"')
        self.assertContains(response, 'name="note"')

    @patch("house.views.publish_authorized_nfc_tags")
    def test_register_nfc_card_normalizes_and_publishes_uid(self, publish):
        response = self.client.post(reverse("register_nfc_card"), {"tag_id": "F2 FF AC B4", "note": "Front door"})
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(NFCRegisteredCard.objects.get().tag_id, "f2ffacb4")
        publish.assert_called_once_with()

    @patch("house.views.publish_authorized_nfc_tags")
    def test_register_nfc_card_rejects_invalid_uid(self, publish):
        response = self.client.post(reverse("register_nfc_card"), {"tag_id": "not-a-uid"})
        self.assertRedirects(response, reverse("dashboard"))
        self.assertFalse(NFCRegisteredCard.objects.exists())
        publish.assert_not_called()
