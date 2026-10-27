"""RNF-06: 80 casos con respuestas de referencia independientes del servicio.

Cada fila fija una suma, su respuesta correcta y una respuesta incorrecta con
la primera columna discrepante esperada. No se usa OCR ni se guardan imágenes.
Las llevadas son aritméticas; no se evalúan anotaciones manuscritas de llevadas.
"""
from unittest import TestCase

from .services.sum_review import review_sum


# A, B, respuesta correcta, respuesta incorrecta, primera columna discrepante.
# Veinte sumas sin llevadas y veinte con llevadas; dos casos por fila.
SIN_LLEVADAS = (
    (0, 0, 0, 1, 'unidades'),
    (0, 7, 7, 0, 'unidades'),
    (5, 0, 5, 15, 'decenas'),
    (2, 3, 5, 4, 'unidades'),
    (12, 6, 18, 28, 'decenas'),
    (20, 30, 50, 5, 'unidades'),
    (23, 14, 37, 32, 'unidades'),
    (42, 16, 58, 48, 'decenas'),
    (34, 25, 59, 69, 'decenas'),
    (61, 28, 89, 88, 'unidades'),
    (100, 200, 300, 200, 'centenas'),
    (123, 234, 357, 347, 'decenas'),
    (406, 152, 558, 458, 'centenas'),
    (700, 80, 780, 708, 'unidades'),
    (801, 98, 899, 999, 'centenas'),
    (909, 0, 909, 999, 'decenas'),
    (999, 0, 999, 99, 'centenas'),
    (0, 999, 999, 1999, 'unidades de millar'),
    (111, 222, 333, 303, 'decenas'),
    (321, 456, 777, 177, 'centenas'),
)
CON_LLEVADAS = (
    (5, 7, 12, 2, 'decenas'),
    (8, 9, 17, 27, 'decenas'),
    (9, 1, 10, 0, 'decenas'),
    (28, 17, 45, 35, 'decenas'),
    (46, 38, 84, 74, 'decenas'),
    (59, 24, 83, 82, 'unidades'),
    (95, 7, 102, 2, 'centenas'),
    (99, 1, 100, 90, 'decenas'),
    (99, 99, 198, 188, 'decenas'),
    (168, 257, 425, 415, 'decenas'),
    (186, 237, 423, 323, 'centenas'),
    (555, 555, 1110, 110, 'unidades de millar'),
    (999, 1, 1000, 900, 'centenas'),
    (999, 999, 1998, 998, 'unidades de millar'),
    (875, 125, 1000, 0, 'unidades de millar'),
    (450, 550, 1000, 100, 'centenas'),
    (678, 245, 923, 913, 'decenas'),
    (709, 291, 1000, 1001, 'unidades'),
    (908, 92, 1000, 1100, 'centenas'),
    (399, 602, 1001, 1, 'unidades de millar'),
)


class ArithmeticAcceptanceTests(TestCase):
    """Cada caso tiene su propio identificador en la salida de unittest/Django."""


def _case_test(a, b, written, status, column):
    def test(self):
        result = review_sum(a, b, written)
        self.assertEqual(result['status'], status)
        self.assertEqual(result['column_name'], column)
        names = ('unidades', 'decenas', 'centenas', 'unidades de millar')
        self.assertEqual(result['column_index'], names.index(column) if column else None)
        marked = [c['name'] for c in result['columns'] if c['needs_review']]
        self.assertEqual(marked, [column] if column else [])
        # La presentación conserva la respuesta entregada, incluso si es errónea.
        displayed = ''.join(c['written_result'] for c in result['columns'])
        self.assertEqual(displayed, str(written))
        self.assertNotIn('expected', result)
    test.__doc__ = f'{a} + {b}, escrito {written}: {status}; columna {column}.'
    return test


for index, (a, b, correct, wrong, column) in enumerate(SIN_LLEVADAS + CON_LLEVADAS):
    for offset, (written, status, expected_column) in enumerate((
        (correct, 'correcto', None), (wrong, 'requiere_revision', column),
    )):
        number = index * 2 + offset + 1
        setattr(ArithmeticAcceptanceTests, f'test_RNF06_{number:03d}',
                _case_test(a, b, written, status, expected_column))
