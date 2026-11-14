"""Canal en tiempo real que localiza las tres filas de la suma.

El navegador envía cuadros reducidos de la cámara por WebSocket y recibe las
coordenadas de las filas que el detector encuentra, varias veces por segundo.
Sirve para guiar el encuadre: indica si la hoja está completa dentro del marco
antes de tomar la fotografía definitiva.

Este canal **no** reconoce cifras ni revisa la suma. La lectura sigue siendo
una petición HTTP con la fotografía a resolución completa (RF-04), porque el
reconocimiento de escritura es mucho más lento que la detección y no debe
ejecutarse sobre cada cuadro.

Límites deliberados, pensados para una instancia de 2 núcleos:

- Un cuadro a la vez por conexión. Si llega otro mientras el detector trabaja,
  se descarta en lugar de acumularse. Es preferible perder cuadros a que la
  cola crezca y la guía quede retrasada respecto a lo que ve el usuario.
- Un detector a la vez en todo el proceso. El semáforo evita que varias
  conexiones saturen la CPU que también atiende las lecturas HTTP.
- Cuadros de 400 KB como máximo. Un cuadro de guía no necesita más.

Si falta ultralytics o el modelo entrenado, el canal responde ``sin_detector``
una sola vez y el navegador vuelve a la captura manual. Un compañero sin el
modelo conserva el comportamiento anterior del proyecto.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time

from channels.generic.websocket import AsyncWebsocketConsumer

from .services.yolo_segmentation import RECORTES, detectar_filas, modelo_disponible

logger = logging.getLogger(__name__)

# Peso máximo de un cuadro de guía. Supera con holgura un JPEG de 480 px.
MAXIMO_BYTES = 400 * 1024
# Cuadros por segundo que el servidor acepta de una conexión. Por encima de
# este ritmo los cuadros se descartan sin abrir el detector.
CUADROS_POR_SEGUNDO = 6
INTERVALO_MINIMO = 1.0 / CUADROS_POR_SEGUNDO
# Conexiones que pueden ocupar el detector al mismo tiempo en este proceso.
DETECCIONES_SIMULTANEAS = 1
_turno = asyncio.Semaphore(DETECCIONES_SIMULTANEAS)

# Confianza exigida en la guía, más alta que la de la lectura. Ante la cámara
# pasan escenas para las que el detector no fue entrenado —una pared, una
# persona, la habitación— y con el umbral de la lectura devolvía tres cajas
# cualesquiera. Aquí una detección dudosa se descarta: no cuesta nada, porque
# llegará otro cuadro en milisegundos. El umbral de la lectura NO se toca, de
# modo que la separación medida sobre las 50 fotografías sigue siendo la misma.
CONFIANZA_GUIA = float(os.environ.get('YOLO_CONFIANZA_GUIA', '0.5'))
# Las tres filas de una suma vertical se escriben una encima de otra. Dos filas
# consecutivas deben compartir buena parte de su anchura; si aparecen
# desplazadas en diagonal, no son las filas de una misma operación.
SOLAPE_HORIZONTAL_MINIMO = 0.45
# Tampoco pueden tener anchuras desproporcionadas entre sí.
ANCHO_RELATIVO_MAXIMO = 4.0


def _filas_plausibles(cajas):
    """¿Las tres cajas se parecen a los renglones de una suma vertical?

    Comprobación geométrica, sin modelo: barata y suficiente para descartar
    detecciones repartidas por la escena. Se aplica solo en la guía.
    """
    filas = [cajas[nombre] for nombre in RECORTES]
    anchos = [caja[2] - caja[0] for caja in filas]
    if min(anchos) <= 0:
        return False
    if max(anchos) / min(anchos) > ANCHO_RELATIVO_MAXIMO:
        return False
    for arriba, abajo in zip(filas, filas[1:]):
        solape = min(arriba[2], abajo[2]) - max(arriba[0], abajo[0])
        if solape <= 0:
            return False
        if solape / min(arriba[2] - arriba[0], abajo[2] - abajo[0]) < \
                SOLAPE_HORIZONTAL_MINIMO:
            return False
    return True


def _normalizar(cajas, ancho, alto):
    """Pasar las cajas a fracciones de 0 a 1 del cuadro enviado.

    El navegador escala el video según el tamaño de la ventana, así que
    enviarle píxeles del cuadro reducido lo obligaría a rehacer la cuenta.
    Con fracciones dibuja la caja sobre el video sea cual sea su tamaño.
    """
    if not ancho or not alto:
        return None
    normalizadas = {}
    for nombre in RECORTES:
        x1, y1, x2, y2 = cajas[nombre]
        normalizadas[nombre] = {
            "x": max(0.0, min(1.0, x1 / ancho)),
            "y": max(0.0, min(1.0, y1 / alto)),
            "w": max(0.0, min(1.0, (x2 - x1) / ancho)),
            "h": max(0.0, min(1.0, (y2 - y1) / alto)),
        }
    return normalizadas


def _detectar(datos):
    """Abrir el cuadro y localizar las filas. Se ejecuta en un hilo aparte.

    Devuelve las cajas normalizadas, o ``None`` cuando no hay tres filas
    utilizables. Un cuadro ilegible no es un error del canal: en una cámara en
    movimiento es lo habitual, y la respuesta es la misma que la de un cuadro
    sin hoja delante.
    """
    from io import BytesIO

    from PIL import Image

    try:
        with Image.open(BytesIO(datos)) as imagen:
            imagen.load()
            rgb = imagen.convert("RGB")
    except (OSError, ValueError, ImportError, Image.DecompressionBombError):
        # ImportError incluido a propósito: al cargarse, ultralytics sustituye
        # PIL.Image.open por una versión que ante un archivo ilegible intenta
        # importar pi_heif. Sin ese paquete el fallo llega como
        # ModuleNotFoundError en lugar de UnidentifiedImageError. Un cuadro
        # entrecortado por la red es corriente y no debe escalar como error.
        return None

    cajas = detectar_filas(rgb, confianza=CONFIANZA_GUIA)
    if cajas is None or not _filas_plausibles(cajas):
        return None
    return _normalizar(cajas, rgb.width, rgb.height)


class DeteccionConsumer(AsyncWebsocketConsumer):
    """Recibe cuadros de la cámara y responde con la posición de las filas."""

    async def connect(self):
        usuario = self.scope.get("user")
        if usuario is None or not usuario.is_authenticated:
            # El canal usa la misma sesión que la web (RNF-04). Sin sesión no
            # se abre: así no queda un detector accesible sin autenticar.
            await self.close(code=4401)
            return

        self._ocupado = False
        self._ultimo = 0.0
        self._avisado_sin_detector = False
        await self.accept()

        hay_detector = await asyncio.to_thread(modelo_disponible)
        await self._enviar({
            "estado": "listo" if hay_detector else "sin_detector",
            "cuadros_por_segundo": CUADROS_POR_SEGUNDO,
        })

    async def disconnect(self, code):
        self._ocupado = False

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data is None:
            # El canal solo acepta cuadros binarios. Un mensaje de texto suele
            # ser una prueba manual; se responde sin abrir el detector.
            await self._enviar({"estado": "formato_no_admitido"})
            return

        if len(bytes_data) > MAXIMO_BYTES:
            await self._enviar({"estado": "cuadro_grande"})
            return

        ahora = time.monotonic()
        if self._ocupado or (ahora - self._ultimo) < INTERVALO_MINIMO:
            # Descartar en silencio: el navegador ya tiene la guía anterior y
            # reenviará enseguida. Responder aquí solo añadiría tráfico.
            return

        self._ocupado = True
        self._ultimo = ahora
        try:
            async with _turno:
                cajas = await asyncio.to_thread(_detectar, bytes_data)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Un fallo del detector no cierra la conexión ni interrumpe la
            # captura manual, igual que en la ruta HTTP de lectura.
            logger.exception("Fallo al detectar las filas en un cuadro")
            cajas = None
        finally:
            self._ocupado = False

        if cajas is None:
            await self._enviar({"estado": "buscando"})
            return

        await self._enviar({"estado": "detectado", "filas": cajas})

    async def _enviar(self, carga):
        try:
            await self.send(text_data=json.dumps(carga))
        except Exception:
            # La conexión pudo cerrarse mientras el detector trabajaba.
            pass