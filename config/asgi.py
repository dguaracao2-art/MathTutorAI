"""
Configuración ASGI del proyecto.

Expone ``application`` con dos protocolos: el HTTP de siempre, con el que
funcionan las pantallas y la API REST, y el WebSocket de la detección en
tiempo real. Un solo proceso atiende ambos, de modo que el despliegue sigue
siendo un monolito: cambia el servidor, no la arquitectura.

``AllowedHostsOriginValidator`` rechaza las conexiones WebSocket cuyo origen
no esté en ALLOWED_HOSTS, y ``AuthMiddlewareStack`` pone la sesión del usuario
en ``scope["user"]`` para que el canal pueda exigir autenticación.
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.asgi import get_asgi_application

# La aplicación HTTP se construye antes de importar el enrutado: así las
# aplicaciones de Django quedan cargadas cuando se leen los consumidores.
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from tutoring.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
    ),
})