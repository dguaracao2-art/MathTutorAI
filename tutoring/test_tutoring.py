"""Regresión de reglas, pantalla y transición hacia una corrección."""
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Exercise
from .services.hints import hints_for
from .services.sum_review import review_sum


class ArithmeticTests(SimpleTestCase):
    def test_expected_examples_and_first_column(self):
        cases = [(23, 14, 37, 'correcto', None), (23, 14, 32, 'requiere_revision', 'unidades'),
                 (28, 17, 35, 'requiere_revision', 'decenas'),
                 (999, 1, 1000, 'correcto', None), (999, 1, 900, 'requiere_revision', 'centenas'),
                 (0, 0, 0, 'correcto', None), (0, 999, 999, 'correcto', None),
                 (999, 999, 1998, 'correcto', None),
                 (999, 999, 998, 'requiere_revision', 'unidades de millar'),
                 (0, 0, 1000, 'requiere_revision', 'unidades de millar')]
        for a, b, written, status, column in cases:
            with self.subTest(a=a, b=b, written=written):
                result = review_sum(a, b, written)
                self.assertEqual((result['status'], result['column_name']), (status, column))
                self.assertEqual(len(hints_for(result)), 0 if status == 'correcto' else 2)
                self.assertNotIn('expected', str(result))

    def test_various_operands_with_and_without_carries(self):
        for a in range(0, 1000, 43):
            for b in range(0, 1000, 37):
                self.assertEqual(review_sum(a, b, a + b)['status'], 'correcto')

    def test_inputs_must_be_confirmed_in_range(self):
        for values in [(-1, 2, 1), (1000, 0, 1000), (2, 1000, 1002),
                       (999, 999, 10000), (True, 1, 2)]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                review_sum(*values)

    def test_hints_do_not_reveal_answer_or_diagnose_unseen_cause(self):
        review = review_sum(28, 17, 35)
        self.assertEqual(review['hint_code'], 'incoming_carry')
        text = ' '.join(hints_for(review))
        self.assertNotIn('45', text)
        self.assertNotIn('olvidaste', text)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ReviewFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='aprendiz', password='test-pass')
        cls.exercise = Exercise.objects.create(operand_a=23, operand_b=14)

    def setUp(self):
        self.client.force_login(self.user)
        self.client.post(reverse('tutoring:select_exercise', args=[self.exercise.pk]))
        self.reader = patch('tutoring.views.leer_fotografia', return_value={
            'estado': 'pendiente_de_confirmacion', 'source': 'trocr-small-handwritten',
            'propuesta': {'operand_a': 23, 'operand_b': 14, 'written_result': 32},
            'can_confirm': True, 'mensaje': 'Revisa los números.',
        })
        self.reader.start()
        self.addCleanup(self.reader.stop)

    def photo(self):
        b = BytesIO()
        Image.new('RGB', (40, 40), 'white').save(b, 'PNG')
        return SimpleUploadedFile('suma.png', b.getvalue(), content_type='image/png')

    def confirm(self, written=32):
        token = self.client.post(reverse('tutoring:upload_photo'), {
            'exercise_id': self.exercise.pk, 'photo': self.photo(),
        }).json()['reading_token']
        return self.client.post(reverse('tutoring:confirm_sum'), {
            'exercise_id': self.exercise.pk, 'reading_token': token, 'photo': self.photo(),
            'operand_a': 23, 'operand_b': 14, 'written_result': written,
        }).json()['confirmed']

    def action(self, name, confirmed, **more):
        return self.client.post(reverse('tutoring:' + name), {
            'exercise_id': self.exercise.pk,
            'confirmation_id': confirmed['confirmation_id'], **more,
        })

    def test_cannot_grade_before_human_confirmation(self):
        self.assertRedirects(self.client.post(reverse('tutoring:check_sum')), reverse('tutoring:exercise_detail'))
        self.assertNotIn('sum_review', self.client.session)

    def test_wrong_result_two_hints_and_retake(self):
        confirmed = self.confirm()
        self.assertIn('Comprobar mi suma', self.client.get(reverse('tutoring:exercise_detail')).content.decode())
        self.assertRedirects(self.action('check_sum', confirmed), reverse('tutoring:review_result'))
        page = self.client.get(reverse('tutoring:review_result'))
        self.assertContains(page, 'Requiere revisión')
        self.assertContains(page, 'unidades')
        self.assertNotContains(page, 'Pista 1')
        self.assertNotContains(page, '37')
        self.action('show_hint', confirmed, level='2')
        self.assertEqual(self.client.session['sum_review']['hint_level'], 0)
        self.action('show_hint', confirmed, level='1')
        self.assertContains(self.client.get(reverse('tutoring:review_result')), 'Pista 1')
        self.action('show_hint', confirmed, level='2')
        self.action('show_hint', confirmed, level='3')
        self.assertEqual(self.client.session['sum_review']['hint_level'], 2)
        self.assertContains(self.client.get(reverse('tutoring:review_result')), 'Pista 2')
        self.action('check_sum', confirmed)
        self.assertEqual(self.client.session['sum_practice']['attempts'], 1)
        self.action('retry_sum', confirmed)
        self.assertNotIn('confirmed_sum', self.client.session)
        self.assertNotIn('sum_review', self.client.session)
        self.assertEqual(self.client.session['sum_practice']['attempts'], 1)
        next_confirmed = self.confirm(37)
        self.action('check_sum', next_confirmed)
        page = self.client.get(reverse('tutoring:review_result'))
        self.assertContains(page, 'Corregido')
        self.assertContains(page, 'Intento 2')
        self.assertNotContains(page, 'Ver pista')

    def test_correct_first_time_is_correcto(self):
        confirmed = self.confirm(37)
        self.action('check_sum', confirmed)
        self.assertContains(self.client.get(reverse('tutoring:review_result')), 'Correcto')

    def test_new_upload_clears_old_review_and_does_not_increment_attempts(self):
        confirmed = self.confirm()
        self.action('check_sum', confirmed)
        self.client.post(reverse('tutoring:upload_photo'), {'exercise_id': self.exercise.pk, 'photo': self.photo()})
        self.assertNotIn('sum_review', self.client.session)
        self.assertRedirects(self.action('show_hint', confirmed, level='1'), reverse('tutoring:exercise_detail'))
        self.assertEqual(self.client.session['sum_practice']['attempts'], 1)

    def test_stale_confirmation_and_other_user_cannot_review(self):
        first = self.confirm()
        second = self.confirm()
        self.assertRedirects(self.action('check_sum', first), reverse('tutoring:exercise_detail'))
        self.assertNotIn('sum_review', self.client.session)
        self.action('check_sum', second)
        other = Client()
        other.force_login(self.user)
        other.post(reverse('tutoring:select_exercise', args=[self.exercise.pk]))
        self.assertRedirects(other.post(reverse('tutoring:show_hint'), {
            'exercise_id': self.exercise.pk, 'confirmation_id': second['confirmation_id'],
            'level': '1',
        }), reverse('tutoring:exercise_detail'))

    def test_get_cannot_change_practice_and_csrf_is_checked(self):
        confirmed = self.confirm()
        self.action('check_sum', confirmed)
        for name in ('check_sum', 'show_hint', 'retry_sum'):
            self.assertEqual(self.client.get(reverse('tutoring:' + name)).status_code, 405)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.user)
        protected.post(reverse('tutoring:select_exercise', args=[self.exercise.pk]))
        self.assertEqual(protected.post(reverse('tutoring:check_sum'), {
            'exercise_id': self.exercise.pk, 'confirmation_id': confirmed['confirmation_id'],
        }).status_code, 403)
