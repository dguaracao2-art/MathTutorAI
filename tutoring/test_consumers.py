"""Pruebas del canal de detección en tiempo real.

Comprueban el contrato del canal sin ejecutar el detector real: se sustituye
``_detectar`` por una función de prueba. Así las pruebas corren en un equipo
sin ultralytics ni modelo entrenado, igual que el resto del proyecto.
"""
from unittest.mock import patch

from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from tutoring import consumers
from tutoring.routing import websocket_urlpatterns

RUTA = "/ws/deteccion/"

FILAS = {
    "operando_a": {"x": 0.25, "y": 0.15, "w": 0.40, "h": 0.18},
    "operando_b": {"x": 0.25, "y": 0.40, "w": 0.40, "h": 0.18},
    "resultado": {"x": 0.25, "y": 0.65, "w": 0.40, "h": 0.18},
}


def _cuadro(tamano=2048):
    """Bytes cualesquiera: el detector está sustituido en estas pruebas."""
    return b"\xff\xd8\xff" + b"0" * tamano


class CanalDeteccionTests(TransactionTestCase):
    """El canal exige sesión, acepta cuadros binarios y responde cajas."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="estudiante", password="clave-de-prueba-123"
        )

    def _comunicador(self, usuario=None):
        aplicacion = URLRouter(websocket_urlpatterns)
        comunicador = WebsocketCommunicator(aplicacion, RUTA)
        from django.contrib.auth.models import AnonymousUser

        comunicador.scope["user"] = usuario or AnonymousUser()
        return comunicador

    async def test_rechaza_conexion_sin_sesion(self):
        comunicador = self._comunicador()
        conectado, codigo = await comunicador.connect()
        self.assertFalse(conectado)
        self.assertEqual(codigo, 4401)

    async def test_acepta_y_anuncia_el_detector_disponible(self):
        comunicador = self._comunicador(self.usuario)
        with patch.object(consumers, "modelo_disponible", return_value=True):
            conectado, _ = await comunicador.connect()
            self.assertTrue(conectado)
            saludo = await comunicador.receive_json_from()
        self.assertEqual(saludo["estado"], "listo")
        self.assertEqual(saludo["cuadros_por_segundo"],
                         consumers.CUADROS_POR_SEGUNDO)
        await comunicador.disconnect()

    async def test_anuncia_sin_detector_cuando_falta_el_modelo(self):
        comunicador = self._comunicador(self.usuario)
        with patch.object(consumers, "modelo_disponible", return_value=False):
            conectado, _ = await comunicador.connect()
            self.assertTrue(conectado)
            saludo = await comunicador.receive_json_from()
        self.assertEqual(saludo["estado"], "sin_detector")
        await comunicador.disconnect()

    async def test_devuelve_las_filas_detectadas(self):
        comunicador = self._comunicador(self.usuario)
        with patch.object(consumers, "modelo_disponible", return_value=True), \
                patch.object(consumers, "_detectar", return_value=FILAS):
            await comunicador.connect()
            await comunicador.receive_json_from()
            await comunicador.send_to(bytes_data=_cuadro())
            respuesta = await comunicador.receive_json_from()
        self.assertEqual(respuesta["estado"], "detectado")
        self.assertEqual(set(respuesta["filas"]),
                         {"operando_a", "operando_b", "resultado"})
        await comunicador.disconnect()

    async def test_un_cuadro_sin_filas_responde_buscando(self):
        comunicador = self._comunicador(self.usuario)
        with patch.object(consumers, "modelo_disponible", return_value=True), \
                patch.object(consumers, "_detectar", return_value=None):
            await comunicador.connect()
            await comunicador.receive_json_from()
            await comunicador.send_to(bytes_data=_cuadro())
            respuesta = await comunicador.receive_json_from()
        self.assertEqual(respuesta["estado"], "buscando")
        await comunicador.disconnect()

    async def test_un_fallo_del_detector_no_cierra_la_conexion(self):
        comunicador = self._comunicador(self.usuario)
        with patch.object(consumers, "modelo_disponible", return_value=True), \
                patch.object(consumers, "_detectar",
                             side_effect=RuntimeError("detector caído")), \
                self.assertLogs(consumers.logger, level="ERROR") as registro:
            await comunicador.connect()
            await comunicador.receive_json_from()
            await comunicador.send_to(bytes_data=_cuadro())
            respuesta = await comunicador.receive_json_from()
        # El fallo queda registrado para el administrador, pero el estudiante
        # recibe el mismo mensaje que ante un cuadro sin hoja.
        self.assertIn("detector caído", registro.output[0])
        self.assertEqual(respuesta["estado"], "buscando")
        await comunicador.disconnect()

    async def test_rechaza_un_cuadro_demasiado_grande(self):
        comunicador = self._comunicador(self.usuario)
        with patch.object(consumers, "modelo_disponible", return_value=True), \
                patch.object(consumers, "_detectar", return_value=FILAS) as detector:
            await comunicador.connect()
            await comunicador.receive_json_from()
            await comunicador.send_to(
                bytes_data=b"0" * (consumers.MAXIMO_BYTES + 1)
            )
            respuesta = await comunicador.receive_json_from()
            self.assertEqual(respuesta["estado"], "cuadro_grande")
            detector.assert_not_called()
        await comunicador.disconnect()

    async def test_rechaza_mensajes_de_texto(self):
        comunicador = self._comunicador(self.usuario)
        with patch.object(consumers, "modelo_disponible", return_value=True), \
                patch.object(consumers, "_detectar", return_value=FILAS) as detector:
            await comunicador.connect()
            await comunicador.receive_json_from()
            await comunicador.send_to(text_data="hola")
            respuesta = await comunicador.receive_json_from()
            self.assertEqual(respuesta["estado"], "formato_no_admitido")
            detector.assert_not_called()
        await comunicador.disconnect()


class NormalizacionTests(TransactionTestCase):
    """Las cajas viajan como fracciones del cuadro, no como píxeles."""

    def test_convierte_pixeles_a_fracciones(self):
        cajas = {
            "operando_a": [100, 20, 300, 60],
            "operando_b": [100, 80, 300, 120],
            "resultado": [100, 140, 300, 180],
        }
        filas = consumers._normalizar(cajas, 400, 200)
        self.assertAlmostEqual(filas["operando_a"]["x"], 0.25)
        self.assertAlmostEqual(filas["operando_a"]["y"], 0.10)
        self.assertAlmostEqual(filas["operando_a"]["w"], 0.50)
        self.assertAlmostEqual(filas["operando_a"]["h"], 0.20)

    def test_recorta_las_fracciones_al_cuadro(self):
        cajas = {
            "operando_a": [-30, -10, 500, 60],
            "operando_b": [100, 80, 300, 120],
            "resultado": [100, 140, 300, 260],
        }
        filas = consumers._normalizar(cajas, 400, 200)
        for fila in filas.values():
            self.assertGreaterEqual(fila["x"], 0.0)
            self.assertGreaterEqual(fila["y"], 0.0)
            self.assertLessEqual(fila["w"], 1.0)
            self.assertLessEqual(fila["h"], 1.0)

    def test_sin_dimensiones_no_devuelve_cajas(self):
        cajas = {nombre: [0, 0, 1, 1] for nombre in
                 ("operando_a", "operando_b", "resultado")}
        self.assertIsNone(consumers._normalizar(cajas, 0, 200))

    def test_un_cuadro_ilegible_no_lanza_excepcion(self):
        self.assertIsNone(consumers._detectar(b"esto no es una imagen"))


class PlausibilidadTests(TransactionTestCase):
    """La guía descarta detecciones que no parecen una suma vertical."""

    @staticmethod
    def _cajas(a, b, c):
        return {"operando_a": a, "operando_b": b, "resultado": c}

    def test_acepta_tres_filas_alineadas(self):
        cajas = self._cajas(
            [100, 20, 300, 60],
            [95, 80, 310, 120],
            [100, 140, 300, 180],
        )
        self.assertTrue(consumers._filas_plausibles(cajas))

    def test_rechaza_filas_repartidas_en_diagonal(self):
        # Caso observado ante la cámara: el detector marcó una pared, una
        # cortina y un rostro como si fueran los tres renglones.
        cajas = self._cajas(
            [490, 290, 685, 400],
            [525, 370, 745, 490],
            [390, 655, 555, 770],
        )
        self.assertFalse(consumers._filas_plausibles(cajas))

    def test_rechaza_filas_sin_solape_horizontal(self):
        cajas = self._cajas(
            [0, 20, 100, 60],
            [400, 80, 500, 120],
            [0, 140, 100, 180],
        )
        self.assertFalse(consumers._filas_plausibles(cajas))

    def test_rechaza_anchuras_desproporcionadas(self):
        cajas = self._cajas(
            [100, 20, 130, 60],
            [100, 80, 900, 120],
            [100, 140, 130, 180],
        )
        self.assertFalse(consumers._filas_plausibles(cajas))

    def test_la_guia_exige_mas_confianza_que_la_lectura(self):
        from tutoring.services import yolo_segmentation

        self.assertGreater(consumers.CONFIANZA_GUIA,
                           yolo_segmentation.CONFIANZA_MINIMA)