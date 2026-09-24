from django.contrib import admin
from django.urls import path
from house import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.dashboard, name="dashboard"),
    path("control/", views.control_device, name="control_device"),
    path("security/", views.set_security_mode, name="set_security_mode"),
    path("nfc/add/", views.add_nfc_log, name="add_nfc_log"),
    path("nfc/authorize/", views.set_nfc_authorization, name="set_nfc_authorization"),
]
