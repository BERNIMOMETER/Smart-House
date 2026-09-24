import re

from django.contrib import messages
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import DeviceState, NFCRegisteredCard, NFCAuditLog, SystemState
from .mqtt import MQTTCommandError, publish_authorized_nfc_tags, publish_command, publish_security_mode

CONTROLLABLE = {
    ("kitchen_living", "living_led"),
    ("bedroom", "fan"),
    ("bedroom", "led"),
    ("entrance", "outdoor_led"),
    ("entrance", "door"),
}


def _device_map():
    return {(d.zone, d.device): d for d in DeviceState.objects.all()}


def dashboard(request):
    devices = _device_map()
    # Django templates can address simple dictionary keys with dot notation.
    status = {f"{zone}_{device}": item for (zone, device), item in devices.items()}
    system, _ = SystemState.objects.get_or_create(pk=1)
    return render(request, "house/dashboard.html", {
        "system": system,
        "status": status,
        "nfc_logs": NFCAuditLog.objects.all()[:12],
        "registered_cards": NFCRegisteredCard.objects.all(),
    })


@require_POST
def set_security_mode(request):
    enabled = request.POST.get("enabled") == "1"
    system, _ = SystemState.objects.get_or_create(pk=1)
    try:
        publish_security_mode(enabled)
    except MQTTCommandError:
        messages.error(request, "Command was not sent. Check the MQTT connection and try again.")
        return redirect("dashboard")
    # This is desired global configuration; devices subsequently report their observed state.
    system.security_mode = enabled
    system.save(update_fields=["security_mode", "updated_at"])
    messages.success(request, f"Security mode command sent: {'ON' if enabled else 'OFF'}.")
    return redirect("dashboard")


@require_POST
def control_device(request):
    zone, device, command = request.POST.get("zone"), request.POST.get("device"), request.POST.get("command")
    if (zone, device) not in CONTROLLABLE or command not in {"ON", "OFF", "AUTO", "OPEN"}:
        return HttpResponseBadRequest("Invalid device command")
    try:
        publish_command(zone, device, command)
    except MQTTCommandError:
        messages.error(request, "Command was not sent. Check the MQTT connection and try again.")
        return redirect("dashboard")
    # AUTO releases a manual override. ON/OFF set it. State itself remains device-reported.
    state, _ = DeviceState.objects.get_or_create(zone=zone, device=device)
    state.manual_override = command in {"ON", "OFF"} and device != "door"
    state.save(update_fields=["manual_override", "updated_at"])
    messages.success(request, f"{zone}/{device}: {command} command sent.")
    return redirect("dashboard")


@require_POST
def register_nfc_card(request):
    tag_id = request.POST.get("tag_id", "").strip()
    normalized_tag_id = tag_id.replace(" ", "").lower()
    if not normalized_tag_id or len(normalized_tag_id) % 2 or not re.fullmatch(r"[0-9a-f]+", normalized_tag_id):
        messages.error(request, "Enter the hexadecimal UID reported by the NFC reader.")
        return redirect("dashboard")
    if NFCRegisteredCard.objects.filter(tag_id=normalized_tag_id).exists():
        messages.error(request, "That NFC card is already registered.")
        return redirect("dashboard")
    NFCRegisteredCard.objects.create(tag_id=normalized_tag_id, note=request.POST.get("note", "").strip())
    try:
        publish_authorized_nfc_tags()
    except MQTTCommandError:
        messages.error(request, "Card saved, but the allow-list was not sent. Check the MQTT connection and try again.")
        return redirect("dashboard")
    messages.success(request, "NFC card registered and sent to the reader.")
    return redirect("dashboard")
