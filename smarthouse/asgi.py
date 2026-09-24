import os
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smarthouse.settings")

django_application = get_asgi_application()

from house.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
	"http": django_application,
	"websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
})
