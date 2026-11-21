"""Pruebas de la lectura cifra a cifra.

Las piezas que se comprueban aquí son las geométricas: separar una fila en
cifras, descartar el signo + y normalizar el recorte. Son las que deciden si
el clasificador recibe lo que debe, y se pueden probar sin modelo entrenado.

La exactitud del clasificador no se prueba aquí: eso se mide sobre
fotografías reales con tools/medir_exactitud.py, porque depende de los datos
con los que se entrenó y no de este código.
"""
from unittest.mock import patch

import numpy as np
from django.test import SimpleTestCase
from PIL import Image, ImageDraw

from tutoring.services import digitos, handwriting


def _fila(cifras, con_signo=False, ancho=300, alto=80):
    """Una fila de bloques separados, cada uno del tamaño de una cifra."""
    imagen = Image.new('L', (ancho, alto), 255)
    lapiz = ImageDraw.Draw(imagen)
    # Las cifras ocupan siempre las mismas columnas, haya signo o no: en una
    # suma vertical el + se escribe al margen y no desplaza los números.
    x = 150
    if con_signo:
        lapiz.rectangle([20, 35, 50, 45], fill=0)
        lapiz.rectangle([30, 25, 40, 55], fill=0)
    for _ in range(cifras):
        lapiz.rectangle([x, 15, x + 25, 65], fill=0)
        x += 45
    return np.asarray(imagen)


class ComponentesTests(SimpleTestCase):

    def test_cuenta_las_cifras_de_una_fila(self):
        gris = _fila(3)
        cajas = digitos.componentes_de(gris, (0, 0, 300, 80))
        self.assertEqual(len(cajas), 3)

    def test_devuelve_las_cifras_de_izquierda_a_derecha(self):
        cajas = digitos.componentes_de(_fila(3), (0, 0, 300, 80))
        self.assertEqual([c[0] for c in cajas], sorted(c[0] for c in cajas))

    def test_descarta_la_raya_de_la_suma(self):
        imagen = Image.new('L', (300, 80), 255)
        lapiz = ImageDraw.Draw(imagen)
        lapiz.rectangle([150, 15, 175, 65], fill=0)
        lapiz.rectangle([10, 70, 290, 73], fill=0)   # raya ancha y plana
        cajas = digitos.componentes_de(np.asarray(imagen), (0, 0, 300, 80))
        self.assertEqual(len(cajas), 1)

    def test_una_caja_vacia_no_lanza_excepcion(self):
        self.assertEqual(digitos.componentes_de(_fila(2), (0, 0, 0, 0)), [])


class SignoMasTests(SimpleTestCase):

    def test_descarta_el_signo_desalineado_de_la_izquierda(self):
        gris_b = _fila(2, con_signo=True)
        cajas_b = digitos.componentes_de(gris_b, (0, 0, 300, 80))
        referencia = [digitos.componentes_de(_fila(2), (0, 0, 300, 80))]
        self.assertGreater(len(cajas_b), 2)
        limpio = digitos.sin_signo_mas(cajas_b, referencia)
        self.assertEqual(len(limpio), 2)

    def test_conserva_las_cifras_alineadas(self):
        cajas = digitos.componentes_de(_fila(2), (0, 0, 300, 80))
        referencia = [digitos.componentes_de(_fila(2), (0, 0, 300, 80))]
        self.assertEqual(len(digitos.sin_signo_mas(cajas, referencia)), 2)

    def test_sin_referencia_no_descarta_nada(self):
        cajas = digitos.componentes_de(_fila(2), (0, 0, 300, 80))
        self.assertEqual(digitos.sin_signo_mas(cajas, []), cajas)

    def test_solo_descarta_por_la_izquierda(self):
        # Una componente desalineada a la derecha es más probablemente una
        # cifra torcida que un signo, y debe conservarse.
        cajas = [(10, 10, 25, 50), (150, 10, 25, 50), (400, 10, 25, 50)]
        referencia = [[(150, 10, 25, 50)]]
        limpio = digitos.sin_signo_mas(cajas, referencia)
        self.assertEqual(limpio, cajas[1:])


class NormalizarTests(SimpleTestCase):

    def test_devuelve_el_lado_esperado(self):
        imagen = digitos.normalizar(_fila(1), (150, 15, 25, 50))
        self.assertEqual(imagen.shape, (digitos.LADO, digitos.LADO))

    def test_conserva_la_proporcion(self):
        # Un trazo alto y estrecho no debe salir cuadrado: deformarlo
        # convertiría un 1 en algo parecido a un 8.
        alto = digitos.normalizar(_fila(1), (150, 15, 10, 50))
        filas = np.flatnonzero(alto.any(axis=1))
        columnas = np.flatnonzero(alto.any(axis=0))
        self.assertGreater(filas[-1] - filas[0], columnas[-1] - columnas[0])


class InterruptorTests(SimpleTestCase):

    def test_apagado_por_omision(self):
        with patch.dict('os.environ', {}, clear=False) as entorno:
            entorno.pop('LECTOR_DIGITOS', None)
            self.assertFalse(handwriting.lector_de_digitos_activo())

    def test_encendido_exige_que_exista_el_modelo(self):
        with patch.dict('os.environ', {'LECTOR_DIGITOS': '1'}):
            with patch.object(digitos, 'modelo_disponible', return_value=False):
                self.assertFalse(handwriting.lector_de_digitos_activo())
            with patch.object(digitos, 'modelo_disponible', return_value=True):
                self.assertTrue(handwriting.lector_de_digitos_activo())

    def test_sin_archivo_el_modelo_no_esta_disponible(self):
        with patch.dict('os.environ', {'MODELO_DIGITOS': '/no/existe/modelo.pt'}):
            self.assertFalse(digitos.modelo_disponible())
