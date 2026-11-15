"""Pruebas de la sustitución del modelo de lectura desde el entorno.

Lo que hay que garantizar es que no cambia nada por omisión y que la revisión
fija, que es el hash concreto del modelo pequeño, no se le aplique a otro
modelo distinto.
"""
import importlib
import importlib.util
from unittest.mock import patch

from django.test import SimpleTestCase
from unittest import skipUnless

from tutoring.services import handwriting

HAY_TRANSFORMERS = importlib.util.find_spec('transformers') is not None


class ModeloConfigurableTests(SimpleTestCase):

    def _recargar(self):
        return importlib.reload(handwriting)

    def tearDown(self):
        # Dejar el módulo como estaba para no afectar al resto de la suite.
        self._recargar()

    def test_sin_variable_usa_el_modelo_de_siempre(self):
        with patch.dict('os.environ', {}, clear=False) as entorno:
            entorno.pop('MODELO_LECTOR', None)
            modulo = self._recargar()
            self.assertEqual(modulo.MODELO, modulo.MODELO_POR_OMISION)
            self.assertEqual(modulo.MODELO, 'microsoft/trocr-small-handwritten')

    def test_una_variable_vacia_no_sustituye_nada(self):
        with patch.dict('os.environ', {'MODELO_LECTOR': '   '}):
            modulo = self._recargar()
            self.assertEqual(modulo.MODELO, modulo.MODELO_POR_OMISION)

    def test_la_variable_sustituye_el_modelo(self):
        with patch.dict('os.environ',
                        {'MODELO_LECTOR': 'microsoft/trocr-base-handwritten'}):
            modulo = self._recargar()
            self.assertEqual(modulo.MODELO, 'microsoft/trocr-base-handwritten')
            self.assertNotEqual(modulo.MODELO, modulo.MODELO_POR_OMISION)

    @skipUnless(HAY_TRANSFORMERS, 'requiere transformers instalado')
    def test_la_revision_fija_solo_se_aplica_al_modelo_de_omision(self):
        # El hash pertenece al modelo pequeño. Pasárselo a otro haría fallar
        # la descarga con un error poco claro.
        capturado = {}

        def falso_from_pretrained(nombre, **opciones):
            capturado.setdefault(nombre, []).append(opciones)
            raise RuntimeError('corte deliberado: solo se comprueban las opciones')

        with patch('transformers.TrOCRProcessor.from_pretrained',
                   side_effect=falso_from_pretrained):
            with self.assertRaises(RuntimeError):
                handwriting.cargar_modelo('microsoft/trocr-base-handwritten')
            with self.assertRaises(RuntimeError):
                handwriting.cargar_modelo(handwriting.MODELO_POR_OMISION)

        base = capturado['microsoft/trocr-base-handwritten'][0]
        omision = capturado[handwriting.MODELO_POR_OMISION][0]
        self.assertNotIn('revision', base)
        self.assertEqual(omision.get('revision'), handwriting.REVISION_MODELO)