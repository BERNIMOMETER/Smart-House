from django.contrib import admin
from .models import DeviceState, NFCAuditLog, SystemState


@admin.register(DeviceState)
class DeviceStateAdmin(admin.ModelAdmin):
    list_display = ("zone", "device", "manual_override", "updated_at")
    list_filter = ("zone", "manual_override")


@admin.register(NFCAuditLog)
class NFCAuditLogAdmin(admin.ModelAdmin):
    list_display = ("tag_id", "granted", "source", "created_at")
    list_filter = ("granted", "source")
    search_fields = ("tag_id", "note")


admin.site.register(SystemState)
