"""Regression tests for dashboard commands and MQTT state persistence."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .models import DeviceState, NFCAuditLog, SystemState
from .mqtt import MQTTBridge


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
        self.assertContains(response, 'action="/nfc/add/"')
        self.assertContains(response, 'name="tag_id"')
        self.assertContains(response, 'name="note"')
        self.assertContains(response, 'name="granted"')
