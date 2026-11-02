"""Protecciones de recortes y contraste, sin modelo ni fotos privadas."""
import unittest

import numpy as np

from tutoring.services.handwriting import _limpiar_fila_binaria


class RowIlluminationTests(unittest.TestCase):
    def test_uniforma_papel_sombreado_y_conserva_un_trazo_delgado(self):
        from PIL import Image
        from tutoring.services.handwriting import _normalizar_iluminacion_fila

        # Hoja gris con iluminación desigual y dos trazos de la misma tinta.
        gris = np.tile(np.linspace(100, 220, 220).astype(np.uint8), (100, 1))
        gris[20:80, 40:43] = 35
        gris[20:80, 150:155] = 65
        copia = gris.copy()
        salida = np.asarray(_normalizar_iluminacion_fila(Image.fromarray(gris)))
        self.assertGreater(salida[30:70, 60:135].min(), 240)
        self.assertLess(salida[30:70, 41].max(), 100)
        self.assertLess(salida[30:70, 152].max(), 130)
        np.testing.assert_array_equal(gris, copia)
        self.assertEqual(salida.shape, gris.shape)

    def test_fondo_uniforme_no_crea_trazos_y_negro_no_divide_por_cero(self):
        from PIL import Image
        from tutoring.services.handwriting import _normalizar_iluminacion_fila

        for tono in (80, 180, 255):
            imagen = Image.new('RGB', (90, 45), (tono, tono, tono))
            salida = np.asarray(_normalizar_iluminacion_fila(imagen))
            np.testing.assert_array_equal(salida, np.full((45, 90), 255, np.uint8))
        negro = _normalizar_iluminacion_fila(Image.new('RGB', (90, 45), 'black'))
        self.assertEqual(negro.getextrema(), (0, 0))


class CropCleanupTests(unittest.TestCase):
    def test_conserva_digitos_altos_incluso_un_uno_delgado(self):
        esperado = np.zeros((60, 70), dtype=np.uint8)
        esperado[:, :2] = 255
        esperado[:, 20:70] = 255
        original = np.pad(esperado, ((10, 12), (15, 18)))
        copia = original.copy()
        np.testing.assert_array_equal(_limpiar_fila_binaria(original), esperado)
        np.testing.assert_array_equal(original, copia)

    def test_quita_fragmento_corto_aislado_sin_cambiar_trazos_del_numero(self):
        numero = np.zeros((80, 90), dtype=np.uint8)
        numero[:, :10] = 255
        numero[:, -10:] = 255
        numero[:10, :] = 255
        numero[-10:, :] = 255
        original = np.pad(numero, ((20, 20), (20, 50)))
        original[2:5, 130:150] = 255
        np.testing.assert_array_equal(_limpiar_fila_binaria(original), numero)

    def test_no_borra_un_trazo_largo_unido_al_digito(self):
        numero = np.zeros((80, 140), dtype=np.uint8)
        numero[:, 10:20] = 255
        numero[-5:, :] = 255
        # Sin evidencia para separar la raya de la cifra, preservar el componente.
        np.testing.assert_array_equal(_limpiar_fila_binaria(numero), numero)

    def test_fila_sin_tinta_permanece_vacia(self):
        vacia = np.zeros((25, 40), dtype=np.uint8)
        np.testing.assert_array_equal(_limpiar_fila_binaria(vacia), vacia)
