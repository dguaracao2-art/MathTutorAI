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
from tutoring.services.hints import hints_for, pistas_de
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
            'tipo': 'pista', 'nivel': 1, 'texto': self.pistas[0], 'siguiente': 2,
            'titulo': 'Pista 1 · columna U', 'boton': 'Ver pista 2 de la columna U'})
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


class PistasParaNinosTests(TestCase):
    """Las pistas usan los números del niño y nunca dicen el resultado."""

    def test_ninguna_pista_revela_el_resultado(self):
        import random
        azar = random.Random(7)
        for _ in range(400):
            a, b = azar.randint(10, 999), azar.randint(10, 999)
            for escrito in (a + b - 1, a + b + 10, a + b - 100, a + b + 1000):
                if not 0 <= escrito <= 9999:
                    continue
                revision = review_sum(a, b, escrito)
                for pista in hints_for(revision):
                    with self.subTest(suma=(a, b, escrito)):
                        self.assertNotIn(str(a + b), pista)
                        self.assertNotIn('profe', pista)

    def test_la_primera_pista_muestra_los_numeros_de_la_columna(self):
        pista = hints_for(review_sum(400, 600, 900))[0]
        self.assertIn('columna C', pista)
        self.assertIn('4 y 6', pista)

    def test_con_llevada_la_primera_pista_no_lo_lleva_a_otro_error(self):
        # Preguntar «¿cuánto es 2 + 1?» le haría escribir 3, que también está mal.
        pista = hints_for(review_sum(28, 17, 55))[0]
        self.assertNotIn('2 + 1', pista)
        self.assertIn('¿Te llevaste algo', pista)

    def test_la_segunda_pista_es_un_ejemplo_con_otros_numeros(self):
        for suma, propios in (((28, 17, 55), '2 + 1 + 1'), ((23, 14, 32), '3 + 4')):
            with self.subTest(suma=suma):
                pista = hints_for(review_sum(*suma))[1]
                self.assertIn('Ejemplo:', pista)
                self.assertNotIn(propios, pista)

    def test_todas_las_segundas_pistas_traen_un_ejemplo(self):
        import random
        azar = random.Random(11)
        for _ in range(300):
            a, b = azar.randint(0, 999), azar.randint(0, 999)
            escrito = a + b + azar.choice((-1, 1, 9, -10, 100, 1000))
            if not 0 <= escrito <= 9999:
                continue
            pistas = hints_for(review_sum(a, b, escrito))
            if pistas:
                with self.subTest(suma=(a, b, escrito)):
                    self.assertIn('Ejemplo:', pistas[1])

    def test_si_ya_se_llevo_el_uno_no_lo_manda_a_sumarlo_otra_vez(self):
        # 15 + 25 = 48: el 4 está bien. Si le decimos solo «lleva el 1 a la
        # izquierda», podría sumarlo de nuevo y escribir 50.
        pista = hints_for(review_sum(15, 25, 48))[1]
        self.assertIn('donde pusiste el 8', pista)
        self.assertIn('columna D ya está bien', pista)

    def test_si_falta_la_llevada_no_dice_que_la_izquierda_esta_bien(self):
        pista = hints_for(review_sum(400, 600, 900))[1]
        self.assertIn('donde pusiste el 9', pista)
        self.assertNotIn('ya está bien', pista)


class VariasColumnasTests(TestCase):
    """Todas las columnas por revisar se marcan y se recorren de una vez."""

    def test_se_encuentran_todas_las_columnas_con_error(self):
        revision = review_sum(602, 187, 691)
        self.assertEqual([d['label'] for d in revision['discrepancias']], ['U', 'D', 'C'])
        self.assertEqual([c['name'] for c in revision['columns'] if c['por_revisar']],
                         ['centenas', 'decenas', 'unidades'])

    def test_la_primera_columna_sigue_siendo_la_oficial(self):
        # RNF-06 y la API siguen hablando de la primera discrepancia.
        revision = review_sum(602, 187, 691)
        self.assertEqual(revision['column_name'], 'unidades')
        self.assertEqual([c['name'] for c in revision['columns'] if c['needs_review']],
                         ['unidades'])
        self.assertEqual(len(hints_for(revision)), 2)

    def test_dos_pistas_por_columna_de_derecha_a_izquierda(self):
        pistas = pistas_de(review_sum(602, 187, 691))
        self.assertEqual([(p['columna'], p['paso']) for p in pistas],
                         [('U', 1), ('U', 2), ('D', 1), ('D', 2), ('C', 1), ('C', 2)])
        self.assertEqual([p['texto'] for p in pistas[:2]], hints_for(review_sum(602, 187, 691)))

    def test_un_error_repetido_no_repite_el_ejemplo(self):
        pistas = pistas_de(review_sum(602, 187, 691))
        self.assertIn('Ejemplo:', pistas[1]['texto'])
        self.assertNotIn('Ejemplo:', pistas[5]['texto'])
        self.assertIn('columna U', pistas[5]['texto'])
        self.assertIn('donde pusiste el 6', pistas[5]['texto'])

    def test_no_dice_que_la_izquierda_esta_bien_si_tambien_esta_marcada(self):
        pistas = pistas_de(review_sum(28, 17, 44, carries={'decenas': 0}))
        self.assertNotIn('ya está bien', ' '.join(p['texto'] for p in pistas))

    def test_ninguna_pista_de_ninguna_columna_revela_el_resultado(self):
        import random
        azar = random.Random(3)
        for _ in range(400):
            a, b = azar.randint(10, 999), azar.randint(10, 999)
            escrito = azar.randint(0, 9999)
            if escrito == a + b:
                continue
            for pista in pistas_de(review_sum(a, b, escrito)):
                with self.subTest(suma=(a, b, escrito)):
                    self.assertNotIn(str(a + b), pista['texto'])


class PantallaVariasColumnasTests(_FlujoDeRevision, TestCase):
    """23 + 14 = 45: la U y la D están mal; se ven y se recorren las dos."""

    def setUp(self):
        self.preparar(escrito=45)

    def test_marca_las_dos_columnas_y_avanza_a_la_decena(self):
        pagina = self.client.get(reverse('tutoring:review_result')).content.decode()
        self.assertIn('Hay 2 columnas por revisar', pagina)
        self.assertEqual(pagina.count('>Revisa</span>'), 2)
        self.assertIn('Ver pista 1 de la columna U', pagina)
        for nivel in ('1', '2', '3'):
            self.client.post(reverse('tutoring:show_hint'), {
                'exercise_id': self.ejercicio.pk,
                'confirmation_id': self.confirmada['confirmation_id'], 'level': nivel,
            })
        pagina = self.client.get(reverse('tutoring:review_result')).content.decode()
        self.assertIn('Pista 1 · columna D', pagina)
        self.assertIn('Ver pista 2 de la columna D', pagina)
        self.assertEqual(self.pistas_en_intento(), 3)

    def test_por_el_canal_tambien_llega_la_pista_de_la_decena(self):
        for nivel in (1, 2):
            tutoria_vivo.pedir_pista(self.clave, self.usuario,
                                     self.confirmada['confirmation_id'], nivel)
        respuesta = tutoria_vivo.pedir_pista(self.clave, self.usuario,
                                             self.confirmada['confirmation_id'], 3)
        self.assertEqual(respuesta['titulo'], 'Pista 1 · columna D')
        self.assertEqual(respuesta['boton'], 'Ver pista 2 de la columna D')
