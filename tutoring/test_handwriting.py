"""Regresiones del lector con imágenes generadas; no contiene fotos personales."""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from PIL import Image

from .services import handwriting as lector


def suma_generada(numeros, *, tenue=False, fondo=False):
    import cv2
    import numpy as np

    imagen = np.full((640, 640, 3), 255, dtype=np.uint8)
    tinta = (190, 194, 214) if tenue else (35, 65, 145)
    for texto, base in zip(map(str, numeros), (140, 220, 320)):
        ancho = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 3)[0][0]
        cv2.putText(imagen, texto, (410 - ancho, base), cv2.FONT_HERSHEY_SIMPLEX,
                    1.5, tinta, 3, cv2.LINE_AA)
    cv2.line(imagen, (225, 205), (255, 205), tinta, 3)
    cv2.line(imagen, (240, 190), (240, 220), tinta, 3)
    cv2.line(imagen, (270, 245), (420, 245), tinta, 3)
    if fondo:
        cv2.rectangle(imagen, (40, 500), (60, 610), (30, 40, 160), -1)
    archivo = BytesIO()
    Image.fromarray(imagen).save(archivo, 'PNG')
    archivo.seek(0)
    return archivo


class SegmentacionTests(SimpleTestCase):
    def test_otras_sumas_tinta_tenue_y_objeto_azul_en_fondo(self):
        for numeros, tenue, fondo in (
            ((5, 7, 12), False, False),
            ((104, 286, 390), True, False),
            ((987, 998, 1985), False, True),
        ):
            with self.subTest(numeros=numeros, tenue=tenue, fondo=fondo):
                archivo = suma_generada(numeros, tenue=tenue, fondo=fondo)
                _, _, recortes, cajas, _ = lector.preparar_suma(archivo)
                self.assertEqual(set(recortes), set(lector.RECORTES))
                for nombre, centro_y in zip(lector.RECORTES, (125, 205, 305)):
                    x1, y1, x2, y2 = cajas[nombre]
                    self.assertLess(y1, centro_y)
                    self.assertGreater(y2, centro_y)
                    self.assertGreater(x1, 260)
                    self.assertLess(x2, 450)
                    self.assertLess(recortes[nombre].convert('L').getextrema()[0], 200)

    def test_cuadricula_gris_no_se_presenta_como_tinta_al_modelo(self):
        import numpy as np
        from PIL import ImageDraw

        foto = Image.open(suma_generada((104, 286, 381))).convert('RGB')
        dibujo = ImageDraw.Draw(foto)
        # Líneas finas de un cuaderno, distintas de la tinta azul.
        for x in range(20, 640, 40):
            dibujo.line((x, 0, x, 640), fill=(170, 170, 170))
        for y in range(20, 640, 40):
            dibujo.line((0, y, 640, y), fill=(170, 170, 170))
        archivo = BytesIO()
        foto.save(archivo, 'PNG')
        _, _, recortes, _, _ = lector.preparar_suma(archivo)
        for recorte in recortes.values():
            tonos = set(np.unique(np.asarray(recorte.convert('L'))).tolist())
            self.assertEqual(tonos, {0, 255})

    def test_fotografia_danada_no_inicia_el_modelo(self):
        with patch.object(lector, 'reconocer_recortes') as modelo:
            resultado = lector.leer_fotografia(BytesIO(b'esto no es una imagen'))
        self.assertFalse(resultado['can_confirm'])
        modelo.assert_not_called()


class ReconocimientoTests(SimpleTestCase):
    def test_lote_conserva_orden_y_resultado_incorrecto_escrito(self):
        recortes = {nombre: Image.new('RGB', (20, 20)) for nombre in reversed(lector.RECORTES)}
        procesador = Mock(return_value=SimpleNamespace(pixel_values='pixeles'))
        procesador.batch_decode.return_value = ['1 0 4', '2 8 6', '3 8 1']
        modelo = Mock()
        with patch.object(lector, 'cargar_modelo', return_value=(procesador, modelo)):
            resultado = lector.reconocer_recortes(recortes, local_files_only=True)
        self.assertEqual(resultado['propuesta'],
                         {'operand_a': 104, 'operand_b': 286, 'written_result': 381})
        self.assertEqual(resultado['estado'], 'pendiente_de_confirmacion')
        procesador.assert_called_once_with(
            images=[recortes[nombre] for nombre in lector.RECORTES], return_tensors='pt')
        modelo.generate.assert_called_once()

    def test_un_fallo_de_modelo_libera_el_lector(self):
        with patch.object(lector, 'cargar_modelo', side_effect=RuntimeError('sin memoria')):
            with self.assertRaises(lector.ReaderUnavailable):
                lector.reconocer_recortes({})
        self.assertTrue(lector._inference_lock.acquire(blocking=False))
        lector._inference_lock.release()
