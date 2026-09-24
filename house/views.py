from django.contrib import messages
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import DeviceState, NFCAuditLog, NFCRegisteredCard, SystemState
from .mqtt import MQTTCommandError, publish_command, publish_nfc_authorization, publish_security_mode

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
def add_nfc_log(request):
    tag_id = request.POST.get("tag_id", "").strip()
    if not tag_id:
        return HttpResponseBadRequest("Tag ID is required")
    NFCAuditLog.objects.create(
        tag_id=tag_id,
        granted=request.POST.get("granted") == "1",
        source="admin",
        note=request.POST.get("note", "").strip(),
    )
    messages.success(request, "NFC audit entry added.")
    return redirect("dashboard")


@require_POST
def set_nfc_authorization(request):
    tag_id = request.POST.get("tag_id", "").strip().lower()
    enabled = request.POST.get("enabled") == "1"
    if not tag_id or any(character not in "0123456789abcdef" for character in tag_id):
        return HttpResponseBadRequest("Tag ID must be hexadecimal")
    try:
        publish_nfc_authorization(tag_id, enabled)
    except MQTTCommandError:
        messages.error(request, "Authorization was not sent. Check the MQTT connection and try again.")
        return redirect("dashboard")
    if enabled:
        NFCRegisteredCard.objects.update_or_create(tag_id=tag_id)
        messages.success(request, f"NFC card {tag_id} authorized.")
    else:
        NFCRegisteredCard.objects.filter(tag_id=tag_id).delete()
        messages.success(request, f"NFC card {tag_id} revoked.")
    return redirect("dashboard")
