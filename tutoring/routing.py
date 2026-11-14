"""Rutas WebSocket de la aplicación.

Separadas de ``urls.py`` porque las atiende el servidor ASGI, no el ciclo
HTTP. La dirección empieza por ``ws/`` para que nginx la distinga y aplique
la cabecera de actualización de protocolo.
"""
from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/deteccion/", consumers.DeteccionConsumer.as_asgi()),
]