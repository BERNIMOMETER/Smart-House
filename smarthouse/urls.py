from django.contrib import admin
from django.urls import path
from house import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.dashboard, name="dashboard"),
    path("control/", views.control_device, name="control_device"),
    path("security/", views.set_security_mode, name="set_security_mode"),
    path("nfc/register/", views.register_nfc_card, name="register_nfc_card"),
]
