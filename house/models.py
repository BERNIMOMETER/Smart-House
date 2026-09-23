from django.db import models


class DeviceState(models.Model):
    """Last reported state or requested operating mode for one MQTT device."""
    zone = models.CharField(max_length=32)
    device = models.CharField(max_length=32)
    value = models.JSONField(default=dict)
    manual_override = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["zone", "device"], name="unique_zone_device")]
        ordering = ["zone", "device"]

    def __str__(self):
        return f"{self.zone}/{self.device}"


class SystemState(models.Model):
    """Singleton-style global state. pk=1 is created on first use."""
    security_mode = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Security mode: {'ON' if self.security_mode else 'OFF'}"


class NFCAuditLog(models.Model):
    tag_id = models.CharField(max_length=128)
    granted = models.BooleanField(default=False)
    source = models.CharField(max_length=32, default="reader")
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tag_id} ({'granted' if self.granted else 'denied'})"
