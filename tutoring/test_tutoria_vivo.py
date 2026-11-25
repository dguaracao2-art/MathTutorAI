"""Pruebas de la tutoría en tiempo real (``/ws/tutoria/``).

La suma de prueba es 23 + 14 con el resultado mal escrito (32), igual que en
las pruebas del flujo de revisión. El lector está sustituido: estas pruebas
no necesitan modelos ni fotografías reales.
"""
from io import BytesIO
from unittest.mock import patch

from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from PIL import Image

from tutoring.models import Attempt, Exercise
from tutoring.routing import websocket_urlpatterns
from tutoring.services import tutoria_vivo
from tutoring.services.hints import hints_for
from tutoring.services.sum_review import review_sum

RUTA = '/ws/tutoria/'


class _FlujoDeRevision:
    """Llevar una suma hasta «Comprobar mi suma» por la vía HTTP de siempre."""

    def preparar(self, escrito=32):
        self.usuario = get_user_model().objects.create_user(
            username='aprendiz', password='clave-de-prueba-123')
        self.ejercicio = Exercise.objects.create(operand_a=23, operand_b=14)
        self.client.force_login(self.usuario)
        self.client.post(reverse('tutoring:select_exercise', args=[self.ejercicio.pk]))
        lector = patch('tutoring.views.leer_fotografia', return_value={
            'estado': 'pendiente_de_confirmacion', 'source': 'prueba',
            'propuesta': {'operand_a': 23, 'operand_b': 14, 'written_result': escrito},
            'can_confirm': True, 'mensaje': 'Revisa los números.',
        })
        lector.start()
        self.addCleanup(lector.stop)
        token = self.client.post(reverse('tutoring:upload_photo'), {
            'exercise_id': self.ejercicio.pk, 'photo': self._foto(),
        }).json()['reading_token']
        self.confirmada = self.client.post(reverse('tutoring:confirm_sum'), {
            'exercise_id': self.ejercicio.pk, 'reading_token': token, 'photo': self._foto(),
            'operand_a': 23, 'operand_b': 14, 'written_result': escrito,
        }).json()['confirmed']
        self.client.post(reverse('tutoring:check_sum'), {
            'exercise_id': self.ejercicio.pk,
            'confirmation_id': self.confirmada['confirmation_id'],
        })
        self.clave = self.client.session.session_key
        self.pistas = hints_for(review_sum(23, 14, escrito))

    @staticmethod
    def _foto():
        datos = BytesIO()
        Image.new('RGB', (40, 40), 'white').save(datos, 'PNG')
        return SimpleUploadedFile('suma.png', datos.getvalue(), content_type='image/png')

    def nivel_en_sesion(self):
        return SessionStore(session_key=self.clave)['sum_review']['hint_level']

    def pistas_en_intento(self):
        return Attempt.objects.get(confirmation_id=self.confirmada['confirmation_id']).hint_count


class ReglasDePistaTests(_FlujoDeRevision, TestCase):
    """``pedir_pista`` sigue exactamente las reglas de la vista HTTP."""

    def setUp(self):
        self.preparar()

    def pedir(self, nivel, confirmacion=None):
        return tutoria_vivo.pedir_pista(
            self.clave, self.usuario,
            confirmacion or self.confirmada['confirmation_id'], nivel)

    def test_entrega_la_primera_pista_y_la_registra(self):
        respuesta = self.pedir(1)
        self.assertEqual(respuesta, {
            'tipo': 'pista', 'nivel': 1, 'texto': self.pistas[0], 'siguiente': 2})
        self.assertEqual(self.nivel_en_sesion(), 1)
        self.assertEqual(self.pistas_en_intento(), 1)

    def test_la_segunda_pista_es_la_ultima(self):
        self.pedir(1)
        respuesta = self.pedir(2)
        self.assertEqual(respuesta['texto'], self.pistas[1])
        self.assertIsNone(respuesta['siguiente'])
        self.assertEqual(self.pistas_en_intento(), 2)

    def test_no_se_puede_saltar_una_pista(self):
        respuesta = self.pedir(2)
        self.assertEqual(respuesta['tipo'], 'aviso')
        self.assertEqual(self.nivel_en_sesion(), 0)
        self.assertEqual(self.pistas_en_intento(), 0)

    def test_no_hay_tercera_pista(self):
        self.pedir(1)
        self.pedir(2)
        self.assertEqual(self.pedir(3)['tipo'], 'aviso')
        self.assertEqual(self.nivel_en_sesion(), 2)

    def test_repetir_una_pista_no_la_cuenta_dos_veces(self):
        self.pedir(1)
        respuesta = self.pedir(1)
        self.assertEqual(respuesta['texto'], self.pistas[0])
        self.assertEqual(self.pistas_en_intento(), 1)

    def test_otra_lectura_no_recibe_pistas(self):
        self.assertEqual(self.pedir(1, confirmacion='otra')['tipo'], 'aviso')
        self.assertEqual(self.nivel_en_sesion(), 0)

    def test_nunca_entrega_el_resultado(self):
        for nivel in (1, 2):
            self.assertNotIn('37', self.pedir(nivel)['texto'])


class SumaCorrectaTests(_FlujoDeRevision, TestCase):

    def setUp(self):
        self.preparar(escrito=37)

    def test_una_suma_correcta_no_tiene_pistas(self):
        respuesta = tutoria_vivo.pedir_pista(
            self.clave, self.usuario, self.confirmada['confirmation_id'], 1)
        self.assertEqual(respuesta['tipo'], 'aviso')


class AvisosDesdeHttpTests(_FlujoDeRevision, TestCase):
    """Las vistas de siempre avisan al canal; las páginas cargan el script."""

    def setUp(self):
        self.preparar()

    def test_comprobar_una_suma_avisa_del_progreso(self):
        with patch('tutoring.review_views.avisar_progreso') as avisar:
            self.client.post(reverse('tutoring:select_exercise', args=[self.ejercicio.pk]))
            token = self.client.post(reverse('tutoring:upload_photo'), {
                'exercise_id': self.ejercicio.pk, 'photo': self._foto(),
            }).json()['reading_token']
            nueva = self.client.post(reverse('tutoring:confirm_sum'), {
                'exercise_id': self.ejercicio.pk, 'reading_token': token, 'photo': self._foto(),
                'operand_a': 23, 'operand_b': 14, 'written_result': 32,
            }).json()['confirmed']
            self.client.post(reverse('tutoring:check_sum'), {
                'exercise_id': self.ejercicio.pk, 'confirmation_id': nueva['confirmation_id'],
            })
        avisar.assert_called_once_with(self.usuario.pk)

    def test_pedir_una_pista_por_http_avisa_del_progreso(self):
        with patch('tutoring.review_views.avisar_progreso') as avisar:
            self.client.post(reverse('tutoring:show_hint'), {
                'exercise_id': self.ejercicio.pk,
                'confirmation_id': self.confirmada['confirmation_id'], 'level': '1',
            })
        avisar.assert_called_once_with(self.usuario.pk)

    def test_un_fallo_del_canal_no_rompe_la_revision(self):
        with patch('channels.layers.get_channel_layer', side_effect=RuntimeError('sin capa')), \
                self.assertLogs('tutoring.services.tutoria_vivo', level='ERROR'):
            tutoria_vivo.avisar_progreso(self.usuario.pk)

    def test_las_pantallas_cargan_la_tutoria_en_vivo(self):
        revision = self.client.get(reverse('tutoring:review_result')).content.decode()
        self.assertIn('data-tutoria-vivo="pistas"', revision)
        self.assertIn('tutoria_vivo.js', revision)
        progreso = self.client.get(reverse('tutoring:progress')).content.decode()
        self.assertIn('data-tutoria-vivo="progreso"', progreso)
        self.assertIn('23 + 14', progreso)


class CanalTutoriaTests(_FlujoDeRevision, TransactionTestCase):
    """El canal exige sesión, entrega pistas y difunde el progreso."""

    def setUp(self):
        self.preparar()

    def _comunicador(self, usuario=None, clave=None):
        comunicador = WebsocketCommunicator(URLRouter(websocket_urlpatterns), RUTA)
        comunicador.scope['user'] = usuario or AnonymousUser()
        comunicador.scope['session'] = SessionStore(session_key=clave)
        return comunicador

    async def _abierto(self):
        comunicador = self._comunicador(self.usuario, self.clave)
        conectado, _ = await comunicador.connect()
        self.assertTrue(conectado)
        self.assertEqual(await comunicador.receive_json_from(), {'tipo': 'listo'})
        return comunicador

    async def test_rechaza_conexion_sin_sesion(self):
        conectado, codigo = await self._comunicador().connect()
        self.assertFalse(conectado)
        self.assertEqual(codigo, 4401)

    async def test_la_pista_llega_y_el_progreso_se_actualiza(self):
        comunicador = await self._abierto()
        await comunicador.send_json_to({
            'accion': 'pista', 'nivel': 1,
            'confirmation_id': self.confirmada['confirmation_id'],
        })
        pista = await comunicador.receive_json_from()
        self.assertEqual(pista['tipo'], 'pista')
        self.assertEqual(pista['texto'], self.pistas[0])
        progreso = await comunicador.receive_json_from()
        self.assertEqual(progreso['tipo'], 'progreso')
        self.assertEqual(progreso['registros'][0]['exercise'], '23 + 14')
        self.assertEqual(progreso['registros'][0]['hints'], 1)
        self.assertEqual(await database_sync_to_async(self.pistas_en_intento)(), 1)
        await comunicador.disconnect()

    async def test_otra_pantalla_recibe_el_progreso(self):
        comunicador = await self._abierto()
        await database_sync_to_async(tutoria_vivo.avisar_progreso)(self.usuario.pk)
        progreso = await comunicador.receive_json_from()
        self.assertEqual(progreso['tipo'], 'progreso')
        self.assertEqual(progreso['registros'][0]['attempts'], 1)
        await comunicador.disconnect()

    async def test_mensajes_que_no_son_una_pista(self):
        comunicador = await self._abierto()
        for mensaje in ('hola', '{"accion": "otra"}', '{"accion": "pista", "nivel": "1"}'):
            await comunicador.send_to(text_data=mensaje)
            respuesta = await comunicador.receive_json_from()
            self.assertEqual(respuesta['tipo'], 'aviso')
        await comunicador.send_to(bytes_data=b'\x00\x01')
        self.assertEqual((await comunicador.receive_json_from())['tipo'], 'aviso')
        await comunicador.disconnect()

    async def test_nadie_recibe_el_progreso_de_otro(self):
        otro = await database_sync_to_async(get_user_model().objects.create_user)(
            username='otro', password='clave-de-prueba-456')
        comunicador = await self._abierto()
        await database_sync_to_async(tutoria_vivo.avisar_progreso)(otro.pk)
        self.assertTrue(await comunicador.receive_nothing(timeout=0.2))
        await comunicador.disconnect()
