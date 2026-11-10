"""El detector es opcional: sin modelo, la lectura sigue siendo la anterior."""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from PIL import Image

from tutoring.services import handwriting as lector
from tutoring.services import yolo_segmentation as detector
from tutoring.test_handwriting import suma_generada

TRES_FILAS = [[40, 20, 150, 70], [45, 115, 155, 165], [50, 210, 160, 260]]


class OrdenarFilasTests(SimpleTestCase):
    def test_asigna_los_nombres_de_arriba_hacia_abajo(self):
        orden = detector.ordenar_filas([TRES_FILAS[2], TRES_FILAS[0], TRES_FILAS[1]])
        self.assertEqual(orden, {
            'operando_a': TRES_FILAS[0],
            'operando_b': TRES_FILAS[1],
            'resultado': TRES_FILAS[2],
        })

    def test_rechaza_un_numero_de_filas_distinto_de_tres(self):
        self.assertIsNone(detector.ordenar_filas(TRES_FILAS[:2]))
        self.assertIsNone(detector.ordenar_filas(TRES_FILAS + [[0, 300, 90, 350]]))

    def test_rechaza_filas_superpuestas_o_un_fragmento_suelto(self):
        superpuestas = [[0, 0, 100, 100], [0, 20, 100, 120], [0, 200, 100, 300]]
        self.assertIsNone(detector.ordenar_filas(superpuestas))
        fragmento = [[0, 0, 100, 100], [0, 120, 100, 128], [0, 200, 100, 300]]
        self.assertIsNone(detector.ordenar_filas(fragmento))

    def test_rechaza_una_caja_sin_superficie(self):
        self.assertIsNone(detector.ordenar_filas(
            [[10, 10, 10, 10], TRES_FILAS[1], TRES_FILAS[2]]))


class ModeloAusenteTests(SimpleTestCase):
    def test_sin_archivo_no_se_importa_ultralytics(self):
        # Importar ultralytics sustituye PIL.Image.open; sin modelo no debe pasar.
        with patch('builtins.__import__', side_effect=AssertionError('no importar')):
            self.assertFalse(detector.modelo_disponible('local_yolo/no_existe.pt'))

    def test_sin_modelo_la_separacion_devuelve_none(self):
        with patch.object(detector, 'modelo_disponible', return_value=False):
            self.assertIsNone(detector.detectar_filas(Image.new('RGB', (80, 80))))
            self.assertIsNone(detector.separar_con_yolo(Image.new('RGB', (80, 80))))

    def test_la_lectura_usa_opencv_cuando_no_hay_detector(self):
        with patch.object(lector, 'separar_con_yolo', return_value=None, create=True):
            _, _, recortes, _, _ = lector.preparar_suma(suma_generada((5, 7, 12)))
        self.assertEqual(set(recortes), set(lector.RECORTES))


class DetectorToleranteTests(SimpleTestCase):
    def _salida(self, cajas, confianzas=None):
        class Detecciones:
            """Imita boxes de ultralytics: admite len() y expone xyxy y conf."""

            xyxy = SimpleNamespace(tolist=lambda: cajas)
            conf = SimpleNamespace(tolist=lambda: confianzas or [0.9] * len(cajas))

            def __len__(self):
                return len(cajas)

        return [SimpleNamespace(boxes=Detecciones())]

    def test_un_fallo_del_detector_no_interrumpe_la_lectura(self):
        with patch.object(detector, 'modelo_disponible', return_value=True), \
             patch.object(detector, 'cargar_detector', side_effect=RuntimeError('pesos')):
            self.assertIsNone(detector.detectar_filas(Image.new('RGB', (80, 80))))

    def test_conserva_las_tres_detecciones_mas_seguras(self):
        extra = TRES_FILAS + [[0, 400, 20, 420]]
        modelo = SimpleNamespace(
            predict=lambda **kwargs: self._salida(extra, [0.9, 0.8, 0.7, 0.3]))
        with patch.object(detector, 'modelo_disponible', return_value=True), \
             patch.object(detector, 'cargar_detector', return_value=modelo):
            orden = detector.detectar_filas(Image.new('RGB', (200, 500)))
        self.assertEqual(orden['resultado'], TRES_FILAS[2])

    def test_con_tres_filas_entrega_los_recortes_del_mismo_formato(self):
        foto = Image.open(suma_generada((104, 286, 390))).convert('RGB')
        cajas = dict(zip(detector.RECORTES, TRES_FILAS))
        with patch.object(detector, 'detectar_filas', return_value=cajas):
            imagen, vista, recortes, ampliadas, angulo = detector.separar_con_yolo(foto)
        self.assertEqual(set(recortes), set(lector.RECORTES))
        self.assertEqual(angulo, 0.0)
        self.assertEqual(vista.size, imagen.size)
        for nombre in lector.RECORTES:
            self.assertEqual(recortes[nombre].mode, 'RGB')
            self.assertEqual(len(ampliadas[nombre]), 4)


class FotografiaDanadaTests(SimpleTestCase):
    def test_un_error_de_importacion_al_abrir_pide_otra_fotografia(self):
        # ultralytics reemplaza PIL.Image.open por una versión que busca códecs.
        with patch.object(lector, 'Image', create=True), \
             patch('PIL.Image.open', side_effect=ModuleNotFoundError('pi_heif')):
            with self.assertRaises(lector.PhotoNotReadable):
                lector.preparar_suma(BytesIO(b'no es una imagen'))
