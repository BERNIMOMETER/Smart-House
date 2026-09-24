from django.urls import path

from .consumers import StateConsumer


websocket_urlpatterns = [
    path("ws/updates/", StateConsumer.as_asgi()),
]