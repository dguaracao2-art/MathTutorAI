"""Banco ampliado: importación sin duplicados y navegación sin fotografías."""
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .models import Exercise


class ExerciseImportTests(TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.csv = Path(self.folder.name) / 'referencia.csv'

    def load(self, text, **options):
        self.csv.write_text(text, encoding='utf-8-sig')
        output = StringIO()
        call_command('cargar_sumas', str(self.csv), stdout=output, **options)
        return output.getvalue()

    def test_importa_operandos_y_repetir_no_duplica_ni_importa_resultados(self):
        text = 'operand_a,operand_b,written_result\n23,14,9999\n28,17,0\n23,14,37\n'
        self.load(text)
        ids = list(Exercise.objects.values_list('pk', flat=True))
        again = self.load(text)
        self.assertEqual(list(Exercise.objects.values_list('pk', flat=True)), ids)
        self.assertEqual(list(Exercise.objects.values_list('operand_a', 'operand_b')), [(23, 14), (28, 17)])
        self.assertIn('Añadidas: 0', again)
        self.assertIn('Filas repetidas: 1', again)

    def test_entrada_invalida_no_guarda_un_lote_parcial(self):
        for invalid in ('', '-1', '1000', '3.5', 'uno'):
            with self.subTest(invalid=invalid), self.assertRaises(CommandError):
                self.load(f'operand_a,operand_b\n23,14\n28,{invalid}\n')
            self.assertFalse(Exercise.objects.exists())

    def test_conserva_una_suma_desactivada_y_admite_punto_y_coma(self):
        existing = Exercise.objects.create(operand_a=23, operand_b=14, is_active=False)
        self.load('operand_a;operand_b\n23;14\n28;17\n')
        existing.refresh_from_db()
        self.assertFalse(existing.is_active)
        self.assertEqual(Exercise.objects.get(operand_a=23).pk, existing.pk)
        self.assertTrue(Exercise.objects.get(operand_a=28).has_carry)

    def test_simulacion_y_archivo_inexistente_no_modifican_banco(self):
        self.load('operand_a,operand_b\n23,14\n', simular=True)
        self.assertFalse(Exercise.objects.exists())
        with self.assertRaises(CommandError):
            call_command('cargar_sumas', str(Path(self.folder.name) / 'no_existe.csv'), stdout=StringIO())
        self.assertFalse(Exercise.objects.exists())

    def test_banco_nuevo_incluye_las_mismas_53_y_no_duplica_al_repetir(self):
        call_command('cargar_sumas', stdout=StringIO())
        self.assertEqual(Exercise.objects.count(), 53)
        pairs = set(Exercise.objects.values_list('operand_a', 'operand_b'))
        self.assertTrue({(23, 14), (28, 17), (400, 600)} <= pairs)
        ids = list(Exercise.objects.values_list('pk', flat=True))
        call_command('cargar_sumas', stdout=StringIO())
        self.assertEqual(list(Exercise.objects.values_list('pk', flat=True)), ids)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ExerciseBankNavigationTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user('banco', password='prueba-local'))
        for a in range(20, 35):
            Exercise.objects.create(operand_a=a, operand_b=17)
        Exercise.objects.create(operand_a=500, operand_b=17, is_active=False)

    def test_paginas_completas_sin_duplicados_ni_sumas_desactivadas(self):
        first = self.client.get(reverse('tutoring:exercise_list'))
        second = self.client.get(reverse('tutoring:exercise_list'), {'page': 2})
        ids1 = {e.pk for e in first.context['exercises']}
        ids2 = {e.pk for e in second.context['exercises']}
        self.assertEqual((len(ids1), len(ids2)), (10, 5))
        self.assertFalse(ids1 & ids2)
        self.assertEqual(first.context['page_obj'].paginator.count, 15)

    def test_busqueda_por_suma_y_numero_conserva_query_al_paginar(self):
        pair = self.client.get(reverse('tutoring:exercise_list'), {'q': '28 + 17'})
        self.assertEqual([(e.operand_a, e.operand_b) for e in pair.context['exercises']], [(28, 17)])
        number = self.client.get(reverse('tutoring:exercise_list'), {'q': '17'})
        self.assertEqual(number.context['page_obj'].paginator.count, 15)
        self.assertContains(number, '?q=17&amp;page=2')

    def test_busqueda_invalida_y_pagina_invalida_no_rompen_la_pantalla(self):
        bad = self.client.get(reverse('tutoring:exercise_list'), {'q': '<script>1</script>'})
        self.assertEqual(bad.context['page_obj'].paginator.count, 0)
        self.assertContains(bad, 'Busca un número')
        self.assertNotContains(bad, '<script>1</script>')
        page = self.client.get(reverse('tutoring:exercise_list'), {'page': 'invalida'})
        self.assertEqual(page.context['page_obj'].number, 1)


class ReaderPreparationTests(SimpleTestCase):
    @patch('tutoring.management.commands.preparar_lector.cargar_modelo')
    def test_prepara_la_cache_sin_necesitar_foto(self, model):
        call_command('preparar_lector', solo_local=True, stdout=StringIO())
        model.assert_called_once_with('microsoft/trocr-small-handwritten', True)

    @patch('tutoring.management.commands.preparar_lector.cargar_modelo', side_effect=OSError('sin caché'))
    def test_cache_ausente_se_reporta_como_error(self, model):
        with self.assertRaises(CommandError):
            call_command('preparar_lector', solo_local=True, stdout=StringIO())
