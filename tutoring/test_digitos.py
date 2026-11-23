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

    def test_encendido_si_existe_el_modelo(self):
        with patch.object(handwriting, '_interruptor_digitos', return_value=''):
            with patch.object(digitos, 'modelo_disponible', return_value=True):
                self.assertTrue(handwriting.lector_de_digitos_activo())

    def test_sin_modelo_sigue_el_lector_de_siempre(self):
        with patch.object(handwriting, '_interruptor_digitos', return_value=''):
            with patch.object(digitos, 'modelo_disponible', return_value=False):
                self.assertFalse(handwriting.lector_de_digitos_activo())

    def test_se_puede_apagar_a_proposito(self):
        for valor in ('0', 'false', 'off'):
            with self.subTest(valor=valor):
                with patch.object(handwriting, '_interruptor_digitos', return_value=valor):
                    with patch.object(digitos, 'modelo_disponible', return_value=True):
                        self.assertFalse(handwriting.lector_de_digitos_activo())

    def test_el_interruptor_prefiere_el_entorno(self):
        with patch.dict('os.environ', {'LECTOR_DIGITOS': 'OFF '}):
            self.assertEqual(handwriting._interruptor_digitos(), 'off')

    def test_sin_archivo_el_modelo_no_esta_disponible(self):
        with patch.dict('os.environ', {'MODELO_DIGITOS': '/no/existe/modelo.pt'}):
            self.assertFalse(digitos.modelo_disponible())


class RayaTests(SimpleTestCase):
    """La raya de la suma pegada a las cifras se borra antes de etiquetar."""

    def _fila_con_raya(self):
        imagen = Image.new('L', (300, 80), 255)
        lapiz = ImageDraw.Draw(imagen)
        for x in (60, 130, 200):
            lapiz.rectangle([x, 10, x + 25, 65], fill=0)
        # Raya que toca el pie de las tres cifras.
        lapiz.rectangle([40, 62, 260, 66], fill=0)
        return np.asarray(imagen)

    def test_cifras_pegadas_a_la_raya_salen_separadas(self):
        piezas = digitos.componentes_de(self._fila_con_raya(), (0, 0, 300, 80))
        self.assertEqual(len(piezas), 3)

    def test_no_borra_un_trazo_horizontal_corto(self):
        # La barra de un 7 o el pie de un 2 son más cortos que la altura de
        # la cifra: tienen que sobrevivir.
        binaria = np.zeros((80, 300), dtype=np.uint8)
        binaria[20:24, 100:140] = 255
        limpia = digitos.sin_trazos_largos(binaria, 80)
        self.assertEqual(int(limpia.sum()), int(binaria.sum()))

    def test_borra_un_trazo_horizontal_largo(self):
        binaria = np.zeros((80, 300), dtype=np.uint8)
        binaria[60:64, 20:280] = 255
        limpia = digitos.sin_trazos_largos(binaria, 80)
        self.assertEqual(int(limpia.sum()), 0)


class TintaTests(SimpleTestCase):
    """La imagen de tinta deja oscura solo la tinta azul."""

    def _hoja(self):
        rgb = np.full((60, 120, 3), 235, dtype=np.uint8)
        rgb[:, 40:44] = (150, 150, 150)       # línea gris de cuadrícula
        rgb[10:50, 70:76] = (40, 60, 170)     # trazo de bolígrafo azul
        return Image.fromarray(rgb)

    def test_la_tinta_azul_queda_oscura(self):
        tinta = digitos.imagen_de_tinta(self._hoja())
        self.assertLess(int(tinta[30, 72]), 60)

    def test_la_cuadricula_gris_desaparece(self):
        tinta = digitos.imagen_de_tinta(self._hoja())
        self.assertGreater(int(tinta[30, 41]), 200)

    def test_sin_tinta_azul_usa_el_brillo(self):
        gris = Image.new('RGB', (40, 40), (200, 200, 200))
        tinta = digitos.imagen_de_tinta(gris)
        self.assertEqual(tinta.shape, (40, 40))
        self.assertEqual(int(tinta[0, 0]), 200)

    def test_se_lee_sobre_dos_imagenes(self):
        vistas = digitos.vistas_de(self._hoja())
        self.assertEqual(len(vistas), 2)
        self.assertEqual(vistas[0].shape, vistas[1].shape)


class EleccionDeVistaTests(SimpleTestCase):
    """Por cada fila se queda la lectura cuya cifra más dudosa es más segura."""

    def test_elige_por_la_cifra_mas_dudosa(self):
        nombres = ('operando_a', 'operando_b', 'resultado')
        # La primera vista tiene mejor media en el segundo sumando, pero con
        # una cifra casi adivinada; la segunda es más pareja.
        vista_1 = {'operando_a': ('23', .99, .98), 'operando_b': ('74', .80, .45),
                   'resultado': ('37', .97, .95)}
        vista_2 = {'operando_a': ('23', .97, .96), 'operando_b': ('14', .75, .70),
                   'resultado': ('37', .98, .97)}
        with patch.object(digitos, 'cargar_clasificador', return_value=None), \
                patch.object(digitos, 'vistas_de', return_value=[1, 2]), \
                patch.object(digitos, '_leer_vista', side_effect=[vista_1, vista_2]):
            textos, _ = digitos.leer_filas(None, {}, nombres)
        self.assertEqual(textos['operando_b'], '14')

    def test_una_fila_poco_segura_queda_vacia(self):
        nombres = ('operando_a', 'operando_b', 'resultado')
        flojo = {n: ('5', .30, .30) for n in nombres}
        with patch.object(digitos, 'cargar_clasificador', return_value=None), \
                patch.object(digitos, 'vistas_de', return_value=[1, 2]), \
                patch.object(digitos, '_leer_vista', side_effect=[flojo, flojo]):
            textos, _ = digitos.leer_filas(None, {}, nombres)
        self.assertEqual(textos, dict.fromkeys(nombres, ''))
