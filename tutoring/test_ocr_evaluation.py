"""Pruebas del contador de exactitud; no descargan modelos ni usan fotos privadas."""
import csv
import importlib.util
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location(
    '_math_ocr_evaluation', Path(__file__).resolve().parents[1] / 'tools' / 'medir_exactitud.py')
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


class OCREvaluationTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def dataset(self, count=2, carries=None, delimiter=','):
        rows = []
        for index in range(count):
            carry = (index >= count // 2) if carries is None else index < carries
            name = f'foto{index:02d}.png'
            # Solo se comprueban referencias y huellas; el OCR está fuera de esta prueba.
            (self.folder / name).write_bytes(f'contenido distinto {index}'.encode())
            rows.append({'archivo': name, 'operand_a': 8 if carry else 1,
                         'operand_b': 9 if carry else 2, 'written_result': 12})
        self.write_rows(rows, delimiter)
        return rows

    def write_rows(self, rows, delimiter=','):
        with (self.folder / 'referencia_ocr.csv').open('w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=evaluation.CABECERA, delimiter=delimiter)
            writer.writeheader()
            writer.writerows(rows)

    def test_tres_campos_exactos_y_lecturas_vacias_cuentan_en_el_total(self):
        self.dataset(4)
        refs = evaluation.cargar_referencias(self.folder)
        propuestas = [{c: r[c] for c in evaluation.CAMPOS} for r in refs]
        propuestas[1]['operand_b'] = None
        propuestas[2]['written_result'] = 17
        propuestas[3] = dict.fromkeys(evaluation.CAMPOS)
        _, result = evaluation.comparar(refs, propuestas)
        self.assertEqual((result['exactas'], result['imagenes'], result['porcentaje_exacto']), (1, 4, 25))
        self.assertEqual(result['aciertos_por_campo']['operand_b'], 2)
        self.assertIsNone(result['umbral_numerico_45_de_50'])

    def test_se_compara_con_lo_escrito_y_no_con_la_respuesta_matematica(self):
        self.dataset(1, carries=1)
        refs = evaluation.cargar_referencias(self.folder)
        _, exact = evaluation.comparar(refs, [{'operand_a': 8, 'operand_b': 9, 'written_result': 12}])
        _, wrong = evaluation.comparar(refs, [{'operand_a': 8, 'operand_b': 9, 'written_result': 17}])
        self.assertEqual(exact['exactas'], 1)
        self.assertEqual(wrong['exactas'], 0)

    def test_umbral_final_44_no_y_45_si(self):
        self.dataset(50)
        refs = evaluation.cargar_referencias(self.folder)
        for hits in (44, 45):
            propuestas = [{c: r[c] for c in evaluation.CAMPOS} if i < hits else {}
                          for i, r in enumerate(refs)]
            _, result = evaluation.comparar(refs, propuestas, final=True)
            self.assertEqual(result['umbral_numerico_45_de_50'], hits == 45)
        with self.assertRaises(ValueError):
            evaluation.comparar(refs[:2], propuestas[:2], final=True)

    def test_csv_con_bom_y_separador_de_excel(self):
        for delimiter in (',', ';'):
            self.dataset(delimiter=delimiter)
            self.assertEqual(len(evaluation.cargar_referencias(self.folder)), 2)

    def test_rechaza_campos_vacios_fuera_de_rango_y_archivo_repetido(self):
        rows = self.dataset()
        for field, value in (('operand_a', ''), ('operand_a', '1000'),
                             ('operand_b', '-1'), ('written_result', '10000')):
            changed = [dict(r) for r in rows]
            changed[0][field] = value
            self.write_rows(changed)
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                evaluation.cargar_referencias(self.folder)
        self.write_rows([rows[0], rows[0]])
        with self.assertRaisesRegex(ValueError, 'repetido'):
            evaluation.cargar_referencias(self.folder)

    def test_rechaza_foto_identica_renombrada_y_rutas_fuera_de_carpeta(self):
        rows = self.dataset()
        (self.folder / rows[1]['archivo']).write_bytes((self.folder / rows[0]['archivo']).read_bytes())
        with self.assertRaisesRegex(ValueError, 'duplicada'):
            evaluation.cargar_referencias(self.folder)
        rows[0]['archivo'] = '../fuera.png'
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, 'solo el nombre'):
            evaluation.cargar_referencias(self.folder)

    def test_final_exige_50_balance_y_ninguna_foto_de_ajuste(self):
        ajuste = self.folder / 'ajuste'
        ajuste.mkdir()
        (ajuste / 'anterior.jpg').write_bytes(b'foto de ajuste independiente')
        self.dataset(2)
        with self.assertRaises(ValueError):
            evaluation.cargar_referencias(self.folder, final=True, ajuste=ajuste)
        self.dataset(50, carries=24)
        with self.assertRaises(ValueError):
            evaluation.cargar_referencias(self.folder, final=True, ajuste=ajuste)
        rows = self.dataset(50)
        self.assertEqual(len(evaluation.cargar_referencias(self.folder, final=True, ajuste=ajuste)), 50)
        (ajuste / 'copiada.jpg').write_bytes((self.folder / rows[0]['archivo']).read_bytes())
        with self.assertRaisesRegex(ValueError, 'ajustar'):
            evaluation.cargar_referencias(self.folder, final=True, ajuste=ajuste)

    def test_plantilla_no_sobrescribe_la_referencia(self):
        self.dataset()
        before = (self.folder / 'referencia_ocr.csv').read_bytes()
        with self.assertRaises(FileExistsError):
            evaluation.crear_plantilla(self.folder)
        self.assertEqual((self.folder / 'referencia_ocr.csv').read_bytes(), before)

    def test_ensayo_incompleto_no_produce_resultados(self):
        self.dataset()
        with patch('sys.stderr', new=StringIO()):
            code = evaluation.main([str(self.folder), '--final'])
        self.assertEqual(code, 1)
        self.assertFalse((self.folder / 'resultado_ocr.csv').exists())

    def test_no_se_acepta_perder_una_foto_en_el_denominador(self):
        self.dataset()
        refs = evaluation.cargar_referencias(self.folder)
        with self.assertRaises(ValueError):
            evaluation.comparar(refs, [{}])

    def test_comando_guarda_comparacion_y_conserva_la_referencia(self):
        rows = self.dataset()
        before = (self.folder / 'referencia_ocr.csv').read_bytes()
        fake = SimpleNamespace(MODELO='lector-de-prueba', REVISION_MODELO='prueba',
                               cargar_modelo=Mock(), leer_fotografia=Mock(side_effect=[
                                   {'propuesta': {c: rows[0][c] for c in evaluation.CAMPOS}},
                                   {'propuesta': dict.fromkeys(evaluation.CAMPOS)},
                               ]))
        with patch.dict('sys.modules', {'tutoring.services.handwriting': fake}), patch('sys.stdout', new=StringIO()):
            code = evaluation.main([str(self.folder)])
        self.assertEqual(code, 0)
        result = json.loads((self.folder / 'resumen_ocr.json').read_text())
        self.assertEqual((result['exactas'], result['imagenes'], result['modo']), (1, 2, 'ensayo'))
        with (self.folder / 'resultado_ocr.csv').open(encoding='utf-8-sig', newline='') as f:
            details = list(csv.DictReader(f))
        self.assertEqual(len(details), 2)
        self.assertEqual(details[1]['lectura_operand_a'], '')
        self.assertEqual((self.folder / 'referencia_ocr.csv').read_bytes(), before)
        fake.cargar_modelo.assert_called_once_with('lector-de-prueba', True)

    def test_un_fallo_del_modelo_no_publica_una_evaluacion_parcial(self):
        rows = self.dataset()
        fake = SimpleNamespace(MODELO='lector-de-prueba', REVISION_MODELO='prueba',
                               cargar_modelo=Mock(), leer_fotografia=Mock(side_effect=[
                                   {'propuesta': {c: rows[0][c] for c in evaluation.CAMPOS}},
                                   RuntimeError('modelo no disponible'),
                               ]))
        with patch.dict('sys.modules', {'tutoring.services.handwriting': fake}), \
                patch('sys.stdout', new=StringIO()), patch('sys.stderr', new=StringIO()):
            code = evaluation.main([str(self.folder)])
        self.assertEqual(code, 1)
        self.assertFalse((self.folder / 'resultado_ocr.csv').exists())
        self.assertFalse((self.folder / 'resumen_ocr.json').exists())

    def test_informe_separado_guarda_etapa_y_texto_sin_tocar_resultado_anterior(self):
        rows = self.dataset(1)
        original = self.folder / 'resultado_ocr.csv'
        original.write_text('resultado anterior', encoding='utf-8')
        destination = self.folder / 'medicion_nueva'
        fake = SimpleNamespace(MODELO='lector-de-prueba', REVISION_MODELO='prueba',
            cargar_modelo=Mock(), leer_fotografia=Mock(return_value={
                'propuesta': {c: rows[0][c] for c in evaluation.CAMPOS},
                'etapa': 'reconocimiento', 'mensaje': 'Completar manualmente no suma un acierto OCR.',
                'lecturas_crudas': {'operand_a': '1', 'operand_b': '2', 'written_result': '1 2'},
            }))
        with patch.dict('sys.modules', {'tutoring.services.handwriting': fake}), \
                patch('sys.stdout', new=StringIO()):
            code = evaluation.main([str(self.folder), '--salida', str(destination)])
        self.assertEqual(code, 0)
        self.assertEqual(original.read_text(), 'resultado anterior')
        with (destination / 'resultado_ocr.csv').open(encoding='utf-8-sig', newline='') as stream:
            detail = list(csv.DictReader(stream))[0]
        self.assertEqual(detail['etapa'], 'reconocimiento')
        self.assertEqual(detail['texto_crudo_written_result'], '1 2')
        summary = json.loads((destination / 'resumen_ocr.json').read_text())
        self.assertEqual(len(summary['sha256_referencia']), 64)
        fake.leer_fotografia.assert_called_once_with(
            self.folder / rows[0]['archivo'], incluir_diagnostico=True)

    def test_salida_existente_no_se_sobrescribe_ni_ejecuta_el_modelo(self):
        self.dataset(1)
        destination = self.folder / 'medicion_existente'
        destination.mkdir()
        report = destination / 'resumen_ocr.json'
        report.write_text('resumen anterior', encoding='utf-8')
        fake = SimpleNamespace(MODELO='prueba', REVISION_MODELO='prueba',
                               cargar_modelo=Mock(), leer_fotografia=Mock())
        with patch.dict('sys.modules', {'tutoring.services.handwriting': fake}), \
                patch('sys.stderr', new=StringIO()):
            code = evaluation.main([str(self.folder), '--salida', str(destination)])
        self.assertEqual(code, 1)
        self.assertEqual(report.read_text(), 'resumen anterior')
        fake.cargar_modelo.assert_not_called()
