"""Pruebas del borrado de la raya de la suma.

El intento anterior se revirtió porque llegaba a marcar tinta de las cifras
como si fuera línea. Estas pruebas fijan las dos condiciones que hacen falta
para que valga la pena: que borre la raya, y que no toque los números.
"""
import numpy as np
from django.test import SimpleTestCase
from PIL import Image, ImageDraw

from tutoring.services import handwriting


def _tinta(imagen):
    """Píxeles oscuros de la imagen."""
    return int(np.count_nonzero(np.asarray(imagen.convert('L')) < 128))


def _con_raya(ancho=200, alto=60, grosor=3):
    """Dos cifras y, debajo, una raya que cruza el recorte."""
    imagen = Image.new('RGB', (ancho, alto), 'white')
    lapiz = ImageDraw.Draw(imagen)
    lapiz.rectangle([30, 10, 55, 40], outline='black', width=4)
    lapiz.rectangle([80, 10, 105, 40], outline='black', width=4)
    lapiz.rectangle([5, alto - 12, ancho - 6, alto - 12 + grosor], fill='black')
    return imagen


def _sin_raya(ancho=200, alto=60):
    imagen = Image.new('RGB', (ancho, alto), 'white')
    lapiz = ImageDraw.Draw(imagen)
    lapiz.rectangle([30, 10, 55, 40], outline='black', width=4)
    lapiz.rectangle([80, 10, 105, 40], outline='black', width=4)
    return imagen


class QuitarRayaTests(SimpleTestCase):

    def test_borra_la_raya(self):
        con = _con_raya()
        limpio = handwriting._quitar_raya_horizontal(con)
        # La franja inferior donde estaba la raya queda en blanco.
        franja = np.asarray(limpio.convert('L'))[-16:, :]
        self.assertEqual(int(np.count_nonzero(franja < 128)), 0)

    def test_conserva_las_cifras(self):
        con = _con_raya()
        limpio = handwriting._quitar_raya_horizontal(con)
        # La zona de los números mantiene su tinta intacta.
        antes = np.asarray(con.convert('L'))[:45, :]
        despues = np.asarray(limpio.convert('L'))[:45, :]
        self.assertEqual(int(np.count_nonzero(antes < 128)),
                         int(np.count_nonzero(despues < 128)))

    def test_sin_raya_no_cambia_nada(self):
        sin = _sin_raya()
        limpio = handwriting._quitar_raya_horizontal(sin)
        self.assertEqual(_tinta(sin), _tinta(limpio))

    def test_no_borra_cuando_marcaria_demasiada_tinta(self):
        # Un recorte casi todo negro: lo que la apertura marque será una parte
        # enorme de la tinta, así que la red de seguridad debe impedirlo.
        casi_negro = Image.new('RGB', (200, 60), 'black')
        limpio = handwriting._quitar_raya_horizontal(casi_negro)
        self.assertEqual(_tinta(casi_negro), _tinta(limpio))

    def test_un_recorte_diminuto_se_devuelve_igual(self):
        diminuto = Image.new('RGB', (20, 8), 'white')
        self.assertIs(handwriting._quitar_raya_horizontal(diminuto), diminuto)

    def test_una_raya_fina_tambien_desaparece(self):
        con = _con_raya(grosor=1)
        limpio = handwriting._quitar_raya_horizontal(con)
        franja = np.asarray(limpio.convert('L'))[-16:, :]
        self.assertEqual(int(np.count_nonzero(franja < 128)), 0)


class InterruptorTests(SimpleTestCase):
    """Apagado por omisión mientras no haya medición que lo respalde."""

    def test_apagado_sin_variable(self):
        from unittest.mock import patch

        with patch.dict('os.environ', {}, clear=False) as entorno:
            entorno.pop('QUITAR_RAYA', None)
            self.assertFalse(handwriting.quitar_raya_activo())

    def test_encendido_con_uno(self):
        from unittest.mock import patch

        with patch.dict('os.environ', {'QUITAR_RAYA': '1'}):
            self.assertTrue(handwriting.quitar_raya_activo())

    def test_apagado_con_cero(self):
        from unittest.mock import patch

        with patch.dict('os.environ', {'QUITAR_RAYA': '0'}):
            self.assertFalse(handwriting.quitar_raya_activo())