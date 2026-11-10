"""La API expone los mismos servicios y conserva las reglas de la práctica."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .services import handwriting as lector
from .test_handwriting import suma_generada


def fotografia_subida(numeros, nombre='suma.png'):
    """Envolver la imagen generada como un archivo recibido por HTTP."""
    return SimpleUploadedFile(nombre, suma_generada(numeros).getvalue(),
                              content_type='image/png')

CONFIRMADA_CORRECTA = {'operand_a': 23, 'operand_b': 14, 'written_result': 37}
CONFIRMADA_CON_ERROR = {'operand_a': 28, 'operand_b': 17, 'written_result': 35}


class APITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estudiante = get_user_model().objects.create_user(
            username='practica1', password='clave-de-prueba-1')

    def setUp(self):
        self.client.force_login(self.estudiante)

    def test_sin_sesion_no_se_atiende_ninguna_ruta(self):
        self.client.logout()
        for nombre, datos in (
            ('api:revisiones', CONFIRMADA_CORRECTA),
            ('api:pistas', {**CONFIRMADA_CON_ERROR, 'numero': 1}),
            ('api:lecturas', {}),
        ):
            with self.subTest(ruta=nombre):
                respuesta = self.client.post(reverse(nombre), datos)
                self.assertIn(respuesta.status_code, (401, 403))

    def test_una_suma_correcta_no_ofrece_pistas(self):
        respuesta = self.client.post(
            reverse('api:revisiones'), CONFIRMADA_CORRECTA,
            content_type='application/json')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['estado'], 'correcto')
        self.assertIsNone(respuesta.json()['columna'])
        self.assertEqual(respuesta.json()['pistas_disponibles'], 0)

    def test_una_discrepancia_senala_la_columna_sin_revelar_el_resultado(self):
        respuesta = self.client.post(
            reverse('api:revisiones'), CONFIRMADA_CON_ERROR,
            content_type='application/json')
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo['estado'], 'requiere_revision')
        self.assertEqual(cuerpo['columna'], 'decenas')
        self.assertEqual(cuerpo['pistas_disponibles'], 2)
        self.assertNotIn('45', respuesta.content.decode())

    def test_las_pistas_llegan_de_una_en_una_y_no_hay_una_tercera(self):
        primera, segunda = (self.client.post(
            reverse('api:pistas'), {**CONFIRMADA_CON_ERROR, 'numero': numero},
            content_type='application/json') for numero in (1, 2))
        self.assertEqual(primera.status_code, 200)
        self.assertEqual(segunda.status_code, 200)
        self.assertNotEqual(primera.json()['pista'], segunda.json()['pista'])
        for texto in (primera.json()['pista'], segunda.json()['pista']):
            self.assertNotIn('45', texto)
        tercera = self.client.post(
            reverse('api:pistas'), {**CONFIRMADA_CON_ERROR, 'numero': 3},
            content_type='application/json')
        self.assertEqual(tercera.status_code, 400)

    def test_no_se_entrega_pista_de_una_suma_sin_discrepancia(self):
        respuesta = self.client.post(
            reverse('api:pistas'), {**CONFIRMADA_CORRECTA, 'numero': 1},
            content_type='application/json')
        self.assertEqual(respuesta.status_code, 409)

    def test_rechaza_numeros_fuera_del_alcance_de_la_practica(self):
        for datos in ({**CONFIRMADA_CORRECTA, 'operand_a': 1000},
                      {**CONFIRMADA_CORRECTA, 'written_result': 10000},
                      {**CONFIRMADA_CORRECTA, 'carries': {'unidades': 1}},
                      {**CONFIRMADA_CORRECTA, 'carries': {'decenas': 2}}):
            with self.subTest(datos=datos):
                respuesta = self.client.post(
                    reverse('api:revisiones'), datos,
                    content_type='application/json')
                self.assertEqual(respuesta.status_code, 400)

    def test_una_marca_de_llevada_confirmada_se_comprueba(self):
        respuesta = self.client.post(
            reverse('api:revisiones'),
            {**CONFIRMADA_CORRECTA, 'carries': {'decenas': 1}},
            content_type='application/json')
        self.assertEqual(respuesta.json()['estado'], 'requiere_revision')
        self.assertEqual(respuesta.json()['tipo_de_discrepancia'], 'carry')

    def test_la_lectura_devuelve_una_propuesta_pendiente_de_confirmar(self):
        propuesta = {
            'estado': 'pendiente_de_confirmacion', 'etapa': 'reconocimiento',
            'source': 'trocr-small-handwritten', 'can_confirm': True,
            'propuesta': {'operand_a': 23, 'operand_b': 14, 'written_result': 37},
            'mensaje': 'Lectura lista.',
        }
        # api_views importa la función por su nombre: se parchea allí.
        with patch('tutoring.api_views.leer_fotografia', return_value=propuesta):
            respuesta = self.client.post(
                reverse('api:lecturas'), {'fotografia': fotografia_subida((23, 14, 37))})
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()['confirmacion_requerida'])
        self.assertEqual(respuesta.json()['propuesta']['written_result'], 37)

    def test_un_lector_ocupado_responde_servicio_no_disponible(self):
        for error, in ((lector.ReaderBusy,), (lector.ReaderUnavailable,)):
            with self.subTest(error=error):
                with patch('tutoring.api_views.leer_fotografia', side_effect=error):
                    respuesta = self.client.post(
                        reverse('api:lecturas'),
                        {'fotografia': fotografia_subida((5, 7, 12))})
                self.assertEqual(respuesta.status_code, 503)

    def test_una_fotografia_no_admitida_se_rechaza_sin_llamar_al_lector(self):
        with patch('tutoring.api_views.leer_fotografia') as modelo:
            respuesta = self.client.post(reverse('api:lecturas'), {})
        self.assertEqual(respuesta.status_code, 400)
        modelo.assert_not_called()
