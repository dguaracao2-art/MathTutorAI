"""Canal en tiempo real de la tutoría: ``/ws/tutoria/``.

Complementa al canal de detección. Aquel guía la cámara; este acompaña al
estudiante después de comprobar su suma:

- **Pistas en vivo.** En la pantalla de revisión, «Ver pista» llega por este
  canal y aparece sin recargar la página. Se registra igual que antes: el
  nivel en la sesión y el número de pistas en el intento.
- **Progreso en vivo.** Cada vez que se registra un intento o una pista, las
  pantallas de «Mi progreso» abiertas por ese mismo usuario se actualizan
  solas, aunque estén en otro dispositivo.

El canal no revisa números mientras se escriben ni entrega la respuesta: usa
las mismas reglas que la vista HTTP (ver ``services/tutoria_vivo.py``). Si el
canal no está disponible, el formulario de siempre sigue funcionando.
"""
from __future__ import annotations

import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .services.tutoria_vivo import (
    avisar_progreso, grupo_de, pedir_pista, registros_para_enviar,
)

logger = logging.getLogger(__name__)

# Un mensaje de pista ocupa unas decenas de bytes. Algo mucho mayor no es
# del navegador de la aplicación y se rechaza sin leerlo.
MAXIMO_MENSAJE = 2048
AVISO_FORMATO = 'Mensaje no admitido.'


class TutoriaConsumer(AsyncWebsocketConsumer):
    """Entrega pistas y avisos de progreso al estudiante con sesión iniciada."""

    async def connect(self):
        self._grupo = None
        usuario = self.scope.get('user')
        if usuario is None or not usuario.is_authenticated:
            # Misma regla que el canal de detección: sin sesión no se abre.
            await self.close(code=4401)
            return
        sesion = self.scope.get('session')
        self._clave = getattr(sesion, 'session_key', None)
        self._grupo = grupo_de(usuario.pk)
        await self.channel_layer.group_add(self._grupo, self.channel_name)
        await self.accept()
        await self._enviar({'tipo': 'listo'})

    async def disconnect(self, code):
        if self._grupo:
            await self.channel_layer.group_discard(self._grupo, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if text_data is None or len(text_data) > MAXIMO_MENSAJE:
            await self._enviar({'tipo': 'aviso', 'texto': AVISO_FORMATO})
            return
        try:
            datos = json.loads(text_data)
        except ValueError:
            await self._enviar({'tipo': 'aviso', 'texto': AVISO_FORMATO})
            return
        nivel = datos.get('nivel') if isinstance(datos, dict) else None
        confirmacion = datos.get('confirmation_id') if isinstance(datos, dict) else None
        if (datos.get('accion') if isinstance(datos, dict) else None) != 'pista' \
                or type(nivel) is not int or not isinstance(confirmacion, str):
            await self._enviar({'tipo': 'aviso', 'texto': AVISO_FORMATO})
            return
        if not self._clave:
            await self._enviar({'tipo': 'aviso', 'texto': 'Tu sesión terminó. Vuelve a iniciar sesión.'})
            return

        usuario = self.scope['user']
        try:
            respuesta = await database_sync_to_async(pedir_pista)(
                self._clave, usuario, confirmacion, nivel)
        except Exception:
            logger.exception('Fallo al entregar una pista por el canal')
            # El navegador vuelve al formulario de siempre ante cualquier aviso.
            respuesta = {'tipo': 'aviso', 'texto': 'No se pudo mostrar la pista.'}
        await self._enviar(respuesta)
        if respuesta.get('tipo') == 'pista':
            await database_sync_to_async(avisar_progreso)(usuario.pk)

    async def progreso_actualizado(self, evento):
        """Evento del grupo del usuario: enviar su progreso al día."""
        registros = await database_sync_to_async(registros_para_enviar)(self.scope['user'])
        await self._enviar({'tipo': 'progreso', 'registros': registros})

    async def _enviar(self, carga):
        try:
            await self.send(text_data=json.dumps(carga, ensure_ascii=False))
        except Exception:
            # La conexión pudo cerrarse mientras se preparaba la respuesta.
            pass
